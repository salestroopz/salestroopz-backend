# app/routers/campaigns.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

# Import project modules
from app.schemas import (
    CampaignInput, CampaignResponse, CampaignStepInput, CampaignStepResponse, UserPublic
)
from app.db import database
from app.auth.dependencies import get_current_user
from app.utils.logger import logger # Assuming logger is setup

# Define Router
router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["Campaign Management"]
)

# --- Campaign Endpoints ---

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_new_campaign(
    campaign_data: CampaignInput, # CampaignInput schema needs optional icp_id
    current_user: UserPublic = Depends(get_current_user)
):
    """Creates a new email campaign definition for the organization, optionally linking an ICP."""
    org_id = current_user.organization_id
    logger.info(f"API: Creating campaign '{campaign_data.name}' for Org ID: {org_id}, ICP ID: {campaign_data.icp_id}")

    # --- Optional: Validate icp_id if provided ---
    if campaign_data.icp_id is not None:
        icp = database.get_icp_by_id(icp_id=campaign_data.icp_id, organization_id=org_id)
        if not icp:
            logger.warning(f"API: ICP ID {campaign_data.icp_id} not found for Org ID {org_id} during campaign creation.")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ICP with ID {campaign_data.icp_id} not found for this organization."
            )
        logger.info(f"API: Validated ICP ID {campaign_data.icp_id} belongs to Org {org_id}.")


    # Extract campaign core data (including icp_id now)
    steps_data = campaign_data.steps
    campaign_core_data = campaign_data.dict(exclude={'steps'}) # Gets name, description, is_active, icp_id

    # Create the main campaign record using the updated database function
    created_campaign = database.create_campaign(
        organization_id=org_id,
        name=campaign_core_data['name'],
        description=campaign_core_data.get('description'),
        is_active=campaign_core_data.get('is_active', True),
        icp_id=campaign_core_data.get('icp_id') # Pass icp_id
    )
    if not created_campaign:
         logger.error(f"API Error: Failed to create campaign '{campaign_data.name}' for Org ID {org_id}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create campaign.")

    campaign_id = created_campaign['id']
    created_steps = []

    # Create steps if provided
    if steps_data:
        logger.info(f"API: Creating {len(steps_data)} steps for Campaign ID: {campaign_id}")
        for step_input in steps_data:
            step_dict = step_input.dict()
            # Pass org_id to step creation as well
            created_step = database.create_campaign_step(
                campaign_id=campaign_id,
                organization_id=org_id, # Ensure org_id is passed
                step_number=step_dict['step_number'],
                delay_days=step_dict.get('delay_days', 1),
                subject=step_dict.get('subject_template'),
                body=step_dict.get('body_template'),
                is_ai=step_dict.get('is_ai_crafted', False),
                follow_up_angle=step_dict.get('follow_up_angle') # Add new field if schema supports it
            )
            if created_step and created_step.get('id'):
                 # Fetch full step data if needed, or just use input + ID
                 full_step = database.get_campaign_step_by_id(created_step['id'], org_id)
                 if full_step: created_steps.append(full_step)
                 else: logger.warning(f"API: Step {step_dict['step_number']} created but failed to fetch for Camp {campaign_id}")
            else:
                logger.error(f"API ERROR: Failed to create step number {step_dict.get('step_number')} for campaign {campaign_id}")
                # Decide on error handling: rollback campaign? return partial success?
                # For now, just log the error for the step.

    # Fetch final campaign data (which now includes icp_id and icp_name via JOIN)
    final_campaign_data = database.get_campaign_by_id(campaign_id, org_id)
    if final_campaign_data:
         final_campaign_data["steps"] = created_steps # Attach successfully created steps
         logger.info(f"API: Successfully created Campaign ID {campaign_id} with {len(created_steps)} steps.")
         return final_campaign_data
    else:
         logger.error(f"API Error: Campaign {campaign_id} created but could not be retrieved.")
         raise HTTPException(status_code=500, detail="Campaign created but could not be retrieved.")


