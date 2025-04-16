from fastapi import APIRouter
from typing import List
from app.schemas import LeadData
from app.agents.leadworkflow import LeadWorkflowAgent
from app.db.database import get_all_leads

router = APIRouter(prefix="/lead", tags=["Lead Workflow"])
agent = LeadWorkflowAgent()

@router.post("/process")
async def process_leads(leads: List[LeadData]):
    processed = agent.run_pipeline(leads)
    return {"status": "success", "processed_leads": processed}

@router.get("/all")
def get_leads():
    return get_all_leads()
