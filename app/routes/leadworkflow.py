from fastapi import APIRouter
from typing import List
from app.schemas import LeadData
from agents.leadworkflow import LeadWorkflowAgent

router = APIRouter(prefix="/lead", tags=["Lead Workflow"])
agent = LeadWorkflowAgent()

@router.post("/process")
async def process_leads(leads: List[LeadData]):
    processed = agent.run_pipeline(leads)
    return {"status": "success", "processed_leads": processed}
