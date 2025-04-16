from typing import List, Dict
from schemas import LeadData

class ICPMatcherAgent:
    def __init__(self):
        self.icp_criteria = {
            "title_keywords": ["CTO", "CIO", "Head of IT", "VP Engineering", "Director IT"],
            "min_company_size": 50  # Simulated
        }

    def match_leads(self, leads: List[LeadData]) -> List[Dict]:
        scored_leads = []

        for lead in leads:
            score = 0
            reason = []

            # Match title
            if any(keyword.lower() in lead.title.lower() for keyword in self.icp_criteria["title_keywords"]):
                score += 50
                reason.append("Matched title")

            # Simulated company size match
            # In reality, this could come from enrichment
            fake_company_size = 100
            if fake_company_size >= self.icp_criteria["min_company_size"]:
                score += 30
                reason.append("Matched company size")

            scored_leads.append({
                **lead.dict(),
                "icp_score": score,
                "match_reason": reason
            })

        return scored_leads
