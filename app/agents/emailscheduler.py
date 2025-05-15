# app/agents/emailscheduler.py

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

from app.utils.logger import logger
from app.db import database
from app.db.database import get_db 
from app.utils.email_sender import send_email, EmailSendingResult # Assuming EmailSendingResult is defined here

class EmailSchedulerAgent:
    """
    Agent responsible for periodically checking lead campaign statuses,
    retrieving pre-generated email steps, personalizing, sending emails,
    logging sent emails, and updating lead status.
    """
    def __init__(self):
        logger.info("EmailSchedulerAgent initialized.")

    def _calculate_next_due_at(self, base_time: datetime, delay_days: int) -> datetime:
        """
        Calculates the next due time by adding delay_days to a base_time.
        Ensures the base_time is timezone-aware (UTC).
        """
        if delay_days < 0: 
            delay_days = 0
        
        if base_time.tzinfo is None: # Ensure base_time is UTC
            base_time = base_time.replace(tzinfo=timezone.utc)
            
        return base_time + timedelta(days=delay_days)

    def _personalize_template(self, template: Optional[str], lead_data: dict) -> str:
        """Replaces placeholders in a template string with lead data."""
        if not template: 
            return ""
        
        personalized_content = template
        lead_name = lead_data.get("name", "")
        first_name = lead_name.split(" ")[0] if lead_name else "there"

        placeholders = {
            "{{lead_name}}": lead_name or "there",
            "{{lead_first_name}}": first_name,
            "{{company_name}}": lead_data.get("company", "your company"),
            "{{title}}": lead_data.get("title", "your role"),
            "{{industry}}": lead_data.get("industry", "your industry"),
            "{{location}}": lead_data.get("location", "your area"),
        }
        for placeholder, value in placeholders.items():
            # Ensure value is a string for replacement, handle None gracefully
            replacement_value = str(value) if value is not None else ""
            personalized_content = personalized_content.replace(placeholder, replacement_value)
        return personalized_content

    def run_scheduler_cycle(self):
        """
        Main scheduler loop: fetches due leads, processes each step.
        """
        cycle_start_time = datetime.now(timezone.utc)
        logger.info(f"--- Starting email scheduler cycle ({cycle_start_time.isoformat()}) ---")
        
        processed_count = 0
        error_count = 0
        skipped_count = 0 # For leads that were due but something else prevented send (e.g. config)

        active_lead_statuses = database.get_active_leads_due_for_step(organization_id=None) # Get for all orgs
        
        if not active_lead_statuses:
            logger.info("EmailSchedulerAgent: No leads currently due for an email.")
            logger.info(f"--- Email scheduler cycle finished. Processed: 0, Skipped: 0, Errors: 0 ---")
            return

        logger.info(f"EmailSchedulerAgent: Found {len(active_lead_statuses)} lead campaign statuses potentially due for processing.")

        for status_record in active_lead_statuses:
            now_utc = datetime.now(timezone.utc) # Get fresh timestamp for each record processing
            lead_id = status_record.get('lead_id')
            campaign_id = status_record.get('campaign_id')
            organization_id = status_record.get('organization_id')
            status_id = status_record.get('id') # lead_campaign_status.id
            current_step_completed = status_record.get('current_step_number', 0)
            
            if not all([lead_id, campaign_id, organization_id, status_id is not None]):
                logger.warning(f"EmailSchedulerAgent: Skipping status record due to missing critical IDs: {status_record}")
                error_count +=1
                continue

            logger.debug(f"EmailSchedulerAgent: Evaluating LCS_ID: {status_id} (Lead: {lead_id}, Campaign: {campaign_id}, Org: {organization_id}, Last Step Sent: {current_step_completed})")

            next_step_to_send_data = database.get_next_campaign_step(campaign_id, organization_id, current_step_completed)

            if not next_step_to_send_data:
                logger.info(f"EmailSchedulerAgent: No further steps for Lead ID {lead_id} in Campaign {campaign_id}. Marking sequence as completed.")
                database.update_lead_campaign_status(
                    status_id=status_id, organization_id=organization_id,
                    updates={"status": "completed_sequence", "next_email_due_at": None, "updated_at": now_utc}
                )
                continue 

            next_step_number_to_send = next_step_to_send_data.get('step_number')
            campaign_step_db_id = next_step_to_send_data.get('id') # ID of the campaign_steps record

            lead_data = database.get_lead_by_id(lead_id, organization_id)
            if not lead_data:
                logger.error(f"EmailSchedulerAgent: Lead data not found for Lead ID {lead_id}. Marking status as error.")
                database.update_lead_campaign_status(status_id, organization_id, {"status": "error_lead_not_found", "error_message": "Lead data missing.", "updated_at": now_utc})
                error_count += 1
                continue

            email_settings = database.get_org_email_settings_from_db(organization_id=organization_id)
            if not email_settings or not email_settings.get('is_configured'):
                logger.warning(f"EmailSchedulerAgent: Email settings not configured for Org {organization_id}. Skipping Lead {lead_id}.")
                database.update_lead_campaign_status(status_id, organization_id, {"status": "error_email_config", "error_message": "Organization email settings not configured.", "updated_at": now_utc})
                skipped_count += 1
                continue
            
            subject_template = next_step_to_send_data.get('subject_template')
            body_template = next_step_to_send_data.get('body_template')

            if not subject_template or not body_template:
                 logger.error(f"EmailSchedulerAgent: Template subject or body missing for Campaign {campaign_id}, Step {next_step_number_to_send}. Lead ID {lead_id}.")
                 database.update_lead_campaign_status(status_id, organization_id, {"status": "error_template_missing", "error_message": f"Template content missing for step {next_step_number_to_send}.", "updated_at": now_utc})
                 error_count += 1
                 continue

            final_subject = self._personalize_template(subject_template, lead_data)
            final_body_html = self._personalize_template(body_template, lead_data).replace('\n', '<br/>')
            final_body_text = self._personalize_template(body_template, lead_data)

            email_send_outcome: Optional[EmailSendingResult] = None
            send_exception_message = None
            
            logger.info(f"EmailSchedulerAgent: Attempting to send Campaign {campaign_id} Step {next_step_number_to_send} to Lead {lead_id} ({lead_data.get('email')}) for Org {organization_id}.")
            try:
                 email_send_outcome = send_email(
                     recipient_email=lead_data['email'], subject=final_subject,
                     html_body=final_body_html, text_body=final_body_text,
                     organization_id=organization_id
                 )
            except Exception as e_send:
                 logger.error(f"EmailSchedulerAgent: Exception during send_email call for Lead {lead_id}: {e_send}", exc_info=True)
                 send_exception_message = str(e_send) # Capture the exception message

            update_payload = {"updated_at": now_utc}
            if email_send_outcome and email_send_outcome.success:
                logger.info(f"EmailSchedulerAgent: Successfully sent Step {next_step_number_to_send} to Lead ID {lead_id}. Message-ID: {email_send_outcome.message_id}")
                update_payload["last_email_sent_at"] = now_utc
                update_payload["current_step_number"] = next_step_number_to_send
                update_payload["error_message"] = None # Clear previous errors

                if email_send_outcome.message_id and campaign_step_db_id is not None:
                    log_result = database.log_sent_email(
                        lead_campaign_status_id=status_id, organization_id=organization_id,
                        lead_id=lead_id, campaign_id=campaign_id, campaign_step_id=campaign_step_db_id,
                        message_id_header=email_send_outcome.message_id,
                        to_email=lead_data['email'], subject=final_subject
                    )
                    if not log_result:
                        logger.error(f"EmailSchedulerAgent: CRITICAL - Failed to log sent email with Message-ID {email_send_outcome.message_id} to DB for lead {lead_id}.")
                elif not campaign_step_db_id:
                     logger.error(f"EmailSchedulerAgent: CRITICAL - campaign_step_db_id is None for Step {next_step_number_to_send}, Campaign {campaign_id}. Cannot log sent email accurately.")
                else: # No message_id returned
                    logger.warning(f"EmailSchedulerAgent: Email sent to lead {lead_id} but no Message-ID returned by sender. Reply linking might be affected.")

                next_subsequent_step_data = database.get_next_campaign_step(campaign_id, organization_id, next_step_number_to_send)
                if next_subsequent_step_data:
                    delay_for_next = next_subsequent_step_data.get("delay_days", 0)
                    update_payload["next_email_due_at"] = self._calculate_next_due_at(now_utc, delay_for_next)
                    update_payload["status"] = "active"
                else:
                    logger.info(f"EmailSchedulerAgent: Lead {lead_id} completed all steps in Campaign {campaign_id}.")
                    update_payload["next_email_due_at"] = None
                    update_payload["status"] = "completed_sequence"
                processed_count += 1
            else:
                failure_reason = "Unknown sending error"
                if email_send_outcome and email_send_outcome.error_message:
                    failure_reason = email_send_outcome.error_message
                elif send_exception_message:
                    failure_reason = send_exception_message
                
                logger.error(f"EmailSchedulerAgent: Failed to send Step {next_step_number_to_send} to Lead ID {lead_id}. Reason: {failure_reason}")
                update_payload["status"] = "error_sending_email"
                update_payload["error_message"] = f"Step {next_step_number_to_send} send fail: {failure_reason[:250]}"
                # Optional: schedule a retry if it's a transient error
                # update_payload["next_email_due_at"] = now_utc + timedelta(hours=settings.EMAIL_RETRY_DELAY_HOURS)
                error_count += 1
            
            database.update_lead_campaign_status(status_id, organization_id, update_payload)
            time.sleep(0.2) # Small polite delay

        logger.info(f"--- Email scheduler cycle finished. Processed: {processed_count}, Skipped (not due/config): {skipped_count}, Errors: {error_count} ---")
