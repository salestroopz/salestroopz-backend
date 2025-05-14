# app/agents/imap_reply_agent.py

import imaplib
import email  # For parsing email messages
from email.header import decode_header
from email.utils import parsedate_to_datetime  # For parsing date headers
import re # For cleaning email body (you were using re.split)
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

# Assuming these paths are correct for your project structure
from app.db import database as db_ops # Using an alias for clarity
# from app.utils.logger import logger # Assuming you have a custom logger setup
# from app.utils.config import settings # If used for IMAP overrides
from app.agents.reply_classifier_agent import ReplyClassifierAgent

# If not using a custom logger from app.utils.logger, set up a standard one:
import logging
logger = logging.getLogger(__name__)
# For basic logging output if not configured elsewhere:
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class ImapReplyAgent:
    def __init__(self):
        logger.info("ImapReplyAgent: Initializing...")
        try:
            # Instantiate your existing ReplyClassifierAgent
            self.reply_classifier = ReplyClassifierAgent()
            logger.info("ImapReplyAgent: ReplyClassifierAgent instantiated successfully.")
        except Exception as e:
            logger.error(f"ImapReplyAgent: Failed to instantiate ReplyClassifierAgent: {e}", exc_info=True)
            self.reply_classifier = None  # Handle gracefully

    def _decode_email_header(self, header_value: Any) -> str:
        if not header_value:
            return ""
        
        # Handle cases where header_value might be a list (e.g., some 'Received' headers)
        if isinstance(header_value, list):
            # Attempt to join or take the most relevant part; for simple headers, first is often enough
            header_value = header_value[0] if header_value else ""

        # Ensure header_value is a string or can be converted to one for decode_header
        if isinstance(header_value, email.header.Header):
            header_value = str(header_value) # Convert Header object to string
        elif not isinstance(header_value, str):
            try:
                header_value = str(header_value)
            except:
                logger.warning(f"ImapReplyAgent: Could not convert header value to string: {type(header_value)}")
                return "" # Return empty if unconvertible

        decoded_parts = []
        try:
            for part_bytes, charset in decode_header(header_value):
                if isinstance(part_bytes, bytes):
                    try:
                        decoded_parts.append(part_bytes.decode(charset or 'utf-8', 'replace')) # 'replace' is safer
                    except (UnicodeDecodeError, LookupError):
                        # Fallback for very problematic charsets
                        decoded_parts.append(part_bytes.decode('latin1', 'replace'))
                else:  # part_bytes is already a string (e.g., if charset was None or 'unknown-8bit')
                    decoded_parts.append(part_bytes)
        except Exception as e:
            logger.error(f"ImapReplyAgent: Error decoding header part: {e}. Header: '{header_value[:100]}...'")
            return header_value # Return original on error, or a placeholder

        return "".join(decoded_parts)

    def _get_cleaned_email_body_text(self, msg: email.message.Message) -> str:
        """
        Extracts and cleans the plain text body from an email.message.Message object.
        Tries to get the latest reply by stripping common quoted text and signatures.
        """
        body = ""
        if msg.is_multipart():
            # Walk through parts, prioritizing plain text not marked as attachment
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))

                if content_type == "text/plain" and "attachment" not in content_disposition.lower():
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        part_body = payload.decode(charset, 'replace') # Use 'replace' for safety

                        # Basic reply cleaning attempt:
                        # Split at common reply headers or typical signature dashes.
                        # More advanced libraries: 'email_reply_parser' or 'talon' (from Mailgun)
                        cleaned_part = re.split(r'\n\s*(?:On|El|Le)\s+.*\s+(?:wrote|écrit|escribió):|\n\s*--\s*\n?>', part_body, 1)[0]
                        body = cleaned_part.strip()
                        if body:  # Prefer the first non-empty plain text part that looks like a reply
                            break
                    except Exception as e:
                        logger.warning(f"ImapReplyAgent: Error decoding/cleaning multipart text part: {e}")
        else:  # Not multipart, try to get body directly
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    part_body = payload.decode(charset, 'replace')
                    cleaned_part = re.split(r'\n\s*(?:On|El|Le)\s+.*\s+(?:wrote|écrit|escribió):|\n\s*--\s*\n?>', part_body, 1)[0]
                    body = cleaned_part.strip()
                except Exception as e:
                    logger.warning(f"ImapReplyAgent: Error decoding/cleaning non-multipart text: {e}")
        
        # Fallback if no "clean" body was found, try to get any plain text
        if not body and msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")).lower():
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, 'replace').strip()
                        if body: break
                    except Exception:
                        continue # Ignore errors in fallback
        return body

    def _process_single_inbox(self, organization_id: int, imap_settings: Dict[str, Any]):
        logger.info(f"ImapReplyAgent: Processing inbox for Org ID: {organization_id}, User: {imap_settings.get('imap_username')}")
        
        imap_host = imap_settings.get('imap_host')
        # Ensure port is int, default correctly based on SSL
        default_port = 993 if imap_settings.get('imap_use_ssl', True) else 143
        imap_port = int(imap_settings.get('imap_port', default_port))
        imap_user = imap_settings.get('imap_username')
        
        # IMPORTANT: Password decryption needs a robust and secure mechanism.
        # Direct call to database._decrypt_data is okay if that function is secure
        # and handles session management or is a static method.
        encrypted_password = imap_settings.get('encrypted_imap_password')
        imap_password = None
        if encrypted_password:
            try:
                # This assumes db_ops has a _decrypt_data method. 
                # If it's a utility, import it directly or pass a decryptor instance.
                imap_password = db_ops._decrypt_data(encrypted_password) # Example, adjust if needed
            except Exception as e:
                logger.error(f"ImapReplyAgent: Failed to decrypt IMAP password for Org ID {organization_id}: {e}")
                return # Cannot proceed without password

        use_ssl = imap_settings.get('imap_use_ssl', True)
        last_processed_uid = imap_settings.get('last_imap_poll_uid') # This should come from DB for this org

        if not all([imap_host, imap_user, imap_password]):
            logger.error(f"ImapReplyAgent: Incomplete IMAP credentials for Org ID {organization_id}. Skipping.")
            return

        imap_conn: Optional[imaplib.IMAP4_SSL | imaplib.IMAP4] = None
        try:
            logger.debug(f"ImapReplyAgent: Connecting to IMAP {imap_host}:{imap_port} for Org ID {organization_id} (SSL: {use_ssl})")
            if use_ssl:
                imap_conn = imaplib.IMAP4_SSL(imap_host, imap_port)
            else:
                imap_conn = imaplib.IMAP4(imap_host, imap_port)
            
            status, login_response = imap_conn.login(imap_user, imap_password)
            if status != 'OK':
                logger.error(f"ImapReplyAgent: IMAP login failed for Org ID {organization_id}. Response: {login_response}")
                return
            logger.info(f"ImapReplyAgent: IMAP login successful for Org ID {organization_id}.")

            status, select_response = imap_conn.select("INBOX", readonly=False)
            if status != 'OK':
                logger.error(f"ImapReplyAgent: Failed to select INBOX for Org ID {organization_id}. Response: {select_response}")
                return

            search_criteria = '(UNSEEN)'
            # More robust UID handling:
            # If last_processed_uid is available and you store UIDVALIDITY for the mailbox:
            # status_validity, uid_validity_data = imap_conn.status('INBOX', '(UIDVALIDITY)')
            # if status_validity == 'OK' and stored_uid_validity == uid_validity_data[0] ...
            #    search_criteria = f'(UID {int(last_processed_uid) + 1}:*)'
            # else: # UIDVALIDITY changed or not stored, resync or use UNSEEN
            #    logger.warning("IMAP: UIDVALIDITY changed or missing. Falling back to UNSEEN search.")
            #    search_criteria = '(UNSEEN)' # Or trigger a full resync logic

            logger.debug(f"ImapReplyAgent: Searching INBOX with criteria: {search_criteria} for Org ID {organization_id} (Last UID: {last_processed_uid})")
            status, message_uids_bytes_list = imap_conn.uid('search', None, search_criteria)
            if status != 'OK':
                logger.error(f"ImapReplyAgent: IMAP search failed for Org ID {organization_id}. Response: {message_uids_bytes_list}")
                return

            email_uids_to_fetch_str = message_uids_bytes_list[0].decode().split()
            if not email_uids_to_fetch_str:
                logger.info(f"ImapReplyAgent: No new emails matching criteria for Org ID {organization_id}.")
                return
            logger.info(f"ImapReplyAgent: Found {len(email_uids_to_fetch_str)} new email(s) for Org ID {organization_id}.")
            
            new_max_uid_processed_this_cycle = int(last_processed_uid or 0)

            for email_uid_str in email_uids_to_fetch_str:
                email_uid_bytes = email_uid_str.encode() # Convert back to bytes for IMAP commands
                current_email_uid_int = int(email_uid_str)
                new_max_uid_processed_this_cycle = max(new_max_uid_processed_this_cycle, current_email_uid_int)

                logger.debug(f"ImapReplyAgent: Fetching email UID {email_uid_str} for Org ID {organization_id}")
                # Fetch essential headers and body structure first to avoid large downloads if not needed
                # status, msg_data = imap_conn.uid('fetch', email_uid_bytes, '(RFC822.HEADER BODYSTRUCTURE)')
                status, msg_data = imap_conn.uid('fetch', email_uid_bytes, '(RFC822)') # Full email for now
                
                if status != 'OK' or not msg_data or msg_data[0] is None:
                    logger.error(f"ImapReplyAgent: Failed to fetch email UID {email_uid_str} for Org ID {organization_id}")
                    continue

                # msg_data is typically a list of tuples, e.g., [(b'1 (UID 123 RFC822 {size}', email_bytes), b')']
                # Need to find the part that is just the email bytes
                raw_email_bytes = None
                if isinstance(msg_data[0], tuple) and len(msg_data[0]) == 2 and isinstance(msg_data[0][1], bytes):
                    raw_email_bytes = msg_data[0][1]
                elif isinstance(msg_data[0], bytes): # Simpler response format from some servers
                    raw_email_bytes = msg_data[0]

                if not raw_email_bytes:
                    logger.error(f"ImapReplyAgent: Could not extract raw email bytes for UID {email_uid_str}")
                    continue

                email_message = email.message_from_bytes(raw_email_bytes)
                
                # Extract headers
                message_id_header = self._decode_email_header(email_message.get("Message-ID"))
                in_reply_to_header = self._decode_email_header(email_message.get("In-Reply-To"))
                references_header = self._decode_email_header(email_message.get("References"))
                from_address_full = self._decode_email_header(email_message.get("From"))
                
                from_address_email_match = re.search(r'<([^>]+)>', from_address_full)
                from_address_email = from_address_email_match.group(1).strip() if from_address_email_match else from_address_full.strip()

                reply_subject = self._decode_email_header(email_message.get("Subject"))
                date_str = email_message.get("Date")
                received_at_dt = parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
                
                # Ensure timezone-aware datetime in UTC
                if received_at_dt.tzinfo is None:
                    received_at_dt = received_at_dt.replace(tzinfo=timezone.utc)
                else:
                    received_at_dt = received_at_dt.astimezone(timezone.utc)

                # Attempt to link reply to an outgoing email
                original_message_id_to_find = None
                if in_reply_to_header:
                    original_message_id_to_find = in_reply_to_header.strip("<> ") # Clean common wrapping
                elif references_header:
                    ref_ids = references_header.strip().split()
                    if ref_ids:
                        original_message_id_to_find = ref_ids[-1].strip("<> ")

                outgoing_log_entry = None
                if original_message_id_to_find:
                    logger.debug(f"ImapReplyAgent: Attempting to link reply via Message-ID: {original_message_id_to_find}")
                    # Assumes get_outgoing_email_log_by_message_id takes db session
                    with db_ops.SessionLocal() as db_session: # Create a new session for this operation
                         outgoing_log_entry = db_ops.get_outgoing_email_log_by_message_id(db_session, organization_id, original_message_id_to_find)


                lead_id, campaign_id, lcs_id = None, None, None
                lead_name_for_prompt = "Valued Prospect" # Default

                if outgoing_log_entry:
                    lead_id = outgoing_log_entry.get("lead_id")
                    campaign_id = outgoing_log_entry.get("campaign_id")
                    # Assuming your outgoing_log_entry might have lead_campaign_status_id or you fetch it
                    if lead_id: # Fetch LCS if not directly on log entry
                         with db_ops.SessionLocal() as db_session:
                            lcs_record = db_ops.get_lead_campaign_status(db_session, lead_id, campaign_id, organization_id) # Add org_id
                            if lcs_record: lcs_id = lcs_record.get("id")
                            # Fetch lead name
                            lead_details = db_ops.get_lead_by_id(db_session, lead_id, organization_id)
                            if lead_details: lead_name_for_prompt = lead_details.get("name", lead_name_for_prompt)

                    logger.info(f"ImapReplyAgent: Reply from {from_address_email} linked to Lead {lead_id}, Campaign {campaign_id} via Message-ID.")
                else:
                    logger.debug(f"ImapReplyAgent: Could not link by Message-ID. Trying to link by From: {from_address_email}")
                    with db_ops.SessionLocal() as db_session:
                        potential_lead = db_ops.get_lead_by_email(db_session, from_address_email, organization_id)
                        if potential_lead:
                            lead_id = potential_lead.get("id")
                            lead_name_for_prompt = potential_lead.get("name", lead_name_for_prompt)
                            # Get their most recent active campaign status
                            status_rec = db_ops.get_most_recent_active_lead_campaign_status(db_session, lead_id, organization_id) # New DB function needed
                            if status_rec: # Ensure they are in an active sequence
                                campaign_id = status_rec.get("campaign_id")
                                lcs_id = status_rec.get("id")
                                logger.info(f"ImapReplyAgent: Reply from {from_address_email} linked to Lead {lead_id}, Campaign {campaign_id} (LCS ID: {lcs_id}) via From address.")
                            else:
                                logger.info(f"ImapReplyAgent: Lead {lead_id} (from {from_address_email}) found, but no active campaign status. Storing reply unlinked or skipping.")
                                # Decide if you store these or just mark as seen
                                # For now, let's store it if lead_id is known, but campaign/lcs might be None
                        else:
                            logger.info(f"ImapReplyAgent: Could not link reply from {from_address_email} to any known lead for org {organization_id}.")
                            # Mark as seen and skip if cannot link to a lead
                            imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                            continue
                
                # Skip further processing if essential linking failed (e.g., no lead_id)
                if not lead_id: # Or campaign_id, lcs_id depending on strictness
                    logger.warning(f"ImapReplyAgent: Essential linking info (lead_id) missing for reply from {from_address_email}. Skipping classification.")
                    imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                    continue

                cleaned_body = self._get_cleaned_email_body_text(email_message)
                if not cleaned_body.strip():
                    logger.info(f"ImapReplyAgent: Reply from {from_address_email} (Lead {lead_id}) has empty cleaned body. Storing as 'empty_reply'.")
                    # Store this as a specific type of reply or skip classification
                    with db_ops.SessionLocal() as db_session:
                        db_ops.store_email_reply(db_session, { # Assuming store_email_reply takes a session
                            "message_id_header": message_id_header,
                            "original_outgoing_email_id": outgoing_log_entry.get("id") if outgoing_log_entry else None,
                            "lead_campaign_status_id": lcs_id, # Can be None if not linked to active campaign
                            "organization_id": organization_id,
                            "lead_id": lead_id,
                            "campaign_id": campaign_id, # Can be None
                            "received_at": received_at_dt,
                            "from_email": from_address_email,
                            "reply_subject": reply_subject,
                            "raw_body_text": raw_email_bytes.decode('utf-8', 'replace'), # Store raw
                            "cleaned_reply_text": "",
                            "ai_classification": "EMPTY_REPLY", # Special category
                            "is_actioned_by_user": True # Auto-actioned as it's empty
                        })
                    imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                    continue

                classification_result = None
                if self.reply_classifier:
                    try:
                        classification_result = self.reply_classifier.classify_text(
                            text_to_classify=cleaned_body,
                            lead_name=lead_name_for_prompt,
                            # You might pass campaign context or offering details here if your classifier uses them
                        )
                    except Exception as class_e:
                        logger.error(f"ImapReplyAgent: Error during reply classification for Lead {lead_id}: {class_e}", exc_info=True)
                else:
                    logger.warning("ImapReplyAgent: ReplyClassifierAgent not available. Skipping classification.")


                # Store the reply and update lead status
                with db_ops.SessionLocal() as db_session:
                    reply_data_to_store = {
                        "message_id_header": message_id_header,
                        "original_outgoing_email_id": outgoing_log_entry.get("id") if outgoing_log_entry else None,
                        "lead_campaign_status_id": lcs_id, # Important: can be None if not linked to active campaign
                        "organization_id": organization_id,
                        "lead_id": lead_id,
                        "campaign_id": campaign_id, # Can be None
                        "received_at": received_at_dt,
                        "from_email": from_address_email,
                        "reply_subject": reply_subject,
                        "raw_body_text": raw_email_bytes.decode('utf-8', 'replace'), # Store raw
                        "cleaned_reply_text": cleaned_body,
                        "ai_classification": classification_result.get("category") if classification_result else "CLASSIFICATION_FAILED",
                        "ai_summary": classification_result.get("summary") if classification_result else None,
                        "ai_extracted_entities": classification_result.get("extracted_info") if classification_result else None,
                        "is_actioned_by_user": False # Default unless auto-actioned (like empty reply)
                    }
                    stored_reply = db_ops.store_email_reply(db_session, reply_data_to_store) # Pass session

                    if stored_reply and lcs_id and classification_result: # Only update LCS if linked and classified
                        logger.info(f"ImapReplyAgent: Stored reply ID {stored_reply['id']} for Lead {lead_id} with AI class '{classification_result.get('category')}'")
                        
                        status_updates: Dict[str, Any] = {
                            "last_response_type": classification_result.get("category"),
                            "last_response_at": received_at_dt,
                        }
                        ai_cat = classification_result.get("category", "").upper() # Standardize category
                        
                        # Define your status update logic based on categories
                        if ai_cat in ["POSITIVE_MEETING_INTEREST", "POSITIVE_GENERAL_INTEREST", "QUESTION_PRODUCT_SERVICE", "QUESTION_OBJECTION"]:
                            status_updates["status"] = "positive_reply_ai_flagged"
                            status_updates["next_email_due_at"] = None  # Pause sequence
                        elif ai_cat == "NEGATIVE_UNSUBSCRIBE":
                            status_updates["status"] = "unsubscribed_ai_flagged" # Or directly 'unsubscribed'
                            status_updates["next_email_due_at"] = None
                            # Optionally mark lead.is_unsubscribed = True globally
                            # db_ops.update_lead_field(db_session, lead_id, organization_id, {"is_unsubscribed": True})
                        elif ai_cat in ["NEGATIVE_NOT_INTERESTED", "NEGATIVE_WRONG_PERSON"]:
                            status_updates["status"] = "negative_reply_ai_flagged"
                            status_updates["next_email_due_at"] = None
                        # Add cases for "OUT_OF_OFFICE", "NEUTRAL_REPLY" etc. if needed
                        
                        if status_updates.get("status"): # Only update if status mapping exists
                            db_ops.update_lead_campaign_status_direct(db_session, lcs_id, status_updates) # Pass session
                            logger.info(f"ImapReplyAgent: Updated LCS ID {lcs_id} for Lead {lead_id} to status '{status_updates['status']}'")
                    elif stored_reply:
                        logger.info(f"ImapReplyAgent: Stored reply ID {stored_reply['id']} for Lead {lead_id} (LCS ID: {lcs_id}, Classification: {classification_result is not None}).")
                    else:
                        logger.error(f"ImapReplyAgent: Failed to store processed reply from {from_address_email} for Lead {lead_id}.")
                
                # Mark email as seen in IMAP server
                imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                logger.debug(f"ImapReplyAgent: Marked email UID {email_uid_str} as Seen for Org ID {organization_id}.")

            # After processing all UIDs in this batch, update last_processed_uid for the org
            if new_max_uid_processed_this_cycle > int(last_processed_uid or 0):
                with db_ops.SessionLocal() as db_session:
                    db_ops.update_organization_email_settings_field( # Pass session
                        db_session,
                        organization_id, 
                        {"last_imap_poll_uid": new_max_uid_processed_this_cycle}
                    )
                logger.info(f"ImapReplyAgent: Updated last_imap_poll_uid for Org ID {organization_id} to {new_max_uid_processed_this_cycle}.")

        except imaplib.IMAP4.error as e_imap:
            logger.error(f"ImapReplyAgent: IMAP4 error for Org ID {organization_id} ({imap_user}): {e_imap}", exc_info=True)
        except Exception as e_main:
            logger.error(f"ImapReplyAgent: General error processing inbox for Org ID {organization_id}: {e_main}", exc_info=True)
        finally:
            if imap_conn:
                try:
                    imap_conn.close()
                except Exception as close_err:
                    logger.debug(f"ImapReplyAgent: Error during IMAP close for Org ID {organization_id}: {close_err}")
                try:
                    imap_conn.logout()
                except Exception as logout_err:
                    logger.debug(f"ImapReplyAgent: Error during IMAP logout for Org ID {organization_id}: {logout_err}")
                logger.debug(f"ImapReplyAgent: IMAP Connection actions (close/logout) performed for Org ID {organization_id}")

    def trigger_imap_polling_for_all_orgs(self):
        logger.info("ImapReplyAgent: Starting polling cycle for all configured organizations.")
        
        # This DB call needs to be within a session context if SessionLocal is used
        organizations_to_poll = []
        try:
            with db_ops.SessionLocal() as db_session: # Create a session
                organizations_to_poll = db_ops.get_organizations_with_imap_enabled(db_session)
        except Exception as e:
            logger.error(f"ImapReplyAgent: Failed to get organizations for IMAP polling: {e}", exc_info=True)
            return
        
        if not organizations_to_poll:
            logger.info("ImapReplyAgent: No organizations found with IMAP reply detection enabled and configured.")
            return

        for org_settings_dict in organizations_to_poll:
            # Ensure 'id' or 'organization_id' is consistently used for the organization's primary key
            org_id = org_settings_dict.get("id") or org_settings_dict.get("organization_id")
            
            if org_id and org_settings_dict.get('imap_is_configured'): # Also check if it's configured
                self._process_single_inbox(org_id, org_settings_dict)
            else:
                logger.warning(f"ImapReplyAgent: Skipping org due to missing ID or IMAP not configured. Data: {org_settings_dict}")
        logger.info("ImapReplyAgent: Finished polling cycle for all organizations.")

    def run(self): # Method that APScheduler will call
        """Main entry point for the scheduled job."""
        logger.info("ImapReplyAgent: Scheduled run triggered.")
        self.trigger_imap_polling_for_all_orgs()


