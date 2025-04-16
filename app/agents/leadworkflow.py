from typing import List
from app.schemas import LeadData
from agents.leadenrichment import LeadEnrichmentAgent
from agents.icp_matcher import ICPMatcherAgent

class LeadWorkflowAgent:
    def __init__(self):
        self.enricher = LeadEnrichmentAgent()
        self.matcher = ICPMatcherAgent()

    def run_pipeline(self, leads: List[LeadData]):
        enriched = self.enricher.enrich_leads(leads)
        scored = self.matcher.match_leads(enriched)
        return scored
