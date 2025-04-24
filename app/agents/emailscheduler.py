# app/agents/emailscheduler.py

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Import project modules
from app.utils.logger import logger
# Import database functions
from app.db import database
# Import Email Crafter if using AI steps
from app.agents.emailcampaign import EmailCraftingAgent
# --- CORRECTED IMPORT: Import the main send_email function ---
from app.utils.email_sender import send_email # Import the refactored main function

class EmailSchedulerAgent:
    """
    Agent responsible for periodically checking lead campaign statuses,
    determining the next email step, preparing content (template or AI),
    sending the email via the org's configured provider, and updating status.
    """
    def __init__(self):
        try:
            self.email_crafter = EmailCraftingAgent()
            logger.info("EmailSchedulerAgent initialized with EmailCraftingAgent.")
        except Exception as e:
             logger.error(f"EmailSchedulerAgent failed to initialize EmailCraftingAgent: {e}. AI crafting will fail.")
             self.email_crafter = None

    def _calculate_due_time(self, last_sent_str: Optional[str], delay_days: int) -> Optional[datetime]:
        # ... (Keep this helper function as is) ...
        pass

    def _replace_placeholders(self, template: str, lead_data: dict) -> str:
         # ... (Keep this helper function as is) ...
         pass

    def run_scheduler_cycle(self):
        """
        Main scheduler loop: fetches due leads, processes each step.
        """
        logger.info("--- Starting email scheduler cycle ---")
        now_utc = datetime.now(timezone.utc)
        processed_count = 0; error_count = 0; skipped_count = 0

        # Fetch potentially due leads (simplified query)
        active_lead_statuses = database.get_active_leads_due_for_step(organization_id=None) # Pass Org ID if running per-org
        logger.info(f"Found {len(active_lead_statuses)} active lead campaign statuses to evaluate.")
        if not active_lead_statuses: return

        for status_record in active_lead_statuses:
            # ... (Keep logic to extract lead_id, campaign_id, org_id, etc.) ...
            lead_id = status_record.get('lead_id'); campaign_id = status_record.get('campaign_id'); # etc...
            organization_id = status_record.get('organization_id'); status_id = status_record.get('id')
            current_step = status_record.get('current_step_number', 0); last_sent_at_str = status_record.get('last_email_sent_at')

            if not all([lead_id, campaign_id, organization_id, status_id is not None]): continue # Skip bad records

            logger.debug(f"Evaluating Lead ID: {lead_id}, Org: {organization_id}, Current Step: {current_step}")
            next_step_data = database.get_next_campaign_step(campaign_id, organization_id, current_step)

            if not next_step_data:
                # ... (Keep logic to mark as completed) ...
                database.update_lead_campaign_status(status_id, organization_id, {"status": "completed"})
                continue

            next_step_number = next_step_data.get('step_number'); delay = next_step_data.get('delay_days', 1)
            due_time = self._calculate_due_time(last_sent_at_str, delay)
            if not due_time or due_time > now_utc: skipped_count += 1; continue

            logger.info(f"Processing Step {next_step_number} for Lead ID {lead_id} (Status ID: {status_id})")
            lead_data = database.get_lead_by_id(lead_id, organization_id)
            if not lead_data:
                # ... (Keep logic to handle missing lead data) ...
                error_count += 1; continue

            # --- Prepare Email Content (Keep this logic as is) ---
            subject = None; body = None; content_prep_error = None
            is_ai = next_step_data.get('is_ai_crafted', 0)
            if is_ai == 1:
                # ... (Keep logic to call AI Crafter - fetches offering/icp data) ...
                pass
            else: # Use template
                # ... (Keep logic to get template and replace placeholders) ...
                pass

            if content_prep_error:
                 # ... (Keep logic to log error and update status) ...
                 error_count += 1; continue

            # --- === Send Email using the main 'send_email' function === ---
            send_success = False
            if subject and body:
                 logger.info(f"Attempting send for Lead {lead_id}, Org {organization_id}, Step {next_step_number}")
                 try:
                     # --- UPDATED CALL ---
                     # Pass only recipient, subject, body, and org_id.
                     # The send_email function now handles fetching settings and routing to the correct provider.
                     send_success = send_email(
                         recipient_email=lead_data['email'],
                         subject=subject,
                         html_body=body.replace('\n', '<br/>'),
                         organization_id=organization_id # Pass org_id
                     )
                     # --- END UPDATED CALL ---
                 except Exception as send_ex:
                     # Catch potential errors within the send_email function itself
                     logger.error(f"Error occurred calling send_email utility for Lead {lead_id}: {send_ex}", exc_info=True)
                     send_success = False # Ensure failure on exception
            else:
                 # Should have been caught by content_prep_error check above
                 logger.error(f"Internal Error: Reached sending stage without subject/body for Lead {lead_id}")
                 error_count += 1
                 database.update_lead_campaign_status(status_id, organization_id, {"status": "error", "error_message": "Internal content preparation error"})
                 continue


            # --- Update Lead Status Based on Send Result (Keep this logic) ---
            update_payload = {}
            if send_success:
                # ... (update status to active/completed, set last_email_sent_at) ...
                processed_count += 1
            else:
                # ... (update status to error, set error_message) ...
                error_count += 1
            database.update_lead_campaign_status(status_id, organization_id, update_payload)

            # Optional delay
            # time.sleep(0.5)


        logger.info(f"--- Email scheduler cycle finished. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count} ---")


# --- How to run this? ---
# (Keep comments about running mechanism)
