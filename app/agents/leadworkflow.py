from typing import List
from app.schemas import LeadData
from app.agents.leadenrichment import LeadEnrichmentAgent
from app.agents.icp_matcher import ICPMatcherAgent
from app.agents.crmagent import CRMConnectorAgent
from app.utils.logger import logger
from app.agents.appointment import AppointmentAgent
from app.db.sqlhelper import save_lead_to_db


class LeadWorkflowAgent:
    def __init__(self):
        self.enrichment_agent = LeadEnrichmentAgent()
        self.matcher_agent = ICPMatcherAgent()
        self.crm_agent = CRMConnectorAgent()
        self.appointment_agent = AppointmentAgent()

    def process_leads(self, leads: List[LeadData]):
        logger.info("Starting full lead generation workflow")

        # Step 1: Enrich the leads
        enriched_leads = self.enrichment_agent.enrich(leads)
        logger.info("Lead enrichment completed")

        # Step 2: Match leads against ICP
        matched_results = self.matcher_agent.match(enriched_leads)
        logger.info(f"Matched leads: {len(matched_results)}")

        # Step 3: Filter qualified leads
        qualified = [lead for lead, score in matched_results if score >= 0.7]
        logger.info(f"{len(qualified)} leads qualified based on matching score")

        # Step 4: Push to CRM
        logger.info("Pushing qualified leads to CRM...")
        crm_response = self.crm_agent.push_leads(qualified)
        logger.info("Leads successfully pushed to CRM")

        # Step 5: Confirm appointments
        appointment_statuses = self.appointment_agent.confirm_appointments(qualified)
        logger.info(f"Confirmed {len(appointment_statuses)} appointments.")

        # Step 6: Save each lead result
        for lead, score in matched_results:
            lead_dict = lead.dict()
            lead_dict["match_score"] = score
            lead_dict["qualified"] = score >= 0.7
            save_lead_to_db(lead_dict)

        logger.info("Workflow completed successfully")

        return {
            "qualified_count": len(qualified),
            "crm_status": crm_response,
            "appointments": [status.dict() for status in appointment_statuses],
            "detailed_scores": [
                {"lead": lead.dict(), "score": score} for lead, score in matched_results
            ]
        }


