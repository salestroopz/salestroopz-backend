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

# /opt/render/project/src/app/agents/crmagent.py  <-- Or your local equivalent path
from typing import Dict
from datetime import datetime

# You can keep the old functions if something else still uses them,
# but the class-based approach is generally cleaner.
# We will encapsulate the data and logic within the class.

class CRMConnectorAgent:
    """
    Agent responsible for connecting to and interacting with CRM data.

    This version uses a simple in-memory dictionary to store lead information.
    In a production scenario, this would interact with a database or a CRM API.
    """
    def __init__(self):
        """Initializes the CRM Connector Agent with an empty data store."""
        # Instance variable to hold CRM data, replacing the global one
        self._crm_data: Dict[str, Dict] = {}
        print("CRMConnectorAgent initialized (In-Memory Store).")

    def update_lead_status(self, email: str, status: str, notes: str = "") -> Dict:
        """
        Updates the status, notes, and last updated timestamp for a lead.
        If the lead doesn't exist, it will be created.

        Args:
            email: The email address of the lead (used as the unique identifier).
            status: The new status for the lead.
            notes: Optional notes to add or update for the lead.

        Returns:
            A dictionary containing a status message and the updated lead data.
        """
        self._crm_data[email] = {
            "status": status,
            "notes": notes,
            "last_updated": datetime.utcnow().isoformat()
        }
        # Optional: Add logging here
        # print(f"Updated lead {email}: {self._crm_data[email]}")
        return {"message": "Lead status updated successfully", "data": self._crm_data[email]}

    def get_lead_status(self, email: str) -> Dict:
        """
        Retrieves the current data for a specific lead by email.

        Args:
            email: The email address of the lead to retrieve.

        Returns:
            A dictionary containing a status message and the lead data if found,
            or an empty data dictionary if not found.
        """
        if email in self._crm_data:
            return {"message": "Lead found", "data": self._crm_data[email]}
        else:
            return {"message": "Lead not found", "data": {}}

    def list_all_leads(self) -> Dict:
        """
        Retrieves all leads currently stored in the CRM.

        Returns:
            A dictionary containing a status message and a dictionary
            of all leads (email -> lead data). Returns a copy to prevent
            direct modification of the internal store.
        """
        return {"message": "All leads retrieved", "data": self._crm_data.copy()}

    def clear_all_leads(self):
        """ Clears all leads from the in-memory store (for testing purposes). """
        self._crm_data = {}
        print("In-memory CRM data cleared.")

# == Optional: Keep old functions for backward compatibility? ==
# If you choose to keep them, they could potentially call the methods
# of a default instance, or you might phase them out entirely.
# For now, let's assume you'll switch to using the class instance.

# == How to use this class elsewhere ==
# 1. Create an instance (often done once, e.g., in main.py or via dependency injection):
#    crm_agent = CRMConnectorAgent()
#
# 2. Call methods on the instance:
#    crm_agent.update_lead_status("new@example.com", "New", "Initial entry")
#    lead_info = crm_agent.get_lead_status("new@example.com")
#    all_leads = crm_agent.list_all_leads()
