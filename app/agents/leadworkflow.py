# app/agents/leadworkflow.py

from typing import List, Dict, Any, Optional
from app.schemas import LeadInput, LeadResponse # Keep needed schemas
from pydantic import BaseModel

# Import Agents
from app.agents.leadenrichment import LeadEnrichmentAgent
from app.agents.icp_matcher import ICPMatcherAgent
from app.agents.campaign_generator import generate_campaign_steps
# from app.agents.crmagent import CRMConnectorAgent
# from app.agents.appointment import AppointmentAgent

# Import Utilities
from app.utils.logger import logger
from app.db import database

class LeadWorkflowAgent:
    def __init__(self):
        self.enrichment_agent = LeadEnrichmentAgent()
        self.matcher_agent = ICPMatcherAgent()
        self.email_crafter = EmailCraftingAgent() # <--- INSTANTIATE EMAIL CRAFTER
        # self.crm_agent = CRMConnectorAgent()
        # self.appointment_agent = AppointmentAgent()
        logger.info("LeadWorkflowAgent initialized (including EmailCrafter).")

    def process_single_lead(self, initial_lead_dict: dict, organization_id: int) -> Dict[str, Any]:
        """
        Enriches, matches, crafts email, saves lead, and enrolls qualified leads in a campaign.
        Returns processing status/results for this lead.
        """
        logger.info(f"Processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        final_save_data = initial_lead_dict.copy()
        is_qualified = False
        match_score = 0.0
        campaign_enrolled = False
        generated_email_content = None # Store crafted email

        # 1. Enrich Lead
        try:
            enriched_dict = self.enrichment_agent.enrich(initial_lead_dict)
            final_save_data.update(enriched_dict)
            logger.debug(f"Enriched lead {initial_lead_dict.get('email')}")
        except Exception as enrich_err:
            logger.error(f"Enrichment failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {enrich_err}", exc_info=True)

        # 2. Match Lead against ICP
        icp_data = None
        try:
            icp_data = database.get_icp_by_organization_id(organization_id)
            if icp_data:
                match_score = self.matcher_agent.match(final_save_data, organization_id=organization_id)
                is_qualified = match_score >= 0.7
                logger.info(f"Lead {initial_lead_dict.get('email')} matched score: {match_score:.2f}, Qualified: {is_qualified}")
                final_save_data['matched'] = 1 if is_qualified else 0
                final_save_data['reason'] = f"ICP Match Score: {match_score:.2f}"
            else:
                 logger.warning(f"No ICP found for Org {organization_id}. Lead cannot be qualified.")
                 final_save_data['matched'] = 0; final_save_data['reason'] = "No ICP definition found"
                 is_qualified = False
        except Exception as match_err:
             logger.error(f"Matching failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {match_err}", exc_info=True)
             final_save_data['matched'] = 0; final_save_data['reason'] = f"Matching Error: {match_err}"
             is_qualified = False

        # --- 3. Craft Initial Email (if qualified) ---
        if is_qualified:
            logger.info(f"Lead qualified, attempting email craft for {initial_lead_dict.get('email')}")
            try:
                # Fetch necessary context for the email
                offerings = database.get_offerings_by_organization_id(organization_id, active_only=True)
                org_details = database.get_organization_by_id(organization_id)
                org_name = org_details.get('name', f"Org {organization_id}") if org_details else f"Org {organization_id}"

                if offerings:
                    offering_to_use = offerings[0] # Use the first active offering
                    logger.debug(f"Using offering '{offering_to_use.get('name')}' for email craft.")

                    # Call the crafting agent
                    generated_email_content = self.email_crafter.craft_initial_email(
                        lead_data=final_save_data,
                        offering_data=offering_to_use,
                        icp_data=icp_data, # Pass fetched ICP (can be None)
                        organization_name=org_name
                    )

                    if generated_email_content:
                        logger.info(f"Email crafted successfully for {initial_lead_dict.get('email')}.")
                        # Optional: Store generated content before saving lead
                        # final_save_data['generated_subject'] = generated_email_content.get('subject')
                        # final_save_data['generated_body'] = generated_email_content.get('body')
                    else:
                        logger.error(f"Email crafting failed for {initial_lead_dict.get('email')}, proceeding without.")
                        final_save_data['reason'] += "; Email Crafting Failed"
                else:
                    logger.warning(f"No active offerings found for Org {organization_id}. Cannot craft email.")
                    final_save_data['reason'] += "; No Active Offering"
                    # Decide if this should disqualify the lead for campaign enrollment
                    # is_qualified = False # Optional: uncomment to prevent enrollment if no offering

            except Exception as craft_err:
                logger.error(f"Error during email crafting call: {craft_err}", exc_info=True)
                final_save_data['reason'] += "; Email Crafting Error"

        # 4. CRM Push Placeholder (If Qualified)
        crm_pushed = False
        if is_qualified:
            # ... (Simulated CRM logic) ...
            final_save_data['crm_status'] = "Pushed (Simulated)"
        else:
            final_save_data.setdefault('crm_status', 'Not Qualified')


        # 5. Save Lead Data to Database (Must happen before enrollment)
        saved_lead_data = None
        try:
            saved_lead_data = database.save_lead(final_save_data, organization_id=organization_id)
            if not (saved_lead_data and saved_lead_data.get('id')):
                 raise ValueError("save_lead did not return valid saved lead data with an ID.")
            logger.debug(f"Saved lead {saved_lead_data.get('email')} (ID: {saved_lead_data.get('id')}) for Org ID {organization_id} to DB.")
        except Exception as db_err:
            logger.error(f"Failed to save lead {final_save_data.get('email')} (Org: {organization_id}) to DB: {db_err}", exc_info=True)
            return {"email": initial_lead_dict.get("email"), "status": "error", "detail": f"DB Save Failed: {db_err}"}


        # 6. Enroll in Campaign (If Qualified and Saved)
        lead_id = saved_lead_data.get('id')
        if is_qualified and lead_id: # Check qualification status again (might have changed if no offering)
            logger.info(f"Attempting campaign enrollment for qualified Lead ID: {lead_id}")
            try:
                # --- TODO: Implement robust logic to find the correct campaign_id ---
                active_campaigns = database.get_campaigns_by_organization(organization_id, active_only=True)
                if active_campaigns:
                    campaign_id_to_enroll = active_campaigns[0]['id'] # Use first active one
                    logger.info(f"Enrolling Lead ID {lead_id} into Campaign ID: {campaign_id_to_enroll}")
                    enroll_status_record = database.enroll_lead_in_campaign(lead_id, campaign_id_to_enroll, organization_id)
                    if enroll_status_record:
                        logger.info(f"Successfully created campaign enrollment record (ID: {enroll_status_record.get('id')}) for Lead ID: {lead_id}")
                        campaign_enrolled = True
                        database.update_lead_partial(lead_id, organization_id, {"crm_status": "Campaign Active"})
                    else: # Enrollment failed (e.g., already enrolled)
                        logger.error(f"Failed to create campaign enrollment record for Lead ID: {lead_id}.")
                        database.update_lead_partial(lead_id, organization_id, {"crm_status": "Enrollment Failed"})
                else:
                    logger.warning(f"No active campaigns found for Org {organization_id}. Cannot enroll lead {lead_id}.")
                    database.update_lead_partial(lead_id, organization_id, {"crm_status": "No Active Campaign"})
            except Exception as enroll_err:
                 logger.error(f"Error during campaign enrollment for Lead ID {lead_id}: {enroll_err}", exc_info=True)
                 database.update_lead_partial(lead_id, organization_id, {"crm_status": "Enrollment Error"})


        logger.info(f"Finished processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        return {
            "email": initial_lead_dict.get("email"),
            "lead_id": lead_id,
            "status": "processed",
            "qualified": is_qualified,
            "match_score": match_score,
            "email_crafted": bool(generated_email_content),
            "campaign_enrolled": campaign_enrolled
            }

    # --- Keep run_pipeline method ---
    def run_pipeline(self, leads_input: List[Dict], organization_id: int) -> List[Dict]:
        """Processes a list of lead dictionaries for a specific organization."""
        # ... (Existing implementation calling process_single_lead) ...
        pass

    # --- run_full_workflow method REMOVED ---
