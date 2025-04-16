from typing import List
from app.schemas import LeadData
from app.agents.leadenrichment import LeadEnrichmentAgent
from app.agents.icp_matcher import ICPMatcherAgent
from app.agents.crmagent import CRMConnectorAgent
from db.database import save_lead_result

def process_leads(self, leads: List[LeadData]):
    results = []
    for lead in leads:
        enriched = self.enrichment_agent.enrich(lead)
        match_result = self.icp_agent.match(enriched)
        enriched.match = match_result["matched"]
        enriched.reason = match_result["reason"]
        if enriched.match:
            self.crm_agent.push_leads([enriched])
        lead_dict = enriched.dict()
        lead_dict["match_result"] = match_result
        save_lead_result(lead_dict)
        results.append(lead_dict)
    return results


class LeadWorkflowAgent:
    def __init__(self):
        self.enrichment_agent = LeadEnrichmentAgent()
        self.matcher_agent = ICPMatcherAgent()
        self.crm_agent = CRMConnectorAgent()

    def process_leads(self, leads: List[LeadData]):
        enriched_leads = self.enrichment_agent.enrich(leads)
        matched_results = self.matcher_agent.match(enriched_leads)

        qualified = [lead for lead, score in matched_results if score >= 0.7]
        crm_response = self.crm_agent.push_leads(qualified)

        return {
            "qualified_count": len(qualified),
            "crm_status": crm_response,
            "detailed_scores": [
                {"lead": lead.dict(), "score": score} for lead, score in matched_results
            ]
        }

def process_leads(self, leads: List[LeadData]):
    results = []
    for lead in leads:
        enriched = self.enrichment_agent.enrich(lead)
        match_result = self.icp_agent.match(enriched)
        enriched.match = match_result["matched"]
        enriched.reason = match_result["reason"]
        if enriched.match:
            self.crm_agent.push_leads([enriched])
        lead_dict = enriched.dict()
        lead_dict["match_result"] = match_result
        save_lead_result(lead_dict)
        results.append(lead_dict)
    return results
