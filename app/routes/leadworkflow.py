# app/routes/leadworkflow.py

from fastapi import APIRouter, Depends, HTTPException, status # Added Depends, HTTPException, status
from typing import List

# Import schemas needed
from app.schemas import LeadInput, LeadResponse, UserPublic # Added LeadResponse, UserPublic

# Import agent and dependencies
from app.agents.leadworkflow import LeadWorkflowAgent
from app.auth.dependencies import get_current_user # Import the auth dependency

# --- DATABASE IMPORT: Use the module ---
from app.db import database # Import the database module

# --- Router Definition ---
# Define with consistent prefix and tags
router = APIRouter(
    prefix="/api/v1/leadworkflow", # Consistent prefix as used in main.py example
    tags=["Lead Workflow Specific"] # Consistent tag
)

# --- Agent Instantiation ---
# Consider using Depends for agent later if needed
try:
    agent = LeadWorkflowAgent()
except Exception as e:
    print(f"Error instantiating LeadWorkflowAgent in leadworkflow.py: {e}")
    # If agent is critical, maybe raise SystemExit or handle differently
    agent = None


# --- Process Leads Endpoint (Now Multi-Tenant Aware) ---
@router.post("/process", status_code=status.HTTP_202_ACCEPTED) # Added status code
async def process_leads_for_tenant(
    leads: List[LeadInput],
    current_user: UserPublic = Depends(get_current_user) # Require authentication
):
    """
    Processes a list of leads for the current user's organization.
    Requires authentication.
    (Assumes agent processing happens synchronously or agent handles background tasks internally)
    """
    if not agent:
         raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Lead processing agent not available.")

    print(f"Received request to process {len(leads)} leads for org: {current_user.organization_id}")

    # --- IMPORTANT: Update Agent Method Signature ---
    # You MUST modify the agent's `run_pipeline` (or equivalent) method
    # to accept the organization_id and pass it down to `save_lead_result`.
    # Example call (adjust based on your actual agent method):
    try:
        # Assuming run_pipeline now takes organization_id
        processed_results = agent.run_pipeline(leads, organization_id=current_user.organization_id)
        # The structure of processed_results depends on what your agent returns
        return {"status": "processing initiated/completed (depends on agent logic)", "detail": processed_results}
    except TypeError as te:
        # Catch if run_pipeline doesn't accept organization_id yet
        if "organization_id" in str(te):
             print(f"ERROR: LeadWorkflowAgent method needs update to accept organization_id. Error: {te}")
             raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Agent processing logic needs update for multi-tenancy.")
        else:
            print(f"Error processing leads: {te}")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during lead processing.")
    except Exception as e:
        print(f"Unexpected error processing leads for org {current_user.organization_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to process leads.")


# --- Get Leads Endpoint (Now Multi-Tenant Aware) ---
# Renamed from /all to / to match the prefix pattern (access at /api/v1/leadworkflow/)
# Or keep /all if preferred (access at /api/v1/leadworkflow/all)
@router.get("/", response_model=List[LeadResponse]) # Changed path, added response_model
def get_leads_for_tenant(current_user: UserPublic = Depends(get_current_user)): # Require authentication
    """
    Gets all leads associated with the current user's organization.
    Requires authentication.
    """
    print(f"Received request to get leads for org: {current_user.organization_id}")
    try:
        # Use the correct, tenant-aware database function
        leads = database.get_leads_by_organization(organization_id=current_user.organization_id)
        return leads
    except Exception as e:
        print(f"Error fetching leads for org {current_user.organization_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve leads.")
