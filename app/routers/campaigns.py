# app/routers/campaigns.py (New File)

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

# Import project modules
from app.schemas import (
    CampaignInput, CampaignResponse, CampaignStepInput, CampaignStepResponse, UserPublic
)
from app.db import database
from app.auth.dependencies import get_current_user

# Define Router
router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["Campaign Management"]
)

# --- Campaign Endpoints ---

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_new_campaign(
    campaign_data: CampaignInput,
    current_user: UserPublic = Depends(get_current_user)
):
    """Creates a new email campaign definition for the organization."""
    org_id = current_user.organization_id
    print(f"API: Creating campaign '{campaign_data.name}' for Org ID: {org_id}")

    # Extract campaign core data and potential steps
    steps_data = campaign_data.steps
    campaign_core_data = campaign_data.dict(exclude={'steps'}) # Get campaign fields only

    # Create the main campaign record
    created_campaign = database.create_campaign(
        organization_id=org_id,
        name=campaign_core_data['name'], # Name is required by schema
        description=campaign_core_data.get('description'),
        is_active=campaign_core_data.get('is_active', True)
    )
    if not created_campaign:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create campaign.")

    campaign_id = created_campaign['id']
    created_steps = []

    # If steps were provided in the input, create them now
    if steps_data:
        print(f"API: Creating {len(steps_data)} steps for Campaign ID: {campaign_id}")
        for step_input in steps_data:
            step_dict = step_input.dict()
            created_step = database.create_campaign_step(
                campaign_id=campaign_id,
                organization_id=org_id,
                step_number=step_dict['step_number'], # Required by schema
                delay_days=step_dict.get('delay_days', 1),
                subject=step_dict.get('subject_template'),
                body=step_dict.get('body_template'),
                is_ai=step_dict.get('is_ai_crafted', False)
            )
            if created_step:
                 # Fetch full step data if needed, or just use input + ID
                 created_steps.append(database.get_campaign_step_by_id(created_step['id'], org_id) or {})
            else:
                # Handle step creation error - maybe rollback campaign creation?
                # For now, log and potentially raise error or return partial success
                print(f"API WARNING: Failed to create step number {step_dict.get('step_number')} for campaign {campaign_id}")
                # Consider cleanup or raising an error

    # Fetch full campaign data and potentially add steps to response
    final_campaign_data = database.get_campaign_by_id(campaign_id, org_id)
    if final_campaign_data:
         final_campaign_data["steps"] = created_steps # Attach created steps
         return final_campaign_data
    else: # Should not happen if creation succeeded but as fallback
         raise HTTPException(status_code=500, detail="Campaign created but could not be retrieved.")


@router.get("/", response_model=List[CampaignResponse])
def list_organization_campaigns(
    active_only: bool = True,
    current_user: UserPublic = Depends(get_current_user)
):
    """Lists email campaigns for the current user's organization."""
    print(f"API: Listing campaigns for Org ID: {current_user.organization_id} (Active: {active_only})")
    campaigns = database.get_campaigns_by_organization(current_user.organization_id, active_only)
    return campaigns

@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_single_campaign(
    campaign_id: int,
    include_steps: bool = True, # Query param to optionally include steps
    current_user: UserPublic = Depends(get_current_user)
):
    """Gets a specific campaign by ID, optionally including its steps."""
    print(f"API: Getting campaign ID {campaign_id} for Org ID: {current_user.organization_id}")
    campaign = database.get_campaign_by_id(campaign_id, current_user.organization_id)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    if include_steps:
        campaign["steps"] = database.get_steps_for_campaign(campaign_id, current_user.organization_id)

    return campaign


# --- Campaign Step Endpoints ---

@router.post("/{campaign_id}/steps/", response_model=CampaignStepResponse, status_code=status.HTTP_201_CREATED)
def add_campaign_step(
    campaign_id: int,
    step_data: CampaignStepInput,
    current_user: UserPublic = Depends(get_current_user)
):
    """Adds a new step to an existing campaign."""
    org_id = current_user.organization_id
    print(f"API: Adding step {step_data.step_number} to Campaign {campaign_id} for Org {org_id}")
    # Verify campaign belongs to user's org first
    campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not campaign:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    step_dict = step_data.dict()
    created_step = database.create_campaign_step(
        campaign_id=campaign_id,
        organization_id=org_id,
        # Get data from step_dict
        step_number=step_dict['step_number'],
        delay_days=step_dict.get('delay_days', 1),
        subject=step_dict.get('subject_template'),
        body=step_dict.get('body_template'),
        is_ai=step_dict.get('is_ai_crafted', False)
    )
    if not created_step or not created_step.get("id"):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create campaign step.")

    # Fetch the full step data to return
    full_step_data = database.get_campaign_step_by_id(created_step['id'], org_id)
    if not full_step_data:
         raise HTTPException(status_code=500, detail="Step created but could not be retrieved.")

    return full_step_data


@router.get("/{campaign_id}/steps/", response_model=List[CampaignStepResponse])
def list_campaign_steps(
    campaign_id: int,
    current_user: UserPublic = Depends(get_current_user)
):
    """Lists all steps for a specific campaign."""
    org_id = current_user.organization_id
    print(f"API: Listing steps for Campaign {campaign_id}, Org {org_id}")
    # Verify campaign belongs to user's org
    campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not campaign:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    steps = database.get_steps_for_campaign(campaign_id, org_id)
    return steps

# --- Add PUT / DELETE endpoints for campaigns and steps as needed ---
