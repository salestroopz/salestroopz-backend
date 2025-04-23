# app/agents/leadworkflow.py

from typing import List, Dict, Any, Optional
from app.schemas import LeadInput, LeadResponse # Keep needed schemas
from pydantic import BaseModel

# Import Agents
from app.agents.leadenrichment import LeadEnrichmentAgent
from app.agents.icp_matcher import ICPMatcherAgent
# from app.agents.crmagent import CRMConnectorAgent
# from app.agents.appointment import AppointmentAgent # Keep commented out or remove if not used here

# Import Utilities
from app.utils.logger import logger
from app.db import database

class LeadWorkflowAgent:
    def __init__(self):
        self.enrichment_agent = LeadEnrichmentAgent()
        self.matcher_agent = ICPMatcherAgent()
        # Instantiate other agents ONLY if they are actually used within this workflow agent's methods
        # self.appointment_agent = AppointmentAgent() # Example: Not called directly in process_single_lead below
        logger.info("LeadWorkflowAgent initialized.")

    def process_single_lead(self, initial_lead_dict: dict, organization_id: int) -> Dict[str, Any]:
        """
        Enriches, matches, saves a SINGLE lead, and enrolls qualified leads in a campaign.
        Returns processing status/results for this lead.
        """
        logger.info(f"Processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        final_save_data = initial_lead_dict.copy()
        is_qualified = False # Initialize qualification status
        match_score = 0.0 # Initialize score
        campaign_enrolled = False # Initialize enrollment status

        # 1. Enrich Lead
        try:
            enriched_dict = self.enrichment_agent.enrich(initial_lead_dict)
            final_save_data.update(enriched_dict)
            logger.debug(f"Enriched lead {initial_lead_dict.get('email')}")
        except Exception as enrich_err:
            logger.error(f"Enrichment failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {enrich_err}", exc_info=True)
            # Continue without enrichment data

        # 2. Match Lead against ICP
        icp_data = None
        try:
            icp_data = database.get_icp_by_organization_id(organization_id)
            if icp_data:
                match_score = self.matcher_agent.match(final_save_data, organization_id=organization_id)
                is_qualified = match_score >= 0.7 # Qualification threshold
                logger.info(f"Lead {initial_lead_dict.get('email')} matched score: {match_score:.2f}, Qualified: {is_qualified}")
                final_save_data['matched'] = 1 if is_qualified else 0
                final_save_data['reason'] = f"ICP Match Score: {match_score:.2f}"
            else:
                 logger.warning(f"No ICP found for Org {organization_id}. Lead cannot be qualified.")
                 final_save_data['matched'] = 0
                 final_save_data['reason'] = "No ICP definition found"
                 is_qualified = False # Explicitly set to false if no ICP

        except Exception as match_err:
             logger.error(f"Matching failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {match_err}", exc_info=True)
             final_save_data['matched'] = 0
             final_save_data['reason'] = f"Matching Error: {match_err}"
             is_qualified = False # Cannot qualify if matching failed

        # 3. CRM Push Placeholder (If Qualified)
        crm_pushed = False # Initialize status flag
        if is_qualified:
            # ... (Simulated CRM logic) ...
            crm_pushed = True # Simulate success
            final_save_data['crm_status'] = "Pushed (Simulated)"
        else:
            # Set a status even if not qualified/pushed
             final_save_data.setdefault('crm_status', 'Not Qualified for CRM')


        # 4. Save Lead Data to Database (This must happen before enrollment)
        saved_lead_data = None
        try:
            # Pass the potentially enriched and matched data
            saved_lead_data = database.save_lead(final_save_data, organization_id=organization_id)
            if saved_lead_data and saved_lead_data.get('id'):
                 logger.debug(f"Saved lead {saved_lead_data.get('email')} (ID: {saved_lead_data.get('id')}) for Org ID {organization_id} to DB.")
            else:
                 # Save failed, error should have been logged in save_lead
                 raise ValueError("save_lead did not return valid saved lead data with an ID.")
        except Exception as db_err:
            logger.error(f"Failed to save lead {final_save_data.get('email')} (Org: {organization_id}) to DB: {db_err}", exc_info=True)
            # Cannot proceed to enrollment if save failed
            return {"email": initial_lead_dict.get("email"), "status": "error", "detail": f"DB Save Failed: {db_err}"}

        # --- 5. Enroll in Campaign (If Qualified and Saved) ---
        lead_id = saved_lead_data.get('id') # Get the ID from the saved data
        if is_qualified and lead_id:
            logger.info(f"Attempting campaign enrollment for qualified Lead ID: {lead_id}")
            try:
                # --- TODO: Implement logic to find the correct campaign_id ---
                # Example: Fetch the first active campaign for the org
                active_campaigns = database.get_campaigns_by_organization(organization_id, active_only=True)
                if active_campaigns:
                    campaign_id_to_enroll = active_campaigns[0]['id'] # Use first active campaign
                    logger.info(f"Enrolling Lead ID {lead_id} into Campaign ID: {campaign_id_to_enroll}")
                    enroll_status_record = database.enroll_lead_in_campaign(lead_id, campaign_id_to_enroll, organization_id)
                    if enroll_status_record:
                        logger.info(f"Successfully created campaign enrollment record (ID: {enroll_status_record.get('id')}) for Lead ID: {lead_id}")
                        campaign_enrolled = True
                        # Update lead's main status if desired
                        database.update_lead_partial(lead_id, organization_id, {"crm_status": "Campaign Active"})
                    else:
                        # enroll_lead_in_campaign should log specific error (e.g., already enrolled)
                        logger.error(f"Failed to create campaign enrollment record for Lead ID: {lead_id}.")
                        database.update_lead_partial(lead_id, organization_id, {"crm_status": "Enrollment Failed"})
                else:
                    logger.warning(f"No active campaigns found for Org {organization_id}. Cannot enroll lead {lead_id}.")
                    database.update_lead_partial(lead_id, organization_id, {"crm_status": "No Active Campaign"})

            except Exception as enroll_err:
                 logger.error(f"Error during campaign enrollment for Lead ID {lead_id}: {enroll_err}", exc_info=True)
                 # Update lead status to reflect error
                 database.update_lead_partial(lead_id, organization_id, {"crm_status": "Enrollment Error"})


        logger.info(f"Finished processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        # Return final status including enrollment attempt
        return {
            "email": initial_lead_dict.get("email"),
            "lead_id": lead_id, # Return the lead's database ID
            "status": "processed",
            "qualified": is_qualified,
            "match_score": match_score,
            # "crm_pushed": crm_pushed, # CRM status now reflected in leads table potentially
            "campaign_enrolled": campaign_enrolled # Indicate if enrollment record was created
            # "appointment_confirmed": final_save_data.get('appointment_confirmed', 0) # If tracking this earlier
            }

    # --- Keep run_pipeline method (no changes needed here) ---
    def run_pipeline(self, leads_input: List[Dict], organization_id: int) -> List[Dict]:
        # ... (existing implementation calling process_single_lead) ...
        pass

    # --- run_full_workflow method REMOVED ---
