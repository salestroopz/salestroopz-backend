# app/agents/emailscheduler.py

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional

from app.utils.logger import logger
from app.db import database
# REMOVE: from app.agents.campaign_generator import generate_campaign_steps # Not needed here
# REMOVE: EmailCraftingAgent import
from app.utils.email_sender import send_email # Your centralized email sender

class EmailSchedulerAgent:
    """
    Agent responsible for periodically checking lead campaign statuses,
    retrieving pre-generated email steps, personalizing, sending emails,
    and updating lead status.
    """
    def __init__(self):
        # No EmailCraftingAgent needed anymore
        logger.info("EmailSchedulerAgent initialized.")

    def _calculate_next_due_at(self, last_sent_at_input: Optional[Any], delay_days: int) -> Optional[datetime]:
        """
        Calculates the next due time based on the last sent time and delay.
        If last_sent_at is None (e.g., for the very first email of a sequence for a lead),
        it assumes the email is due now or based on enrollment time + delay.
        For simplicity, if last_sent_at is None, this can return now + delay,
        or the calling logic can handle the "first email" due time.
        """
        if delay_days < 0: delay_days = 0 # Ensure non-negative delay

        if last_sent_at_input is None:
            # For the first email, due time is typically enrollment_time + delay_days_for_step_1
            # This function is more for calculating subsequent steps.
            # The get_active_leads_due_for_step should handle the initial due time.
            # If called for a step after the first, last_sent_at should not be None.
            # Let's assume for now this is for steps *after* the first, or that
            # next_email_due_at was correctly set upon enrollment for the first step.
            # If used strictly for calculating *next* due after a send:
            return datetime.now(timezone.utc) + timedelta(days=delay_days)


        last_sent_dt: Optional[datetime] = None
        if isinstance(last_sent_at_input, str):
            try:
                last_sent_dt = datetime.fromisoformat(last_sent_at_input.replace('Z', '+00:00'))
                if last_sent_dt.tzinfo is None: # If no timezone, assume UTC
                    last_sent_dt = last_sent_dt.replace(tzinfo=timezone.utc)
            except ValueError:
                logger.warning(f"Could not parse last_sent_at string: {last_sent_at_input}")
                return datetime.now(timezone.utc) + timedelta(days=delay_days) # Fallback
        elif isinstance(last_sent_at_input, datetime):
            last_sent_dt = last_sent_at_input
            if last_sent_dt.tzinfo is None: # Ensure UTC
                 last_sent_dt = last_sent_dt.replace(tzinfo=timezone.utc)
        else: # Fallback if type is unexpected
            logger.warning(f"Unexpected type for last_sent_at: {type(last_sent_at_input)}")
            return datetime.now(timezone.utc) + timedelta(days=delay_days)


        return last_sent_dt + timedelta(days=delay_days)

    def _personalize_template(self, template: Optional[str], lead_data: dict) -> str:
        """Replaces placeholders in a template string with lead data."""
        if not template: return ""
        
        personalized_content = template
        # Ensure lead_data values are strings for replacement, or handle None appropriately
        lead_name = lead_data.get("name", "")
        first_name = lead_name.split(" ")[0] if lead_name else "there"

        placeholders = {
            "{{lead_name}}": lead_name or "there", # Fallback if name is empty
            "{{lead_first_name}}": first_name,
            "{{company_name}}": lead_data.get("company", "your company"),
            "{{title}}": lead_data.get("title", "your role"),
            "{{industry}}": lead_data.get("industry", "your industry"),
            "{{location}}": lead_data.get("location", "your area"), # Added location
            # Add more placeholders as your CampaignGeneratorAgent might use
        }
        for placeholder, value in placeholders.items():
            personalized_content = personalized_content.replace(placeholder, str(value) if value is not None else "")
        return personalized_content

    def run_scheduler_cycle(self):
        """
        Main scheduler loop: fetches due leads, processes each step.
        """
        logger.info(f"--- Starting email scheduler cycle ({datetime.now(timezone.utc)}) ---")
        now_utc = datetime.now(timezone.utc)
        processed_count = 0; error_count = 0; skipped_not_due = 0

        # Fetches leads where status is 'active' AND (next_email_due_at IS NULL OR next_email_due_at <= now_utc)
        active_lead_statuses = database.get_active_leads_due_for_step(organization_id=None)
        
        if not active_lead_statuses:
            logger.info("EmailSchedulerAgent: No leads currently due for an email.")
            return

        logger.info(f"EmailSchedulerAgent: Found {len(active_lead_statuses)} active lead campaign statuses potentially due.")

        for status_record in active_lead_statuses:
            lead_id = status_record.get('lead_id')
            campaign_id = status_record.get('campaign_id')
            organization_id = status_record.get('organization_id')
            status_id = status_record.get('id') # This is lead_campaign_status.id
            current_step_completed = status_record.get('current_step_number', 0) # Last step successfully sent
            
            # Basic validation
            if not all([lead_id, campaign_id, organization_id, status_id is not None]):
                logger.warning(f"EmailSchedulerAgent: Skipping status record with missing critical IDs: {status_record}")
                error_count +=1 # Count as an error to investigate
                continue

            logger.debug(f"EmailSchedulerAgent: Evaluating Lead ID: {lead_id}, Campaign ID: {campaign_id}, Org: {organization_id}, Last Step Sent: {current_step_completed}")

            # Fetch the next step template (current_step_completed + 1)
            next_step_to_send_data = database.get_next_campaign_step(campaign_id, organization_id, current_step_completed)

            if not next_step_to_send_data:
                logger.info(f"EmailSchedulerAgent: No further steps for Lead ID {lead_id} in Campaign {campaign_id}. Marking sequence as completed.")
                database.update_lead_campaign_status(
                    status_id=status_id,
                    organization_id=organization_id,
                    updates={"status": "completed_sequence", "next_email_due_at": None, "updated_at": now_utc}
                )
                # processed_count += 1 # Or a different counter for "completed"
                continue # Move to next lead status

            next_step_number_to_send = next_step_to_send_data.get('step_number')
            
            # Due time check (already done by get_active_leads_due_for_step, but as a failsafe or if logic changes)
            # The `next_email_due_at` on the status_record is what makes it "due".
            # If it was NULL (newly enrolled), it's due now for step 1 (if step 1 delay is 0).
            # If it was set by previous step, it's due if <= now_utc.

            logger.info(f"EmailSchedulerAgent: Processing Step {next_step_number_to_send} for Lead ID {lead_id} (LCS_ID: {status_id})")
            
            lead_data = database.get_lead_by_id(lead_id, organization_id)
            if not lead_data:
                logger.error(f"EmailSchedulerAgent: Lead data not found for Lead ID {lead_id} (Org: {organization_id}). Marking status as error.")
                database.update_lead_campaign_status(status_id, organization_id, {"status": "error_lead_not_found", "error_message": "Lead data missing.", "updated_at": now_utc})
                error_count += 1
                continue

            # Prepare Email Content (Always from template now)
            subject_template = next_step_to_send_data.get('subject_template')
            body_template = next_step_to_send_data.get('body_template')
            content_prep_error = None

            if not subject_template or not body_template:
                content_prep_error = f"Template subject or body missing for Campaign {campaign_id}, Step {next_step_number_to_send}."
            
            if content_prep_error:
                 logger.error(f"EmailSchedulerAgent: Content preparation failed for Lead {lead_id}, Step {next_step_number_to_send}: {content_prep_error}")
                 database.update_lead_campaign_status(status_id, organization_id, {"status": "error_template_missing", "error_message": content_prep_error, "updated_at": now_utc})
                 error_count += 1
                 continue

            final_subject = self._personalize_template(subject_template, lead_data)
            # Replace \n with <br> for HTML emails, ensure body_template itself does not already contain HTML tags if this is unintended.
            final_body_html = self._personalize_template(body_template, lead_data).replace('\n', '<br/>') 
            # For a plain text version, just personalize without <br>
            final_body_text = self._personalize_template(body_template, lead_data)


            # Send Email using your centralized send_email utility
            send_success = False
            logger.info(f"EmailSchedulerAgent: Attempting send for Lead {lead_id} (Email: {lead_data.get('email')}), Org {organization_id}, Campaign {campaign_id}, Step {next_step_number_to_send}")
            try:
                 send_success = send_email( # This function must exist in app.utils.email_sender
                     recipient_email=lead_data['email'],
                     subject=final_subject,
                     html_body=final_body_html, # Pass HTML body
                     text_body=final_body_text,   # Pass plain text body
                     organization_id=organization_id
                 )
            except Exception as send_ex:
                 logger.error(f"EmailSchedulerAgent: Error during send_email call for Lead {lead_id}: {send_ex}", exc_info=True)
                 send_success = False

            # Update Lead Status Based on Send Result
            update_payload = {"updated_at": now_utc}
            if send_success:
                logger.info(f"EmailSchedulerAgent: Successfully sent Step {next_step_number_to_send} to Lead ID {lead_id}.")
                update_payload["last_email_sent_at"] = now_utc
                update_payload["current_step_number"] = next_step_number_to_send # The step just sent
                update_payload["error_message"] = None # Clear previous errors

                # Calculate next_email_due_at for the *subsequent* step
                next_subsequent_step_data = database.get_next_campaign_step(
                    campaign_id, organization_id, next_step_number_to_send # Pass step just sent
                )
                if next_subsequent_step_data:
                    delay_for_very_next_step = next_subsequent_step_data.get("delay_days", 0)
                    update_payload["next_email_due_at"] = now_utc + timedelta(days=delay_for_very_next_step)
                    update_payload["status"] = "active" # Still active, waiting for next step
                else: # This was the last step
                    logger.info(f"EmailSchedulerAgent: Lead {lead_id} completed all steps in Campaign {campaign_id}.")
                    update_payload["next_email_due_at"] = None
                    update_payload["status"] = "completed_sequence"
                processed_count += 1
            else:
                logger.error(f"EmailSchedulerAgent: Failed to send Step {next_step_number_to_send} to Lead ID {lead_id}.")
                update_payload["status"] = "error_sending_email" # Or a retry status
                update_payload["error_message"] = f"Failed to send step {next_step_number_to_send}. Check email_sender logs."
                # Optionally, schedule a retry by setting next_email_due_at
                # update_payload["next_email_due_at"] = now_utc + timedelta(hours=1) # Retry in 1 hour
                error_count += 1
            
            database.update_lead_campaign_status(status_id, organization_id, update_payload)
            time.sleep(0.2) # Small polite delay between processing leads to avoid overwhelming DB/sender

        logger.info(f"--- Email scheduler cycle finished. Processed: {processed_count}, Skipped (not due now): {skipped_not_due}, Errors: {error_count} ---")

# To run this agent (e.g., from a main scheduler script or a Celery task):
# if __name__ == "__main__":
#     scheduler_agent = EmailSchedulerAgent()
#     while True:
#         scheduler_agent.run_scheduler_cycle()
#         logger.info("Sleeping for 5 minutes before next cycle...")
#         time.sleep(300) # Sleep for 5 minutes
