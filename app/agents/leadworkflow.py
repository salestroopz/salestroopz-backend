# app/agents/leadworkflow.py

from typing import List, Dict, Any # Ensure Dict, Any are imported
from app.schemas import LeadInput, LeadResponse # Assuming LeadResponse might be useful internally
from app.agents.leadenrichment import LeadEnrichmentAgent
from app.agents.icp_matcher import ICPMatcherAgent
# from app.agents.crmagent import CRMConnectorAgent # Let's assume CRM logic is separate or needs org_id too
from app.agents.appointment import AppointmentAgent # Needs org_id?
from app.utils.logger import logger # Keep your logger

# --- DATABASE IMPORT: Use the consolidated, multi-tenant version ---
from app.db import database # Import the module

class LeadWorkflowAgent:
    def __init__(self):
        # Instantiate dependent agents
        # These agents might ALSO need to be org-aware if they access tenant-specific data/config
        self.enrichment_agent = LeadEnrichmentAgent()
        self.matcher_agent = ICPMatcherAgent()
        # self.crm_agent = CRMConnectorAgent() # How will this get org-specific API keys? Postponed for now.
        # self.appointment_agent = AppointmentAgent() # How will this get org-specific settings? Postponed for now.
        logger.info("LeadWorkflowAgent initialized.")


    # --- Renamed and Modified for Multi-Tenancy & Per-Lead Processing ---
    # This method now processes a single lead dict, intended to be called per lead
    def process_single_lead(self, initial_lead_dict: dict, organization_id: int) -> Dict[str, Any]:
        """
        Enriches, matches, and saves a SINGLE lead for a specific organization.
        Handles CRM push and appointment steps (conceptually).
        Returns processing status/results for this lead.
        """
        logger.info(f"Processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        final_save_data = initial_lead_dict.copy() # Start building the data to save

        # 1. Enrich Lead (Enrichment agent might need org_id if it uses specific API keys/DB)
        try:
            # Assuming enrich method takes one lead dict
            # Pass org_id if enrich needs it: enriched_lead_dict = self.enrichment_agent.enrich(initial_lead_dict, organization_id)
            enriched_lead_dict = self.enrichment_agent.enrich(initial_lead_dict)
            final_save_data.update(enriched_lead_dict) # Update with enriched data
            logger.debug(f"Enriched lead {initial_lead_dict.get('email')}")
        except Exception as enrich_err:
            logger.error(f"Enrichment failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {enrich_err}")
            # Decide if you want to proceed without enrichment or stop
            # For now, we proceed with original data + error note

        # 2. Match Lead against ICP (Matcher agent might need org_id if ICP definitions are tenant-specific)
        match_score = 0.7 # Default score if matching fails or skipped
        is_qualified = False
        try:
            # Assuming match method takes one lead dict (now potentially enriched)
            # Pass org_id if match needs it: match_score = self.matcher_agent.match(final_save_data, organization_id)
            match_score = self.matcher_agent.match(final_save_data) # Assuming it returns a score
            is_qualified = match_score >= 0.7 # Example threshold
            logger.info(f"Lead {initial_lead_dict.get('email')} matched score: {match_score:.2f}, Qualified: {is_qualified}")
            final_save_data['matched'] = 1 if is_qualified else 0
            final_save_data['reason'] = f"Match Score: {match_score:.2f}" # Example reason
        except Exception as match_err:
             logger.error(f"Matching failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {match_err}")
             final_save_data['matched'] = 0
             final_save_data['reason'] = f"Matching Error: {match_err}"


        # 3. CRM Push (if qualified)
        # This needs significant multi-tenant rework (API keys per org) - Placeholder
        crm_pushed = False
        if is_qualified:
            try:
                logger.info(f"Attempting CRM push for qualified lead {initial_lead_dict.get('email')} (Org: {organization_id})...")
                # crm_response = self.crm_agent.push_single_lead(final_save_data, organization_id) # Needs org_id for API keys/endpoint
                # if crm_response.get("success"): crm_pushed = True
                crm_pushed = True # Placeholder for success
                final_save_data['crm_status'] = "Pushed" # Example status
                logger.info(f"CRM push simulated for {initial_lead_dict.get('email')}")
            except Exception as crm_err:
                 logger.error(f"CRM push failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {crm_err}")
                 final_save_data['crm_status'] = "Push Failed"

        # 4. Appointment Confirmation (if qualified/pushed?)
        # Needs multi-tenant rework (email settings per org) - Placeholder
        appointment_confirmed = False
        if is_qualified: # Or maybe 'if crm_pushed:'?
            try:
                logger.info(f"Attempting Appointment confirmation for {initial_lead_dict.get('email')} (Org: {organization_id})...")
                # appt_status = self.appointment_agent.confirm_single_appointment(final_save_data, organization_id) # Needs org_id
                # if appt_status == AppointmentStatus.CONFIRMED: appointment_confirmed = True
                appointment_confirmed = True # Placeholder for success
                final_save_data['appointment_confirmed'] = 1 if appointment_confirmed else 0
                logger.info(f"Appointment confirmation simulated for {initial_lead_dict.get('email')}")
            except Exception as appt_err:
                 logger.error(f"Appointment confirmation failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {appt_err}")
                 final_save_data['appointment_confirmed'] = 0


        # 5. Save Final Result to Database (using the correct function)
        try:
            # --- Use the correct database function and pass organization_id ---
            database.save_lead(final_save_data, organization_id=organization_id)
            logger.debug(f"Saved lead {final_save_data.get('email')} for Org ID {organization_id} to DB.")
        except Exception as db_err:
            logger.error(f"Failed to save lead {final_save_data.get('email')} (Org: {organization_id}) to DB: {db_err}")
            # Decide how to handle DB save failure (e.g., raise exception, return error status)
            return {"email": initial_lead_dict.get("email"), "status": "error", "detail": f"DB Save Failed: {db_err}"}

        logger.info(f"Finished processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        # Return status for this specific lead
        return {
            "email": initial_lead_dict.get("email"),
            "status": "processed",
            "qualified": is_qualified,
            "match_score": match_score,
            "crm_pushed": crm_pushed, # Placeholder status
            "appointment_confirmed": appointment_confirmed # Placeholder status
            }

    # --- Method to process a LIST of leads (calls process_single_lead) ---
    def run_pipeline(self, leads_input: List[Dict], organization_id: int) -> List[Dict]:
        """
        Processes a list of lead dictionaries for a specific organization
        by calling process_single_lead for each.
        """
        logger.info(f"Running pipeline for {len(leads_input)} leads for Org ID: {organization_id}")
        results = []
        for lead_dict in leads_input:
             # Convert LeadInput model to dict if necessary, though background task likely already did
             if isinstance(lead_dict, BaseModel): # Check if it's a Pydantic model
                 lead_data = lead_dict.dict(exclude_unset=True) # Convert model to dict
             else:
                 lead_data = lead_dict # Assume it's already a dict

             if not lead_data.get('email'):
                 logger.warning(f"Skipping lead in pipeline due to missing email: {lead_data.get('name')}")
                 results.append({"email": None, "status": "skipped", "detail": "Missing email"})
                 continue

             try:
                 result = self.process_single_lead(lead_data, organization_id=organization_id)
                 results.append(result)
             except Exception as e:
                 logger.error(f"Pipeline error processing lead {lead_data.get('email')} for Org {organization_id}: {e}")
                 results.append({"email": lead_data.get("email"), "status": "error", "detail": str(e)})
        logger.info(f"Pipeline finished for Org ID: {organization_id}. Processed: {len(results)} records.")
        return results # Return list of processing results


    # --- Original Full Cycle method - needs significant multi-tenant update ---
    def run_full_workflow(self, icp: ICPRequest, organization_id: int): # Added organization_id
        """
        [NEEDS REWORK FOR MULTI-TENANCY]
        Fetches leads based on ICP for an org and processes them.
        """
        logger.info(f"Running full workflow for Org ID {organization_id}, ICP: {icp.dict()}")
        # 1. Fetch Leads: How do you get leads based on ICP for a SPECIFIC org?
        #    - Does ICPMatcherAgent handle this? Does it need org_id?
        #    - Do you call an external source (Apollo) using org-specific keys?
        #    - This needs implementation.
        logger.warning(f"Lead fetching for run_full_workflow (Org: {organization_id}) not implemented.")
        initial_leads_dicts = [] # Placeholder

        # 2. Process fetched leads using the pipeline method
        if initial_leads_dicts:
            pipeline_results = self.run_pipeline(initial_leads_dicts, organization_id=organization_id)
            return {"status": "Full workflow run", "results": pipeline_results}
        else:
            logger.info(f"No initial leads fetched for full workflow (Org: {organization_id}).")
            return {"status": "Full workflow run", "detail": "No initial leads fetched based on ICP.", "results": []}

