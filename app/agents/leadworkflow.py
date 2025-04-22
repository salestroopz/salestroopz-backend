# app/agents/leadworkflow.py

from typing import List, Dict, Any
# --- Removed ICPRequest from this import ---
from app.schemas import LeadInput, LeadResponse # Assuming LeadResponse might be useful internally
from pydantic import BaseModel # Import BaseModel for isinstance check

# Import other agents and utilities
from app.agents.leadenrichment import LeadEnrichmentAgent
from app.agents.icp_matcher import ICPMatcherAgent
# from app.agents.crmagent import CRMConnectorAgent
from app.agents.appointment import AppointmentAgent # Needs org_id?
from app.utils.logger import logger

# --- DATABASE IMPORT ---
from app.db import database

class LeadWorkflowAgent:
    def __init__(self):
        self.enrichment_agent = LeadEnrichmentAgent()
        self.matcher_agent = ICPMatcherAgent()
        # self.crm_agent = CRMConnectorAgent()
        # self.appointment_agent = AppointmentAgent()
        logger.info("LeadWorkflowAgent initialized.")

    def process_single_lead(self, initial_lead_dict: dict, organization_id: int) -> Dict[str, Any]:
        """
        Enriches, matches, and saves a SINGLE lead for a specific organization.
        Handles CRM push and appointment steps (conceptually).
        Returns processing status/results for this lead.
        """
        logger.info(f"Processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        final_save_data = initial_lead_dict.copy()

        # 1. Enrich Lead
        try:
            # Pass org_id if enrich needs it: enriched_dict = self.enrichment_agent.enrich(initial_lead_dict, organization_id)
            enriched_dict = self.enrichment_agent.enrich(initial_lead_dict)
            final_save_data.update(enriched_dict)
            logger.debug(f"Enriched lead {initial_lead_dict.get('email')}")
        except Exception as enrich_err:
            logger.error(f"Enrichment failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {enrich_err}", exc_info=True)

        # 2. Match Lead against ICP
        match_score = 0.0 # Default score if matching fails
        is_qualified = False
        try:
            # Pass org_id for tenant-specific ICP lookup
            match_score = self.matcher_agent.match(final_save_data, organization_id=organization_id)
            is_qualified = match_score >= 0.7 # Example threshold
            logger.info(f"Lead {initial_lead_dict.get('email')} matched score: {match_score:.2f}, Qualified: {is_qualified}")
            final_save_data['matched'] = 1 if is_qualified else 0
            # Save the score itself, maybe more useful than just the reason string
            final_save_data['reason'] = f"ICP Match Score: {match_score:.2f}"
        except Exception as match_err:
             logger.error(f"Matching failed for {initial_lead_dict.get('email')} (Org: {organization_id}): {match_err}", exc_info=True)
             final_save_data['matched'] = 0
             final_save_data['reason'] = f"Matching Error: {match_err}"

        # 3. CRM Push Placeholder
        crm_pushed = False
        if is_qualified:
            # ... (keep placeholder CRM logic) ...
            final_save_data['crm_status'] = "Pushed (Simulated)"

        # 4. Appointment Confirmation Placeholder
        appointment_confirmed = False
        if is_qualified:
            # ... (keep placeholder Appointment logic) ...
            final_save_data['appointment_confirmed'] = 1 # Simulate success

        # 5. Save Final Result to Database
        try:
            database.save_lead(final_save_data, organization_id=organization_id)
            logger.debug(f"Saved lead {final_save_data.get('email')} for Org ID {organization_id} to DB.")
        except Exception as db_err:
            logger.error(f"Failed to save lead {final_save_data.get('email')} (Org: {organization_id}) to DB: {db_err}", exc_info=True)
            return {"email": initial_lead_dict.get("email"), "status": "error", "detail": f"DB Save Failed: {db_err}"}

        logger.info(f"Finished processing lead: {initial_lead_dict.get('email')} for Org ID: {organization_id}")
        return {
            "email": initial_lead_dict.get("email"),
            "status": "processed",
            "qualified": is_qualified,
            "match_score": match_score,
            "crm_pushed": crm_pushed,
            "appointment_confirmed": appointment_confirmed
            }

    def run_pipeline(self, leads_input: List[Dict], organization_id: int) -> List[Dict]:
        """
        Processes a list of lead dictionaries for a specific organization
        by calling process_single_lead for each.
        """
        logger.info(f"Running pipeline for {len(leads_input)} leads for Org ID: {organization_id}")
        results = []
        for lead_item in leads_input: # Use different variable name
             # Ensure input is a dictionary
             if isinstance(lead_item, BaseModel):
                 lead_data = lead_item.dict(exclude_unset=True)
             elif isinstance(lead_item, dict):
                 lead_data = lead_item
             else:
                 logger.warning(f"Skipping invalid item in pipeline input (not dict or Pydantic model): {type(lead_item)}")
                 results.append({"input": str(lead_item), "status": "skipped", "detail": "Invalid input format"})
                 continue

             if not lead_data.get('email'):
                 logger.warning(f"Skipping lead in pipeline due to missing email: {lead_data.get('name')}")
                 results.append({"email": None, "status": "skipped", "detail": "Missing email"})
                 continue

             try:
                 result = self.process_single_lead(lead_data, organization_id=organization_id)
                 results.append(result)
             except Exception as e:
                 logger.error(f"Pipeline error processing lead {lead_data.get('email')} for Org {organization_id}: {e}", exc_info=True)
                 results.append({"email": lead_data.get("email"), "status": "error", "detail": str(e)})
        logger.info(f"Pipeline finished for Org ID: {organization_id}. Results count: {len(results)}.")
        return results

    # --- run_full_workflow method REMOVED ---
        else:
            logger.info(f"No initial leads fetched for full workflow (Org: {organization_id}).")
            return {"status": "Full workflow run", "detail": "No initial leads fetched based on ICP.", "results": []}