@router.get("/", response_model=List[CampaignResponse])
def list_organization_campaigns(
    active_only: bool = True,
    current_user: UserPublic = Depends(get_current_user)
):
    """Lists email campaigns for the current user's organization (includes associated ICP name)."""
    logger.info(f"API: Listing campaigns for Org ID: {current_user.organization_id} (Active: {active_only})")
    # Database function now returns icp_id and icp_name
    campaigns = database.get_campaigns_by_organization(current_user.organization_id, active_only)
    logger.info(f"API: Found {len(campaigns)} campaigns for Org ID: {current_user.organization_id}")
    return campaigns

@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_single_campaign(
    campaign_id: int,
    include_steps: bool = True, # Query param to optionally include steps
    current_user: UserPublic = Depends(get_current_user)
):
    """Gets a specific campaign by ID (includes associated ICP name), optionally including its steps."""
    logger.info(f"API: Getting campaign ID {campaign_id} for Org ID: {current_user.organization_id}")
    # Database function now returns icp_id and icp_name
    campaign = database.get_campaign_by_id(campaign_id, current_user.organization_id)
    if not campaign:
        logger.warning(f"API: Campaign ID {campaign_id} not found for Org ID: {current_user.organization_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    if include_steps:
        logger.debug(f"API: Fetching steps for campaign ID {campaign_id}")
        campaign["steps"] = database.get_steps_for_campaign(campaign_id, current_user.organization_id)

    logger.info(f"API: Successfully retrieved campaign ID {campaign_id}")
    return campaign

# --- TODO: Implement PUT / DELETE for Campaigns ---
# @router.put("/{campaign_id}", response_model=CampaignResponse) ...
# @router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT) ...


# --- Campaign Step Endpoints ---

@router.post("/{campaign_id}/steps/", response_model=CampaignStepResponse, status_code=status.HTTP_201_CREATED)
def add_campaign_step(
    campaign_id: int,
    step_data: CampaignStepInput, # CampaignStepInput schema needs follow_up_angle if used
    current_user: UserPublic = Depends(get_current_user)
):
    """Adds a new step to an existing campaign."""
    org_id = current_user.organization_id
    logger.info(f"API: Adding step {step_data.step_number} to Campaign {campaign_id} for Org {org_id}")

    # Verify campaign belongs to user's org first
    campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not campaign:
         logger.warning(f"API: Campaign {campaign_id} not found for Org {org_id} when adding step.")
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    step_dict = step_data.dict()
    created_step = database.create_campaign_step(
        campaign_id=campaign_id,
        organization_id=org_id,
        step_number=step_dict['step_number'],
        delay_days=step_dict.get('delay_days', 1),
        subject=step_dict.get('subject_template'),
        body=step_dict.get('body_template'),
        is_ai=step_dict.get('is_ai_crafted', False),
        follow_up_angle=step_dict.get('follow_up_angle') # Add field
    )
    if not created_step or not created_step.get("id"):
        logger.error(f"API Error: Failed to create step {step_data.step_number} for Campaign {campaign_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create campaign step.")

    step_id = created_step['id']
    # Fetch the full step data to return
    full_step_data = database.get_campaign_step_by_id(step_id, org_id)
    if not full_step_data:
         logger.error(f"API Error: Step {step_id} created but could not be retrieved.")
         # Technically step was created, maybe return created_step dict? Or 500?
         raise HTTPException(status_code=500, detail="Step created but could not be retrieved.")

    logger.info(f"API: Successfully added step ID {step_id} to campaign {campaign_id}")
    return full_step_data


@router.get("/{campaign_id}/steps/", response_model=List[CampaignStepResponse])
def list_campaign_steps(
    campaign_id: int,
    current_user: UserPublic = Depends(get_current_user)
):
    """Lists all steps for a specific campaign."""
    org_id = current_user.organization_id
    logger.info(f"API: Listing steps for Campaign {campaign_id}, Org {org_id}")
    # Verify campaign belongs to user's org
    campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not campaign:
         logger.warning(f"API: Campaign {campaign_id} not found for Org {org_id} when listing steps.")
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    steps = database.get_steps_for_campaign(campaign_id, org_id)
    logger.info(f"API: Found {len(steps)} steps for Campaign {campaign_id}")
    return steps

# --- TODO: Add PUT / DELETE endpoints for campaign steps as needed ---
# @router.put("/{campaign_id}/steps/{step_id}", response_model=CampaignStepResponse) ...
# @router.delete("/{campaign_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT) ...
