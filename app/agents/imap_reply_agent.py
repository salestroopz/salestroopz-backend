# app/agents/imap_reply_agent.py

import imaplib
import email # For parsing email messages
from email.header import decode_header
from email.utils import parsedate_to_datetime # For parsing date headers
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone

from app.db import database
from app.utils.logger import logger
from app.utils.config import settings # If needed for IMAP settings overrides, etc.
from app.agents.reply_classifier_agent import ReplyClassifierAgent # <--- IMPORT YOUR EXISTING AGENT

class ImapReplyAgent:
    def __init__(self):
        logger.info("ImapReplyAgent initialized.")
        try:
            # Instantiate your existing ReplyClassifierAgent
            self.reply_classifier = ReplyClassifierAgent()
            logger.info("ReplyClassifierAgent instantiated within ImapReplyAgent.")
        except Exception as e:
            logger.error(f"ImapReplyAgent: Failed to instantiate ReplyClassifierAgent: {e}", exc_info=True)
            self.reply_classifier = None # Handle gracefully if it fails

    def _decode_email_header(self, header_value: Any) -> str: # Header can be list or str
        if not header_value:
            return ""
        
        if isinstance(header_value, list): # Some headers can be lists
            header_value = header_value[0] # Take the first one, usually sufficient

        if isinstance(header_value, email.header.Header):
            header_value = str(header_value) # Convert Header object to string

        decoded_parts = []
        for part_bytes, charset in decode_header(str(header_value)): # Ensure it's a string
            if isinstance(part_bytes, bytes):
                try:
                    decoded_parts.append(part_bytes.decode(charset or 'utf-8', 'ignore'))
                except (UnicodeDecodeError, LookupError):
                    decoded_parts.append(part_bytes.decode('latin1', 'ignore')) 
            else: 
                decoded_parts.append(part_bytes)
        return "".join(decoded_parts)

    def _get_cleaned_email_body_text(self, msg: email.message.Message) -> str:
        """
        Extracts and cleans the plain text body from an email.message.Message object.
        Focuses on getting the latest reply, stripping quoted text and signatures.
        """
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition.lower():
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        part_body = payload.decode(charset, 'ignore')
                        # Simple reply cleaning: take text before common reply headers or typical signature dashes
                        # More robust: use a library like 'email_reply_parser' or 'talon'
                        # For now, a basic attempt:
                        cleaned_part = re.split(r'\n\s*On .*wrote:|\n\s*--\s*\n?>', part_body, 1)[0]
                        body = cleaned_part.strip() 
                        if body: # Prefer the first non-empty plain text part that seems like a reply
                            break 
                    except Exception as e:
                        logger.warning(f"IMAP: Error decoding/cleaning text part: {e}")
        else: 
            content_type = msg.get_content_type()
            if content_type == "text/plain":
                try:
                    payload = msg.get_payload(decode=True)
                    charset = msg.get_content_charset() or 'utf-8'
                    part_body = payload.decode(charset, 'ignore')
                    cleaned_part = re.split(r'\n\s*On .*wrote:|\n\s*--\s*\n?>', part_body, 1)[0]
                    body = cleaned_part.strip()
                except Exception as e:
                    logger.warning(f"IMAP: Error decoding/cleaning non-multipart text: {e}")
        
        if not body and msg.is_multipart(): # Fallback if no clean plain text, try to find any text
             for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, 'ignore').strip()
                        if body: break
                    except: continue
        return body

    def _process_single_inbox(self, organization_id: int, imap_settings: Dict[str, Any]):
        logger.info(f"IMAP: Processing inbox for org_id: {organization_id} - User: {imap_settings.get('imap_username')}")
        
        imap_host = imap_settings.get('imap_host')
        imap_port = int(imap_settings.get('imap_port', 993 if imap_settings.get('imap_use_ssl', True) else 143))
        imap_user = imap_settings.get('imap_username')
        imap_password = database._decrypt_data(imap_settings.get('encrypted_imap_password')) # Assumes decryption
        use_ssl = imap_settings.get('imap_use_ssl', True)
        last_processed_uid = imap_settings.get('last_imap_poll_uid') # Fetch this from DB

        if not all([imap_host, imap_user, imap_password]):
            logger.error(f"IMAP: Incomplete IMAP credentials for org {organization_id}. Skipping.")
            return

        imap_conn: Optional[imaplib.IMAP4_SSL | imaplib.IMAP4] = None
        try:
            if use_ssl:
                imap_conn = imaplib.IMAP4_SSL(imap_host, imap_port)
            else:
                imap_conn = imaplib.IMAP4(imap_host, imap_port)
            
            status, _ = imap_conn.login(imap_user, imap_password)
            if status != 'OK': logger.error(f"IMAP: Login failed for org {organization_id}"); return
            logger.info(f"IMAP: Logged in for org {organization_id}")

            status, _ = imap_conn.select("INBOX", readonly=False) # readonly=False to allow setting \Seen flag
            if status != 'OK': logger.error(f"IMAP: Failed to select INBOX for org {organization_id}"); return

            # Search for emails: UNSEEN or (if using last_processed_uid) UID next_uid:*
            search_criteria = '(UNSEEN)'
            if last_processed_uid:
                # Robust UID searching requires knowing the mailbox's UIDVALIDITY.
                # For simplicity, if UIDs are sequential and increasing:
                # search_criteria = f'(UID {int(last_processed_uid)+1}:*)'
                # However, UNSEEN is often safer for initial implementation if not storing UIDVALIDITY.
                 logger.debug(f"IMAP: Searching for emails with criteria: {search_criteria} (last UID: {last_processed_uid})")
            else:
                 logger.debug(f"IMAP: Searching for emails with criteria: {search_criteria} (no last UID)")


            status, message_uids_bytes = imap_conn.uid('search', None, search_criteria)
            if status != 'OK': logger.error(f"IMAP: Search failed for org {organization_id}"); return

            email_uids_to_fetch = message_uids_bytes[0].split()
            if not email_uids_to_fetch: logger.info(f"IMAP: No new emails found for org {organization_id}."); return
            logger.info(f"IMAP: Found {len(email_uids_to_fetch)} new email(s) for org {organization_id}.")
            
            new_max_uid_processed_this_cycle = last_processed_uid or 0

            for email_uid_bytes in email_uids_to_fetch:
                email_uid_str = email_uid_bytes.decode()
                new_max_uid_processed_this_cycle = max(int(new_max_uid_processed_this_cycle), int(email_uid_str))

                logger.debug(f"IMAP: Fetching email UID {email_uid_str} for org {organization_id}")
                status, msg_data = imap_conn.uid('fetch', email_uid_bytes, '(RFC822)') # BODY[HEADER.FIELDS (In-Reply-To References Message-ID)] BODY[TEXT]
                if status != 'OK' or not msg_data or msg_data[0] is None :
                    logger.error(f"IMAP: Failed to fetch email UID {email_uid_str}"); continue

                raw_email_bytes = msg_data[0][1] # msg_data is [(b'1 (UID 123 RFC822 {size}', email_bytes), b')']
                if not isinstance(raw_email_bytes, bytes): continue

                email_message = email.message_from_bytes(raw_email_bytes)
                
                in_reply_to_header = email_message.get("In-Reply-To")
                references_header = email_message.get("References")
                from_address_full = self._decode_email_header(email_message.get("From"))
                # Extract just email from "Name <email@example.com>"
                from_address_email_match = re.search(r'<([^>]+)>', from_address_full)
                from_address_email = from_address_email_match.group(1) if from_address_email_match else from_address_full.strip()

                reply_subject = self._decode_email_header(email_message.get("Subject"))
                date_str = email_message.get("Date")
                received_at_dt = parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
                if received_at_dt.tzinfo is None: received_at_dt = received_at_dt.replace(tzinfo=timezone.utc)
                else: received_at_dt = received_at_dt.astimezone(timezone.utc)

                # Try to link using In-Reply-To or References
                original_message_id_to_find = None
                if in_reply_to_header:
                    original_message_id_to_find = in_reply_to_header.strip()
                elif references_header:
                    # References can have multiple IDs, usually the last one is the direct parent
                    ref_ids = references_header.strip().split()
                    if ref_ids: original_message_id_to_find = ref_ids[-1].strip()
                
                outgoing_log_entry = None
                if original_message_id_to_find:
                    logger.debug(f"IMAP: Trying to link reply using Message-ID: {original_message_id_to_find}")
                    outgoing_log_entry = database.get_outgoing_email_log_by_message_id(organization_id, original_message_id_to_find)

                lead_id = None
                campaign_id = None
                lcs_id = None # lead_campaign_status_id

                if outgoing_log_entry:
                    lead_id = outgoing_log_entry.get("lead_id")
                    campaign_id = outgoing_log_entry.get("campaign_id")
                    lcs_id = outgoing_log_entry.get("lead_campaign_status_id")
                    logger.info(f"IMAP: Reply linked to Lead {lead_id}, Campaign {campaign_id} via Message-ID.")
                else:
                    # Fallback: Try to link by From address if not linked by Message-ID
                    logger.debug(f"IMAP: Could not link by Message-ID. Trying to link by From: {from_address_email}")
                    potential_lead = database.get_lead_by_email(from_address_email, organization_id)
                    if potential_lead:
                        lead_id = potential_lead.get("id")
                        # Get their active campaign status
                        status_rec = database.get_lead_campaign_status(lead_id, organization_id)
                        if status_rec and status_rec.get("status") in ["active", "error_sending_email"]: # Check if they are in an active sequence
                            campaign_id = status_rec.get("campaign_id")
                            lcs_id = status_rec.get("id")
                            logger.info(f"IMAP: Reply linked to Lead {lead_id}, Campaign {campaign_id} via From address and active status.")
                        else:
                            logger.info(f"IMAP: Lead {lead_id} found by From address but not in an active campaign sequence.")
                            # Decide if you still want to process/store this reply
                            # For now, let's only process if linked to an active campaign status
                            imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)') # Mark as seen
                            continue 
                    else:
                        logger.info(f"IMAP: Could not link reply from {from_address_email} to any known lead for org {organization_id}.")
                        imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)') # Mark as seen
                        continue 
                
                # Ensure we have essential IDs to proceed with classification and DB storage
                if not all([lead_id, campaign_id, lcs_id]):
                    logger.warning(f"IMAP: Missing lead_id, campaign_id, or lcs_id after linking attempts for reply from {from_address_email}. Skipping further processing.")
                    imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                    continue

                cleaned_body = self._get_cleaned_email_body_text(email_message)
                if not cleaned_body:
                    logger.info(f"IMAP: Reply from {from_address_email} (Lead {lead_id}) has empty cleaned body. Skipping classification.")
                    # Optionally store it as an empty reply or with a specific category
                    imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                    continue

                # --- Integrate Your Existing ReplyClassifierAgent ---
                classification_result = None
                if self.reply_classifier:
                    lead_name_for_prompt = database.get_lead_by_id(lead_id, organization_id).get("name") # Fetch lead name for better prompt
                    classification_result = self.reply_classifier.classify_text(cleaned_body, lead_name=lead_name_for_prompt) # Use your agent's method name

                if classification_result:
                    reply_data_to_store = {
                        "outgoing_email_log_id": outgoing_log_entry.get("id") if outgoing_log_entry else None,
                        "lead_campaign_status_id": lcs_id,
                        "organization_id": organization_id,
                        "lead_id": lead_id,
                        "campaign_id": campaign_id,
                        "received_at": received_at_dt,
                        "from_email": from_address_email,
                        "reply_subject": reply_subject,
                        "raw_body_text": raw_email_bytes.decode('utf-8', 'ignore'), # Store raw for reference
                        "cleaned_reply_text": cleaned_body,
                        "ai_classification": classification_result.get("category"),
                        "ai_summary": classification_result.get("summary"),
                        "ai_extracted_entities": classification_result.get("extracted_info"),
                        "is_actioned_by_user": False # Default
                    }
                    stored_reply = database.store_email_reply(reply_data_to_store)
                    if stored_reply:
                        logger.info(f"IMAP: Stored reply ID {stored_reply['id']} with AI classification '{classification_result.get('category')}'")
                        # Now update lead_campaign_status based on classification
                        status_updates: Dict[str, Any] = {
                            "last_response_type": classification_result.get("category"),
                            "last_response_at": received_at_dt,
                            # "user_notes": classification_result.get("summary") # Or append to existing
                        }
                        ai_cat = classification_result.get("category")
                        if ai_cat in ["POSITIVE_MEETING_INTEREST", "POSITIVE_GENERAL_INTEREST", "QUESTION_PRODUCT_SERVICE", "QUESTION_OBJECTION"]:
                            status_updates["status"] = "positive_reply_ai_flagged" # Or more specific like "question_ai_flagged"
                            status_updates["next_email_due_at"] = None # Pause sequence
                        elif ai_cat == "NEGATIVE_UNSUBSCRIBE":
                            status_updates["status"] = "unsubscribed_ai_flagged"
                            status_updates["next_email_due_at"] = None
                        elif ai_cat == "NEGATIVE_NOT_INTERESTED" or ai_cat == "NEGATIVE_WRONG_PERSON":
                             status_updates["status"] = "negative_reply_ai_flagged"
                             status_updates["next_email_due_at"] = None
                        # For OOO or NEUTRAL, you might choose not to change status or next_email_due_at,
                        # or move to a "neutral_reply_received" status for review.
                        
                        if status_updates.get("status"): # Only update if status needs changing
                            database.update_lead_campaign_status(status_id=lcs_id, organization_id=organization_id, updates=status_updates)
                    else:
                        logger.error(f"IMAP: Failed to store processed reply from {from_address_email} for lead {lead_id}.")
                else:
                    logger.warning(f"IMAP: Reply classification failed or returned None for reply from {from_address_email} (Lead {lead_id}).")
                
                # Mark as seen
                imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')

            # After processing all UIDs in this batch, update last_processed_uid for the org
            if new_max_uid_processed_this_cycle > (last_processed_uid or 0):
                database.update_organization_email_settings_field( # NEW DB function needed
                    organization_id, 
                    {"last_imap_poll_uid": new_max_uid_processed_this_cycle}
                )

        except imaplib.IMAP4.error as e_imap:
            logger.error(f"IMAP: IMAP4 error for org {organization_id} ({imap_user}): {e_imap}", exc_info=True)
        except Exception as e_main:
            logger.error(f"IMAP: General error processing inbox for org {organization_id}: {e_main}", exc_info=True)
        finally:
            if imap_conn:
                try: imap_conn.close()
                except: pass
                try: imap_conn.logout()
                except: pass
                logger.debug(f"IMAP: Connection closed for org {organization_id}")

    def trigger_imap_polling_for_all_orgs(self):
        logger.info("IMAP POLLER AGENT: Starting polling cycle for all configured organizations.")
        organizations_to_poll = database.get_organizations_with_imap_enabled()
        
        if not organizations_to_poll:
            logger.info("IMAP POLLER AGENT: No organizations found with IMAP reply detection enabled and configured.")
            return

        for org_settings_dict in organizations_to_poll:
            org_id = org_settings_dict.get("organization_id") # Or 'id' if that's the key
            if org_id:
                self._process_single_inbox(org_id, org_settings_dict)
            else:
                logger.warning(f"IMAP POLLER AGENT: Found org settings without organization_id: {org_settings_dict}")
        logger.info("IMAP POLLER AGENT: Finished polling cycle for all organizations.")

# To be called by APScheduler in main.py:
# imap_agent = ImapReplyAgent()
# async def scheduled_imap_poll_task():
#     logger.info("SCHEDULER: Triggering ImapReplyAgent cycle.")
#     try:
#         # If _process_single_inbox involves blocking IO (like network calls for IMAP without an async library),
#         # running it in a threadpool executor is good practice if your scheduler is asyncio based.
#         # For simplicity, if it's a separate process/thread from APScheduler, direct call is fine.
#         imap_agent.trigger_imap_polling_for_all_orgs()
#     except Exception as e:
#         logger.error(f"SCHEDULER: Error in scheduled_imap_poll_task: {e}", exc_info=True)
          _process_single_inbox(org_id, org_settings)
       else:
            logger.warning(f"IMAP POLLER: Incomplete IMAP settings for an organization, cannot poll. Data: {org_settings}")
    logger.info("IMAP POLLER: Finished cycle for all organizations.")
