# app/agents/emailscheduler.py

import time
from datetime import datetime, timedelta, timezone # Ensure timezone for comparisons
from typing import Dict, List, Optional

# Import project modules
from app.utils.logger import logger
# Import database functions REQUIRED by the scheduler
from app.db import database
# Import Email Crafter if using AI steps
from app.agents.emailcampaign import EmailCraftingAgent
# Import Email Sender utility
from app.utils.email_sender import send_email, get_org_email_settings

class EmailSchedulerAgent:
    """
    Agent responsible for periodically checking lead campaign statuses,
    determining the next email step, preparing content (template or AI),
    sending the email, and updating the lead's status in the campaign.
    """
    def __init__(self):
        # Initialize agents/utilities needed within the cycle
        # Instantiate EmailCrafter only if needed (can be done inside loop too)
        try:
            self.email_crafter = EmailCraftingAgent()
            logger.info("EmailSchedulerAgent initialized with EmailCraftingAgent.")
        except Exception as e:
             logger.error(f"EmailSchedulerAgent failed to initialize EmailCraftingAgent: {e}. AI crafting will fail.")
             self.email_crafter = None

    def _calculate_due_time(self, last_sent_str: Optional[str], delay_days: int) -> Optional[datetime]:
        """Calculates when the next email is due based on last sent time and delay."""
        if not last_sent_str:
             # If first email, assume it's due relative to when lead was enrolled.
             # The DB query for due leads should handle this initial state.
             # Returning 'now' ensures it gets picked up if query is basic.
             return datetime.now(timezone.utc)

        try:
            # Attempt to parse ISO format timestamp, assume UTC
            # Ensure timestamps are stored consistently in the DB (preferably ISO format UTC)
            last_sent_dt = datetime.fromisoformat(last_sent_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
            due_time = last_sent_dt + timedelta(days=int(delay_days)) # Ensure delay is int
            return due_time
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Could not parse last_email_sent_at timestamp '{last_sent_str}' or delay '{delay_days}': {e}")
            return None

    def _replace_placeholders(self, template: str, lead_data: dict) -> str:
         """Replaces simple placeholders like {{name}}, {{company}} in templates."""
         if not template: return ""
         content = template
         # Use .get() for safety, provide fallbacks
         lead_name = lead_data.get("name", "") or ""
         first_name = lead_name.split(" ")[0] or "there"
         content = content.replace("{{name}}", lead_name or "there")
         content = content.replace("{{first_name}}", first_name)
         content = content.replace("{{company}}", lead_data.get("company", "your company") or "your company")
         content = content.replace("{{title}}", lead_data.get("title", "your role") or "your role")
         # Add more replacements as needed (e.g., {{offering_name}})
         return content

    def run_scheduler_cycle(self):
        """
        Main scheduler loop: fetches due leads, processes each step.
        Should be run periodically.
        """
        logger.info("--- Starting email scheduler cycle ---")
        now_utc = datetime.now(timezone.utc)
        processed_count = 0
        error_count = 0
        skipped_count = 0

        # --- Fetch potentially due leads ---
        # TODO: Enhance get_active_leads_due_for_step query for efficiency if possible
        # For now, it gets all 'active' leads, filtering happens in the loop.
        active_lead_statuses = database.get_active_leads_due_for_step(organization_id=None) # Pass Org ID if running per-org
        logger.info(f"Found {len(active_lead_statuses)} active lead campaign statuses to evaluate.")

        if not active_lead_statuses:
             logger.info("No active leads found in campaigns. Cycle complete.")
             return # Nothing to do

        for status_record in active_lead_statuses:
            lead_id = status_record.get('lead_id')
            campaign_id = status_record.get('campaign_id')
            organization_id = status_record.get('organization_id')
            current_step = status_record.get('current_step_number', 0)
            last_sent_at_str = status_record.get('last_email_sent_at')
            status_id = status_record.get('id')

            if not all([lead_id, campaign_id, organization_id, status_id is not None]):
                 logger.warning(f"Scheduler: Skipping status record ID {status_id} due to missing IDs: {status_record}")
                 skipped_count += 1
                 continue

            logger.debug(f"Evaluating Lead ID: {lead_id}, Org: {organization_id}, Current Step: {current_step}")

            # --- Get the NEXT step details ---
            next_step_data = database.get_next_campaign_step(campaign_id, organization_id, current_step)

            if not next_step_data:
                logger.info(f"No further steps found for Lead ID {lead_id} in Campaign ID {campaign_id}. Marking as completed.")
                database.update_lead_campaign_status(status_id, organization_id, {"status": "completed"})
                continue # Move to the next lead

            next_step_number = next_step_data.get('step_number')
            delay = next_step_data.get('delay_days', 1)

            # --- Check if the next step is due ---
            due_time = self._calculate_due_time(last_sent_at_str, delay)

            # If due_time calculation failed or it's not yet time, skip
            if not due_time or due_time > now_utc:
                 #logger.debug(f"Lead {lead_id} not due yet (Due: {due_time}, Now: {now_utc}). Skipping.")
                 skipped_count += 1
                 continue

            logger.info(f"Processing Step {next_step_number} for Lead ID {lead_id} (Status ID: {status_id})")

            # --- Get Lead Data ---
            lead_data = database.get_lead_by_id(lead_id, organization_id)
            if not lead_data:
                logger.error(f"Scheduler: Could not find Lead data for Lead ID {lead_id}. Setting status to error.")
                database.update_lead_campaign_status(status_id, organization_id, {"status": "error", "error_message": "Lead data not found"})
                error_count += 1
                continue

            # --- Prepare Email Content ---
            subject = None; body = None
            is_ai = next_step_data.get('is_ai_crafted', 0)
            content_prep_error = None # Track errors during content generation

            if is_ai == 1:
                logger.debug(f"Using AI crafter for Step {next_step_number}...")
                if not self.email_crafter:
                     content_prep_error = "AI Email Crafter not initialized."
                else:
                    # Fetch data needed for AI crafting
                    offerings = database.get_offerings_by_organization_id(organization_id, active_only=True)
                    icp = database.get_icp_by_organization_id(organization_id)
                    org = database.get_organization_by_id(organization_id)
                    org_name = org['name'] if org else f"Org {organization_id}"
                    offering_to_use = offerings[0] if offerings else None

                    if offering_to_use:
                        email_content = self.email_crafter.craft_initial_email( # Maybe craft_followup_email later?
                            lead_data=lead_data, offering_data=offering_to_use,
                            icp_data=icp, organization_name=org_name
                        )
                        if email_content: subject = email_content.get('subject'); body = email_content.get('body')
                        else: content_prep_error = "AI email crafting returned no content."
                    else: content_prep_error = f"Cannot use AI crafter: No active offering found for Org {organization_id}."

            else: # Use template
                logger.debug(f"Using template for Step {next_step_number}...")
                subject_template = next_step_data.get('subject_template')
                body_template = next_step_data.get('body_template')
                if subject_template and body_template:
                     subject = self._replace_placeholders(subject_template, lead_data)
                     body = self._replace_placeholders(body_template, lead_data)
                else: content_prep_error = f"Template subject or body missing for Step {next_step_number}."

            if content_prep_error:
                 logger.error(f"Content preparation failed for Lead {lead_id}, Step {next_step_number}: {content_prep_error}")
                 database.update_lead_campaign_status(status_id, organization_id, {"status": "error", "error_message": content_prep_error})
                 error_count += 1
                 continue # Skip to next lead

            # --- Send Email ---
            send_success = False
            email_config = get_org_email_settings(organization_id) # Fetch org-specific settings
            if not all(email_config.values()):
                 logger.error(f"Cannot send email for Lead {lead_id}: Email sending not configured for Org {organization_id}.")
                 database.update_lead_campaign_status(status_id, organization_id, {"status": "error", "error_message": "Email sending not configured for org"})
                 error_count += 1
                 continue # Skip to next lead

            # Proceed with sending only if content and config are ready
            send_success = send_email(
                recipient_email=lead_data['email'], subject=subject, html_body=body.replace('\n', '<br/>'),
                sender_address=email_config["sender_address"], sender_name=email_config["sender_name"],
                smtp_host=email_config["smtp_host"], smtp_port=email_config["smtp_port"],
                smtp_username=email_config["smtp_username"], smtp_password=email_config["smtp_password"]
            )

            # --- Update Lead Status Based on Send Result ---
            update_payload = {}
            if send_success:
                logger.info(f"Successfully sent Step {next_step_number} to Lead {lead_id}.")
                update_payload['current_step_number'] = next_step_number
                update_payload['last_email_sent_at'] = now_utc.isoformat() # Store timestamp
                update_payload['error_message'] = None # Clear previous errors on success

                # Check if this was the last step in the campaign
                is_last_step = not database.get_next_campaign_step(campaign_id, organization_id, next_step_number)
                if is_last_step:
                    update_payload['status'] = 'completed'
                    logger.info(f"Marking campaign completed for Lead {lead_id}.")
                else:
                     update_payload['status'] = 'active' # Keep active for next step

                processed_count += 1
            else:
                logger.error(f"Failed to send Step {next_step_number} to Lead {lead_id} (check email_sender logs).")
                update_payload['status'] = 'error' # Mark as error on send failure
                update_payload['error_message'] = f"Failed to send step {next_step_number} email."
                error_count += 1

            database.update_lead_campaign_status(status_id, organization_id, update_payload)
            # Optional: Add a small delay between processing leads to avoid hitting rate limits
            # time.sleep(0.5)


        logger.info(f"--- Email scheduler cycle finished. Processed: {processed_count}, Skipped: {skipped_count}, Errors: {error_count} ---")


# --- How to run this? ---
# (Keep comments about running via loop, APScheduler/Celery, or API trigger)