# Example usage for APScheduler (in your main.py or scheduler_setup.py):
#
# from app.agents.imap_reply_agent import ImapReplyAgent
# from apscheduler.schedulers.asyncio import AsyncIOScheduler # Or BackgroundScheduler
# from app.db.database import SessionLocal # Pass the session factory
#
# scheduler = AsyncIOScheduler(timezone="UTC")
#
# # Instantiate agent (outside the job function if it holds state or connections you want to reuse,
# # but be mindful of thread/process safety if it does. For IMAP, new connections per poll cycle are often safer)
# # For this agent, since it creates connections inside _process_single_inbox, it's okay.
# imap_agent_instance = ImapReplyAgent()
#
# # Define the job function that APScheduler will execute
# async def scheduled_imap_poll_job():
#     logger.info("APScheduler: Executing scheduled IMAP poll job.")
#     try:
#         # If ImapReplyAgent.run() is synchronous (blocking), run it in a thread pool
#         # if your main app/scheduler is asyncio-based.
#         # loop = asyncio.get_event_loop()
#         # await loop.run_in_executor(None, imap_agent_instance.run)
#         imap_agent_instance.run() # If it's okay to run synchronously in scheduler's thread/process
#     except Exception as e:
#         logger.error(f"APScheduler: Error in scheduled_imap_poll_job: {e}", exc_info=True)
#
# # To add the job in your main app startup:
# # scheduler.add_job(scheduled_imap_poll_job, 'interval', minutes=15, id='imap_poll_job')
# # scheduler.start()
