# app/agents/imap_reply_agent.py

import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
from typing import List, Optional, Any # Removed Dict for org_settings_obj
from datetime import datetime, timezone
from sqlalchemy.orm import Session # For type hinting

from app.utils.logger import logger
from app.db import database as db_ops # Using an alias for clarity
from app.db.database import get_db # To get a database session
from app.agents.reply_classifier_agent import ReplyClassifierAgent
from app.db import models # Import your ORM models for type hinting

# (Keep your existing logger setup if not using app.utils.logger)

class ImapReplyAgent:
    def __init__(self):
        logger.info("ImapReplyAgent: Initializing...")
        try:
            self.reply_classifier = ReplyClassifierAgent()
            logger.info("ImapReplyAgent: ReplyClassifierAgent instantiated successfully.")
        except Exception as e:
            logger.error(f"ImapReplyAgent: Failed to instantiate ReplyClassifierAgent: {e}", exc_info=True)
            self.reply_classifier = None

    # (Keep your _decode_email_header and _get_cleaned_email_body_text methods as they are)
    def _decode_email_header(self, header_value: Any) -> str:
        if not header_value:
            return ""
        if isinstance(header_value, list):
            header_value = header_value[0] if header_value else ""
        if isinstance(header_value, email.header.Header):
            header_value = str(header_value)
        elif not isinstance(header_value, str):
            try:
                header_value = str(header_value)
            except:
                logger.warning(f"ImapReplyAgent: Could not convert header value to string: {type(header_value)}")
                return ""

        decoded_parts = []
        try:
            for part_bytes, charset in decode_header(header_value):
                if isinstance(part_bytes, bytes):
                    try:
                        decoded_parts.append(part_bytes.decode(charset or 'utf-8', 'replace'))
                    except (UnicodeDecodeError, LookupError):
                        decoded_parts.append(part_bytes.decode('latin1', 'replace'))
                else:
                    decoded_parts.append(part_bytes)
        except Exception as e:
            logger.error(f"ImapReplyAgent: Error decoding header part: {e}. Header: '{header_value[:100]}...'")
            return header_value
        return "".join(decoded_parts)

    def _get_cleaned_email_body_text(self, msg: email.message.Message) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition.lower():
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        part_body = payload.decode(charset, 'replace')
                        cleaned_part = re.split(r'\n\s*(?:On|El|Le)\s+.*\s+(?:wrote|écrit|escribió):|\n\s*--\s*\n?>', part_body, 1)[0]
                        body = cleaned_part.strip()
                        if body: break
                    except Exception as e:
                        logger.warning(f"ImapReplyAgent: Error decoding/cleaning multipart text part: {e}")
        else:
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
        if not body and msg.is_multipart(): # Fallback
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")).lower():
                    try:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, 'replace').strip()
                        if body: break
                    except Exception: continue
        return body


    def _process_single_inbox(self, db: Session, org_settings_obj: models.OrganizationEmailSettings):
        # org_settings_obj is now an ORM object, not a dict
        # The db session is passed in
        organization_id = org_settings_obj.organization_id
        logger.info(f"ImapReplyAgent: Processing inbox for Org ID: {organization_id}, User: {org_settings_obj.imap_username}")

        imap_host = org_settings_obj.imap_host
        default_port = 993 if org_settings_obj.imap_use_ssl else 143
        imap_port = org_settings_obj.imap_port if org_settings_obj.imap_port is not None else default_port
        imap_user = org_settings_obj.imap_username

        # imap_password should be a decrypted transient attribute on org_settings_obj
        # set by get_organizations_with_imap_enabled
        imap_password = getattr(org_settings_obj, 'imap_password', None) # Access the decrypted password

        use_ssl = org_settings_obj.imap_use_ssl
        last_processed_uid_str = org_settings_obj.last_imap_poll_uid # String or None

        if not all([imap_host, imap_user, imap_password]):
            logger.error(f"ImapReplyAgent: Incomplete IMAP credentials for Org ID {organization_id}. Skipping. Host: {imap_host}, User: {imap_user}, PassSet: {imap_password is not None}")
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
            if last_processed_uid_str and last_processed_uid_str.isdigit():
                # More robust: Fetch only UIDs greater than the last one
                # Consider UIDVALIDITY checks for full robustness (omitted for brevity here)
                search_criteria = f'(UID {int(last_processed_uid_str) + 1}:*)'
                logger.info(f"ImapReplyAgent: Searching with UID criteria: {search_criteria}")


            logger.debug(f"ImapReplyAgent: Searching INBOX with criteria: {search_criteria} for Org ID {organization_id}")
            status, message_uids_bytes_list = imap_conn.uid('search', None, search_criteria)
            if status != 'OK':
                logger.error(f"ImapReplyAgent: IMAP search failed for Org ID {organization_id}. Response: {message_uids_bytes_list}")
                return

            email_uids_to_fetch_str = message_uids_bytes_list[0].decode().split()
            if not email_uids_to_fetch_str:
                logger.info(f"ImapReplyAgent: No new emails matching criteria for Org ID {organization_id} using '{search_criteria}'.")
                # If UID search returned nothing, but UNSEEN might have older unseen, consider a fallback UNSEEN search
                # For now, we'll proceed if the current criteria finds nothing.
                return
            logger.info(f"ImapReplyAgent: Found {len(email_uids_to_fetch_str)} email(s) for Org ID {organization_id} using '{search_criteria}'.")

            new_max_uid_processed_this_cycle = int(last_processed_uid_str or 0)

            for email_uid_str in email_uids_to_fetch_str:
                email_uid_bytes = email_uid_str.encode()
                current_email_uid_int = int(email_uid_str)
                
                # If using UID-based search, we assume all fetched UIDs are "new" relative to last_processed_uid_str.
                # If using UNSEEN, this check is more relevant to avoid reprocessing if an email was marked SEEN by another client.
                if last_processed_uid_str and current_email_uid_int <= int(last_processed_uid_str) and search_criteria == '(UNSEEN)':
                    logger.debug(f"ImapReplyAgent: Skipping UID {email_uid_str} as it's less than or equal to last processed UID {last_processed_uid_str} during UNSEEN scan.")
                    imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)') # Mark it seen anyway
                    continue

                new_max_uid_processed_this_cycle = max(new_max_uid_processed_this_cycle, current_email_uid_int)

                logger.debug(f"ImapReplyAgent: Fetching email UID {email_uid_str} for Org ID {organization_id}")
                status, msg_data = imap_conn.uid('fetch', email_uid_bytes, '(RFC822)')
                # ... (rest of your email parsing logic - keep it) ...
                if status != 'OK' or not msg_data or msg_data[0] is None:
                    logger.error(f"ImapReplyAgent: Failed to fetch email UID {email_uid_str} for Org ID {organization_id}")
                    continue
                raw_email_bytes = None
                if isinstance(msg_data[0], tuple) and len(msg_data[0]) == 2 and isinstance(msg_data[0][1], bytes):
                    raw_email_bytes = msg_data[0][1]
                elif isinstance(msg_data[0], bytes):
                    raw_email_bytes = msg_data[0]
                if not raw_email_bytes:
                    logger.error(f"ImapReplyAgent: Could not extract raw email bytes for UID {email_uid_str}")
                    continue

                email_message = email.message_from_bytes(raw_email_bytes)
                message_id_header = self._decode_email_header(email_message.get("Message-ID"))
                in_reply_to_header = self._decode_email_header(email_message.get("In-Reply-To"))
                references_header = self._decode_email_header(email_message.get("References"))
                from_address_full = self._decode_email_header(email_message.get("From"))
                from_address_email_match = re.search(r'<([^>]+)>', from_address_full)
                from_address_email = from_address_email_match.group(1).strip() if from_address_email_match else from_address_full.strip()
                reply_subject = self._decode_email_header(email_message.get("Subject"))
                date_str = email_message.get("Date")
                received_at_dt = parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
                if received_at_dt.tzinfo is None:
                    received_at_dt = received_at_dt.replace(tzinfo=timezone.utc)
                else:
                    received_at_dt = received_at_dt.astimezone(timezone.utc)

                original_message_id_to_find = None
                if in_reply_to_header:
                    original_message_id_to_find = in_reply_to_header.strip("<> ")
                elif references_header:
                    ref_ids = references_header.strip().split()
                    if ref_ids: original_message_id_to_find = ref_ids[-1].strip("<> ")
                
                outgoing_log_entry_orm: Optional[models.OutgoingEmailLog] = None # Changed to ORM type
                if original_message_id_to_find:
                    logger.debug(f"ImapReplyAgent: Attempting to link reply via Message-ID: {original_message_id_to_find}")
                    # Use the passed-in db session
                    outgoing_log_entry_orm = db_ops.get_outgoing_email_log_by_message_id(
                        db, organization_id, original_message_id_to_find
                    )

                lead_id, campaign_id, lcs_id = None, None, None
                lead_name_for_prompt = "Valued Prospect"

                if outgoing_log_entry_orm:
                    lead_id = outgoing_log_entry_orm.lead_id
                    campaign_id = outgoing_log_entry_orm.campaign_id
                    lcs_id = outgoing_log_entry_orm.lead_campaign_status_id # Directly from log if available
                    
                    if lead_id and not lcs_id: # If log doesn't have LCS ID, try to get it
                        lcs_record_orm = db_ops.get_lead_campaign_status(db, lead_id, organization_id) # Use current session
                        if lcs_record_orm: lcs_id = lcs_record_orm.id

                    if lead_id:
                        lead_details_orm = db_ops.get_lead_by_id(db, lead_id, organization_id) # Use current session
                        if lead_details_orm: lead_name_for_prompt = lead_details_orm.name or lead_name_for_prompt
                    logger.info(f"ImapReplyAgent: Reply from {from_address_email} linked to Lead {lead_id}, Campaign {campaign_id} via Message-ID.")
                else: # Try to link by From address
                    logger.debug(f"ImapReplyAgent: Could not link by Message-ID. Trying to link by From: {from_address_email}")
                    potential_lead_orm = db_ops.get_lead_by_email(db, from_address_email, organization_id) # Use current session
                    if potential_lead_orm:
                        lead_id = potential_lead_orm.id
                        lead_name_for_prompt = potential_lead_orm.name or lead_name_for_prompt
                        # Get their most recent *active* campaign status (or any status for context)
                        # This might need a more specific DB function if you only want "active"
                        status_rec_orm = db_ops.get_lead_campaign_status(db, lead_id, organization_id) # Use current session
                        if status_rec_orm:
                            campaign_id = status_rec_orm.campaign_id
                            lcs_id = status_rec_orm.id
                            logger.info(f"ImapReplyAgent: Reply from {from_address_email} linked to Lead {lead_id}, Campaign {campaign_id} (LCS ID: {lcs_id}) via From address.")
                        else:
                            logger.info(f"ImapReplyAgent: Lead {lead_id} (from {from_address_email}) found, but no campaign status record. Storing reply linked to lead only.")
                    else:
                        logger.info(f"ImapReplyAgent: Could not link reply from {from_address_email} to any known lead for org {organization_id}.")
                        imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                        continue
                
                if not lead_id: # If still no lead_id, cannot proceed
                    logger.warning(f"ImapReplyAgent: Essential linking info (lead_id) missing for reply from {from_address_email}. Skipping classification.")
                    imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                    continue

                cleaned_body = self._get_cleaned_email_body_text(email_message)
                # ... (rest of your classification and storing logic) ...
                # Ensure all db_ops calls use the passed 'db' session.
                # Example for storing reply:
                if not cleaned_body.strip(): # Handle empty reply
                    logger.info(f"ImapReplyAgent: Reply from {from_address_email} (Lead {lead_id}) has empty cleaned body. Storing as 'empty_reply'.")
                    db_ops.store_email_reply(db, { # Use passed db session
                        "message_id_header": message_id_header,
                        "outgoing_email_log_id": outgoing_log_entry_orm.id if outgoing_log_entry_orm else None,
                        "lead_campaign_status_id": lcs_id,
                        "organization_id": organization_id,
                        "lead_id": lead_id,
                        "campaign_id": campaign_id,
                        "received_at": received_at_dt,
                        "from_email": from_address_email,
                        "reply_subject": reply_subject,
                        "raw_body_text": raw_email_bytes.decode('utf-8', 'replace'),
                        "cleaned_reply_text": "",
                        "ai_classification": "EMPTY_REPLY",
                        "is_actioned_by_user": True
                    })
                    imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                    continue

                classification_result = None
                if self.reply_classifier:
                    try:
                        classification_result = self.reply_classifier.classify_text(cleaned_body, lead_name_for_prompt)
                    except Exception as class_e: logger.error(f"ImapReplyAgent: Error during reply classification for Lead {lead_id}: {class_e}", exc_info=True)
                else: logger.warning("ImapReplyAgent: ReplyClassifierAgent not available.")

                reply_data_to_store = {
                    "message_id_header": message_id_header,
                    "outgoing_email_log_id": outgoing_log_entry_orm.id if outgoing_log_entry_orm else None,
                    "lead_campaign_status_id": lcs_id,
                    "organization_id": organization_id,
                    "lead_id": lead_id,
                    "campaign_id": campaign_id,
                    "received_at": received_at_dt,
                    "from_email": from_address_email,
                    "reply_subject": reply_subject,
                    "raw_body_text": raw_email_bytes.decode('utf-8', 'replace'),
                    "cleaned_reply_text": cleaned_body,
                    "ai_classification": classification_result.get("category") if classification_result else "CLASSIFICATION_FAILED",
                    "ai_summary": classification_result.get("summary") if classification_result else None,
                    "ai_extracted_entities": classification_result.get("extracted_info") if classification_result else None,
                    "is_actioned_by_user": False
                }
                stored_reply_orm = db_ops.store_email_reply(db, reply_data_to_store) # Use passed db session

                if stored_reply_orm and lcs_id and classification_result:
                    logger.info(f"ImapReplyAgent: Stored reply ID {stored_reply_orm.id} for Lead {lead_id} with AI class '{classification_result.get('category')}'")
                    status_updates: Dict[str, Any] = {
                        "last_response_type": classification_result.get("category"),
                        "last_response_at": received_at_dt,
                    }
                    ai_cat = classification_result.get("category", "").upper()
                    # Simplified status update logic (expand as needed)
                    if "POSITIVE" in ai_cat or "QUESTION" in ai_cat: status_updates["status"] = "positive_reply_ai_flagged"; status_updates["next_email_due_at"] = None
                    elif "UNSUBSCRIBE" in ai_cat: status_updates["status"] = "unsubscribed_ai_flagged"; status_updates["next_email_due_at"] = None
                    elif "NEGATIVE" in ai_cat: status_updates["status"] = "negative_reply_ai_flagged"; status_updates["next_email_due_at"] = None
                    
                    if status_updates.get("status"):
                        db_ops.update_lead_campaign_status(db, lcs_id, organization_id, status_updates) # Use passed db session
                        logger.info(f"ImapReplyAgent: Updated LCS ID {lcs_id} for Lead {lead_id} to status '{status_updates['status']}'")
                elif stored_reply_orm:
                    logger.info(f"ImapReplyAgent: Stored reply ID {stored_reply_orm.id} for Lead {lead_id} (LCS ID: {lcs_id}, Classification: {classification_result is not None}).")
                else:
                    logger.error(f"ImapReplyAgent: Failed to store processed reply from {from_address_email} for Lead {lead_id}.")

                imap_conn.uid('store', email_uid_bytes, '+FLAGS', '(\\Seen)')
                logger.debug(f"ImapReplyAgent: Marked email UID {email_uid_str} as Seen for Org ID {organization_id}.")


            # After processing all UIDs in this batch, update last_processed_uid for the org
            # Only update if we actually processed something new or the max UID changed
            if new_max_uid_processed_this_cycle > int(last_processed_uid_str or 0):
                db_ops.update_organization_email_settings_field( # Use passed db session
                    db,
                    organization_id,
                    {"last_imap_poll_uid": str(new_max_uid_processed_this_cycle), "last_imap_poll_timestamp": datetime.now(timezone.utc)}
                )
                logger.info(f"ImapReplyAgent: Updated last_imap_poll_uid for Org ID {organization_id} to {new_max_uid_processed_this_cycle}.")

        except imaplib.IMAP4.error as e_imap:
            logger.error(f"ImapReplyAgent: IMAP4 error for Org ID {organization_id} ({imap_user}): {e_imap}", exc_info=True)
        except Exception as e_main:
            logger.error(f"ImapReplyAgent: General error processing inbox for Org ID {organization_id}: {e_main}", exc_info=True)
        finally:
            if imap_conn:
                try: imap_conn.close()
                except: pass
                try: imap_conn.logout()
                except: pass
                logger.debug(f"ImapReplyAgent: IMAP Connection actions (close/logout) performed for Org ID {organization_id}")

    def trigger_imap_polling_for_all_orgs(self):
        logger.info("ImapReplyAgent: Starting polling cycle for all configured organizations.")
        
        db_session: Session = next(get_db()) # <--- GET ONE SESSION FOR THE WHOLE POLLING CYCLE
        organizations_to_poll: List[models.OrganizationEmailSettings] = []
        try:
            # This function now takes 'db' and returns ORM objects with decrypted imap_password
            organizations_to_poll = db_ops.get_organizations_with_imap_enabled(db_session) # Pass the session

            if not organizations_to_poll:
                logger.info("ImapReplyAgent: No organizations found with IMAP reply detection enabled and configured.")
                return

            for org_settings_orm_obj in organizations_to_poll: # This is now an ORM object
                # org_id is org_settings_orm_obj.organization_id
                # imap_is_configured is org_settings_orm_obj.is_configured (or a specific imap_is_configured field if you add one)
                if org_settings_orm_obj.organization_id and org_settings_orm_obj.is_configured and org_settings_orm_obj.enable_reply_detection:
                    # Pass the SAME db_session and the ORM object to _process_single_inbox
                    self._process_single_inbox(db_session, org_settings_orm_obj)
                else:
                    logger.warning(f"ImapReplyAgent: Skipping org ID {org_settings_orm_obj.organization_id} due to missing ID or IMAP not configured/enabled.")
            
        except Exception as e:
            logger.error(f"ImapReplyAgent: Failed to get/process organizations for IMAP polling: {e}", exc_info=True)
        finally:
            db_session.close() # <--- CLOSE THE SESSION AT THE END OF THE CYCLE
            
        logger.info("ImapReplyAgent: Finished polling cycle for all organizations.")

    def run(self): # Method that APScheduler will call
        logger.info("ImapReplyAgent: Scheduled run triggered.")
        self.trigger_imap_polling_for_all_orgs()
#
# # To add the job in your main app startup:
# # scheduler.add_job(scheduled_imap_poll_job, 'interval', minutes=15, id='imap_poll_job')
# # scheduler.start()
