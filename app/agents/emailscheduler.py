# app/agents/emailscheduler.py

import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Import project modules
from app.utils.logger import logger
# Import database functions
from app.db import database
# Import Email Crafter if using AI steps
from app.agents.campaign_generator import generate_campaign_steps
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
            subject = None; body = None
            is_ai = next_step_data.get('is_ai_crafted', 0)
            content_prep_error = None

            if is_ai == 1: # Needs AI Generation
                logger.debug(f"Using AI crafter for Step {next_step_number}...")
                if not self.email_crafter:
                     content_prep_error = "AI Email Crafter not initialized."
                     logger.error(content_prep_error) # Log it here
                else: # Fetch context data needed for ANY AI crafting step
                    offerings = database.get_offerings_by_organization_id(organization_id, active_only=True)
                    icp = database.get_icp_by_organization_id(organization_id)
                    org = database.get_organization_by_id(organization_id)
                    org_name = org['name'] if org else f"Org {organization_id}"
                    offering_to_use = offerings[0] if offerings else None

                    if offering_to_use:
                        email_content = None
                        # --- Decide which crafting method to call ---
                        if current_step == 0: # This means we are about to send Step 1 (the initial)
                            logger.debug(f"Calling craft_initial_email for Lead {lead_id}")
                            email_content = self.email_crafter.craft_initial_email(
                                lead_data=lead_data, offering_data=offering_to_use,
                                icp_data=icp, organization_name=org_name
                            )
                        else: # This is a follow-up step (current_step >= 1)
                            logger.debug(f"Calling craft_follow_up_email for Lead {lead_id}, previous step was {current_step}")
                            # Fetch data about the previous step that was sent
                            previous_step_data = database.get_campaign_step_by_number( # Use the function we added
                                campaign_id, organization_id, current_step # Get details of the step JUST completed
                            )
                            if not previous_step_data:
                                 logger.warning(f"Could not fetch previous step ({current_step}) data for follow-up context for lead {lead_id}.")
                            email_content = self.email_crafter.craft_follow_up_email(
                                lead_data=lead_data, offering_data=offering_to_use,
                                icp_data=icp, organization_name=org_name,
                                previous_step_data=previous_step_data, # Pass previous step info
                                current_step_data=next_step_data # Pass details of the step we ARE sending
                            )
                        # --- End method choice ---

                        # Process the result
                        if email_content: subject = email_content.get('subject'); body = email_content.get('body')
                        else: content_prep_error = f"AI email crafting returned no content for Step {next_step_number}."
                    else: content_prep_error = f"Cannot use AI crafter: No active offering found for Org {organization_id}."

            else: # Use Template
                logger.debug(f"Using template for Step {next_step_number}...")
                subject_template = next_step_data.get('subject_template')
                body_template = next_step_data.get('body_template')
                if subject_template and body_template:
                     subject = self._replace_placeholders(subject_template, lead_data)
                     body = self._replace_placeholders(body_template, lead_data)
                else: content_prep_error = f"Template subject or body missing for Step {next_step_number}."

            # --- Keep error handling and Email Sending logic ---
            if content_prep_error:
                 logger.error(f"Content preparation failed for Lead {lead_id}, Step {next_step_number}: {content_prep_error}")
                 database.update_lead_campaign_status(status_id, organization_id, {"status": "error", "error_message": content_prep_error})
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
