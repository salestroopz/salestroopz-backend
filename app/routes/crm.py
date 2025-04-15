# app/routers/crm.py

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.agents import crmagent

router = APIRouter(prefix="/crm", tags=["CRM"])

class LeadUpdateRequest(BaseModel):
    email: str
    status: str
    notes: Optional[str] = ""

@router.post("/update")
def update_lead(lead: LeadUpdateRequest):
    return crmagent.update_lead_status(lead.email, lead.status, lead.notes)

@router.get("/get")
def get_lead(email: str):
    return crmagent.get_lead_status(email)

@router.get("/all")
def list_all():
    return crmagent.list_all_leads()
