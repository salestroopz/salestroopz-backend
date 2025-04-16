from .schemas import LeadEnrichmentRequest, LeadEnrichmentResponse

class LeadEnrichmentAgent:
    def enrich_lead(self, lead: LeadEnrichmentRequest) -> LeadEnrichmentResponse:
        # Simulated enrichment logic
        enriched_data = {
            "name": lead.name,
            "company": lead.company,
            "title": lead.title or "Head of Growth",
            "email": lead.email or f"{lead.name.lower().replace(' ', '.')}@{lead.company.lower().replace(' ', '')}.com",
            "linkedin_profile": f"https://www.linkedin.com/in/{lead.name.lower().replace(' ', '-')}",
            "company_size": "51-200 employees",
            "industry": "SaaS",
            "location": "San Francisco, CA"
        }
        return LeadEnrichmentResponse(**enriched_data)
