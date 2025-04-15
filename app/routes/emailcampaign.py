# app/routes/emailcampaign.py

from fastapi import APIRouter
from app.agents import emailcampaign
from app.agents.emailcampaign import CampaignRequest

router = APIRouter()

@router.post("/create_campaign")
def create_campaign(request: CampaignRequest):
    return emailcampaign.generate_campaign(request)
