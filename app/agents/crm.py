from typing import List
from pydantic import BaseModel
from app.utils.logger import logger


class LeadData(BaseModel):
    name: str
    email: str
    company: str
    title: str
    source: str


class CRMConnectorAgent:
    def __init__(self, crm_provider: str = "SimulatedCRM"):
        self.crm_provider = crm_provider

    def push_leads(self, leads: List[LeadData]):
        logger.info(f"Pushing {len(leads)} leads to {self.crm_provider}")
        # Simulated CRM sync logic
        for lead in leads:
            print(f"Pushing {lead.name} to {self.crm_provider}...")
        return {
            "status": "success",
            "message": f"{len(leads)} leads pushed to {self.crm_provider}"
        }
