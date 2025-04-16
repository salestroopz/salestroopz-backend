from fastapi import APIRouter
from app.routes.schemas import LeadEnrichmentRequest
from app.agents.leadenrichment import LeadEnrichmentAgent

router = APIRouter()

@router.post("/enrich-lead")
def enrich_lead(data: LeadEnrichmentRequest):
    agent = LeadEnrichmentAgent()
    enriched = agent.enrich_lead(data)
    return enriched
