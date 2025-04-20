# app/routes/workflow.py

from fastapi import APIRouter, Depends, HTTPException, status # Added Depends, HTTPException, status
from typing import List # <--- IMPORT List FROM TYPING

# Import schemas needed for this file
from app.schemas import ICPRequest, LeadResponse, UserPublic # Added LeadResponse, UserPublic

# Import agents and dependencies
from app.agents.leadworkflow import LeadWorkflowAgent
from app.auth.dependencies import get_current_user # Import the auth dependency

# --- DATABASE IMPORT: CHOOSE ONE SOURCE OF TRUTH ---
# Option A: Use the multi-tenant database.py (RECOMMENDED for Phase 0+)
from app.db import database
# Option B: Use the old sqlhelper (If you MUST keep old functionality temporarily)
# from app.db.sqlhelper import get_all_leads as get_all_leads_sqlhelper # Rename if using both temporarily

# --- Router Definition ---
# Define prefix and tags here for consistency (RECOMMENDED)
router = APIRouter(
    prefix="/api/v1/workflow", # Example prefix for this specific workflow file
    tags=["Lead Workflow (Original)"] # Example Tag
)

# === Existing /full-cycle endpoint ===
# Note: This probably needs to be updated for multi-tenancy later
@router.post("/full-cycle")
def run_full_cycle_workflow(icp: ICPRequest):
    """Runs the original full workflow based on ICPRequest."""
    # TODO: Update this endpoint for multi-tenancy (needs user context)
    print("Received request for /full-cycle")
    agent = LeadWorkflowAgent()
    # Assuming agent.run_full_workflow needs update for multi-tenancy too
    return agent.run_full_workflow(icp)

# === CORRECTED Multi-Tenant /leads endpoint ===
# Remove the old /leads definition entirely
@router.get("/leads", response_model=List[LeadResponse]) # Corrected usage of List and LeadResponse
def list_tenant_leads(current_user: UserPublic = Depends(get_current_user)): # Renamed function for clarity
    """
    Lists leads currently saved in the database FOR THE CURRENT USER'S ORGANIZATION.
    Requires authentication. Uses the multi-tenant database functions.
    """
    print(f"Received request for /leads for org: {current_user.organization_id}")
    try:
        # Use the get_all_leads function from the imported database module
        leads = database.get_all_leads(organization_id=current_user.organization_id)
        return leads
    except Exception as e:
        # Add error handling in case database call fails
        print(f"Error fetching leads for org {current_user.organization_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve leads.")
