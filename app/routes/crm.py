# app/routers/crm.py

from fastapi import APIRouter
from typing import List
from app.agents.crm import CRMConnectorAgent, LeadData

router = APIRouter()

@router.post("/push-leads")
def push_leads_to_crm(leads: List[LeadData]):
    crm_agent = CRMConnectorAgent()
    return crm_agent.push_leads(leads)
