from fastapi import APIRouter
from app.schemas import LeadEnrichmentRequest
from app.agents.leadenrichment import LeadEnrichmentAgent
from typing import Any, List, Optional, Dict

router = APIRouter(prefix="/api/v1/leadenrichment", tags=["Lead Enrichment"])

@router.post("/enrich-lead")
def enrich_lead(data: LeadEnrichmentRequest):
    agent = LeadEnrichmentAgent()
    enriched = agent.enrich_lead(data)
    return enriched
