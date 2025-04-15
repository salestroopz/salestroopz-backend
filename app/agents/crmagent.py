# app/agents/crmagent.py

from typing import Dict
from datetime import datetime

# Temporary in-memory CRM store (can be replaced with DB or CRM API)
crm_data: Dict[str, Dict] = {}

def update_lead_status(email: str, status: str, notes: str = "") -> Dict:
    crm_data[email] = {
        "status": status,
        "notes": notes,
        "last_updated": datetime.utcnow().isoformat()
    }
    return {"message": "Lead status updated", "data": crm_data[email]}

def get_lead_status(email: str) -> Dict:
    if email in crm_data:
        return crm_data[email]
    else:
        return {"message": "Lead not found", "data": {}}

def list_all_leads() -> Dict:
    return crm_data
