# app/agents/emailcampaign.py

from pydantic import BaseModel
from typing import List

class EmailTemplate(BaseModel):
    subject: str
    body: str
    delay_days: int  # Days to wait before sending this email

class CampaignRequest(BaseModel):
    campaign_name: str
    templates: List[EmailTemplate]

def generate_campaign(request: CampaignRequest):
    # For now, just return the templates in order as a mock
    return {
        "campaign_name": request.campaign_name,
        "steps": [
            {
                "subject": template.subject,
                "body": template.body,
                "delay_days": template.delay_days
            }
            for template in request.templates
        ]
    }
