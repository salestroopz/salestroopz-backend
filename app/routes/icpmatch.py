from fastapi import APIRouter
from typing import List
from app.schemas import LeadData
from app.agents.icp_matcher import ICPMatcherAgent

router = APIRouter(prefix="/lead", tags=["ICP Matching"])
agent = ICPMatcherAgent()

@router.post("/match")
async def match_leads_to_icp(leads: List[LeadInput]):
    scored_leads = agent.match_leads(leads)
    return {"status": "success", "scored_leads": scored_leads}
