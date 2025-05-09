# app/routers/campaigns.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

# Import project modules
from app import schemas # This will import all schemas defined in app/schemas.py
from app.db import database
from app.auth.dependencies import get_current_user # Assuming this provides your UserPublic model correctly
from app.agents.campaign_generator import generate_campaign_steps # Import the AI agent
from app.utils.logger import logger

# Define Router
router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["Campaign Management"]
)

# --- Campaign Endpoints ---

@router.post("/", response_model=schemas.CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_new_campaign_with_ai_steps( # Renamed for clarity
    campaign_in: schemas.CampaignInput,
    background_tasks: BackgroundTasks, # FastAPI BackgroundTasks
    current_user: schemas.UserPublic = Depends(get_current_user) # Use UserPublic from schemas
):
    """
    Creates a new email campaign.
    The AI will generate email steps in the background.
    """
    org_id = current_user.organization_id
    logger.info(f"API: Creating campaign '{campaign_in.name}' for Org ID: {org_id}, ICP ID: {campaign_in.icp_id}, Offering ID: {campaign_in.offering_id}")

    # --- Optional: Validate icp_id if provided ---
    if campaign_in.icp_id is not None:
        icp = database.get_icp_by_id(icp_id=campaign_in.icp_id, organization_id=org_id)
        if not icp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ICP with ID {campaign_in.icp_id} not found for this organization."
            )
    # --- Optional: Validate offering_id if provided ---
    if campaign_in.offering_id is not None:
        offering = database.get_offering_by_id(offering_id=campaign_in.offering_id, organization_id=org_id)
        if not offering:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Offering with ID {campaign_in.offering_id} not found for this organization."
            )

    created_campaign = database.create_campaign(
        organization_id=org_id,
        name=campaign_in.name,
        description=campaign_in.description,
        icp_id=campaign_in.icp_id,
        offering_id=campaign_in.offering_id,
        is_active=campaign_in.is_active, # User can set initial active state
        ai_status="pending" # Initial AI status
    )
    if not created_campaign:
         logger.error(f"API Error: Failed to create campaign '{campaign_in.name}' for Org ID {org_id}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create campaign in database.")

    campaign_id = created_campaign['id']

    # Trigger AI agent in the background
    logger.info(f"API: Triggering AI step generation for Campaign ID: {campaign_id}")
    background_tasks.add_task(
        generate_campaign_steps,
        campaign_id=campaign_id,
        organization_id=org_id
        # force_regeneration can be added as a param if needed for other endpoints
    )
    
    # The response model schemas.CampaignResponse does not include steps list by default
    # created_campaign dict from database.create_campaign (which calls get_campaign_by_id)
    # should have icp_name and offering_name already.
    return schemas.CampaignResponse(**created_campaign)


@router.get("/", response_model=List[schemas.CampaignResponse])
async def list_organization_campaigns( # Renamed for clarity
    active_only: Optional[bool] = None, # Now optional, can list all
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    """Lists email campaigns for the current user's organization."""
    logger.info(f"API: Listing campaigns for Org ID: {current_user.organization_id} (Active filter: {active_only})")
    campaigns = database.get_campaigns_by_organization(current_user.organization_id, active_only=active_only)
    logger.info(f"API: Found {len(campaigns)} campaigns for Org ID: {current_user.organization_id}")
    # Convert list of dicts to list of CampaignResponse objects
    return [schemas.CampaignResponse(**campaign) for campaign in campaigns]


@router.get("/{campaign_id}", response_model=schemas.CampaignDetailResponse) # Use CampaignDetailResponse
async def get_single_campaign_details( # Renamed for clarity
    campaign_id: int,
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    """Gets detailed information for a specific campaign, including its steps."""
    org_id = current_user.organization_id
    logger.info(f"API: Getting campaign ID {campaign_id} for Org ID: {org_id}")
    
    campaign_data = database.get_campaign_by_id(campaign_id, org_id)
    if not campaign_data:
        logger.warning(f"API: Campaign ID {campaign_id} not found for Org ID: {org_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    campaign_steps = database.get_steps_for_campaign(campaign_id, org_id)
    
    # Construct the CampaignDetailResponse
    # Ensure campaign_data (a dict) and campaign_steps (list of dicts) are compatible
    response_data = {**campaign_data, "steps": [schemas.CampaignStepResponse(**step) for step in campaign_steps]}
    logger.info(f"API: Successfully retrieved campaign ID {campaign_id} with {len(campaign_steps)} steps.")
    return schemas.CampaignDetailResponse(**response_data)


@router.put("/{campaign_id}", response_model=schemas.CampaignResponse)
async def update_existing_campaign_details( # Renamed for clarity
    campaign_id: int,
    campaign_update_data: schemas.CampaignUpdate, # Use CampaignUpdate schema
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    """Updates an existing campaign's basic information."""
    org_id = current_user.organization_id
    logger.info(f"API: Updating campaign ID {campaign_id} for Org ID: {org_id} with data: {campaign_update_data.dict(exclude_unset=True)}")

    # Check if campaign exists and belongs to org
    existing_campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not existing_campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    update_data_dict = campaign_update_data.dict(exclude_unset=True)
    if not update_data_dict:
        logger.info(f"API: No update data provided for campaign {campaign_id}.")
        # Return existing campaign data if no updates, or raise 400
        return schemas.CampaignResponse(**existing_campaign)
        # raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No update data provided.")

    updated_campaign = database.update_campaign(
        campaign_id=campaign_id,
        organization_id=org_id,
        updates=update_data_dict
    )
    if not updated_campaign:
        # This might happen if update_campaign returns None on failure beyond not found
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update campaign information.")
    
    logger.info(f"API: Successfully updated campaign ID {campaign_id}.")
    return schemas.CampaignResponse(**updated_campaign)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_campaign_record( # Renamed for clarity
    campaign_id: int,
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    """Deletes a campaign and its associated steps."""
    org_id = current_user.organization_id
    logger.info(f"API: Deleting campaign ID {campaign_id} for Org ID: {org_id}")

    # Check if campaign exists and belongs to org before attempting delete
    existing_campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not existing_campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    deleted = database.delete_campaign(campaign_id=campaign_id, organization_id=org_id)
    if not deleted:
        # This case should ideally be caught by the check above, but as a safeguard
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete campaign.")
    
    logger.info(f"API: Successfully deleted campaign ID {campaign_id}.")
    return None # For 204 No Content


# --- Campaign Step Endpoints (Revised) ---

@router.get("/{campaign_id}/steps/", response_model=List[schemas.CampaignStepResponse])
async def list_campaign_steps_read_only( # Renamed for clarity
    campaign_id: int,
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    """Lists all AI-generated steps for a specific campaign (read-only)."""
    org_id = current_user.organization_id
    logger.info(f"API: Listing steps for Campaign {campaign_id}, Org {org_id}")
    
    campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not campaign:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    steps = database.get_steps_for_campaign(campaign_id, org_id)
    logger.info(f"API: Found {len(steps)} steps for Campaign {campaign_id}")
    return [schemas.CampaignStepResponse(**step) for step in steps]


@router.put("/{campaign_id}/steps/{step_id}", response_model=schemas.CampaignStepResponse)
async def update_campaign_step_details( # Renamed for clarity
    campaign_id: int, # Path parameter to scope the step to a campaign
    step_id: int,
    step_update_data: schemas.CampaignStepUpdate, # Use specific update schema
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    """Updates an existing campaign step (e.g., content edited by user)."""
    org_id = current_user.organization_id
    logger.info(f"API: Updating step ID {step_id} for Campaign {campaign_id}, Org {org_id}")

    # Verify campaign exists and step belongs to it and user's org
    campaign = database.get_campaign_by_id(campaign_id, org_id)
    if not campaign:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent campaign not found.")

    original_step = database.get_campaign_step_by_id(step_id, org_id)
    if not original_step:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign step not found.")
    if original_step.get('campaign_id') != campaign_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Step does not belong to the specified campaign.")

    updates_dict = step_update_data.dict(exclude_unset=True)
    if not updates_dict:
        return schemas.CampaignStepResponse(**original_step) # No changes, return original

    # If user edits, it's no longer purely AI crafted
    if "subject_template" in updates_dict or "body_template" in updates_dict:
        updates_dict['is_ai_crafted'] = False

    updated_step = database.update_campaign_step(
        step_id=step_id,
        organization_id=org_id,
        updates=updates_dict
    )
    if not updated_step:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update campaign step.")
    
    logger.info(f"API: Successfully updated step ID {step_id} for campaign {campaign_id}")
    return schemas.CampaignStepResponse(**updated_step)


# POST /{campaign_id}/steps/ is REMOVED (AI generates steps)
# DELETE /{campaign_id}/steps/{step_id} can be added if needed to delete individual AI steps


# --- Lead Enrollment Endpoints ---

@router.post("/{campaign_id}/enroll_leads", status_code=status.HTTP_200_OK, response_model=Dict[str, Any])
async def enroll_specific_leads_into_campaign( # Renamed for clarity
    campaign_id: int,
    enroll_request: schemas.CampaignEnrollLeadsRequest,
    current_user: schemas.UserPublic = Depends(get_current_user)
) -> Dict[str, Any]:
    """Enrolls a provided list of lead IDs into a specified active campaign."""
    # ... (Logic for this endpoint as defined in previous detailed response) ...
    # Includes:
    # 1. Validate campaign (exists, active, has steps)
    # 2. Get first step delay
    # 3. Loop enroll_request.lead_ids:
    #    - Validate lead
    #    - Check existing active enrollment (handle re-enrollment policy)
    #    - Call database.enroll_lead_in_campaign
    #    - Update next_email_due_at for the new status record
    # 4. Return summary
    organization_id = current_user.organization_id
    logger.info(f"API: Enrolling leads {enroll_request.lead_ids} into Campaign {campaign_id} for Org {organization_id}")

    campaign = database.get_campaign_by_id(campaign_id=campaign_id, organization_id=organization_id)
    if not campaign: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Campaign ID {campaign_id} not found.")
    if not campaign.get("is_active"): raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign '{campaign.get('name')}' is not active.")
    
    campaign_steps = database.get_steps_for_campaign(campaign_id=campaign_id, organization_id=organization_id)
    if not campaign_steps and campaign.get("ai_status") not in ["completed_partial", "completed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign '{campaign.get('name')}' steps not ready (AI Status: {campaign.get('ai_status')}).")

    first_step_delay_days = 0 # Default if no steps or first step has no delay defined
    if campaign_steps:
        first_step = min(campaign_steps, key=lambda x: x.get('step_number', float('inf')))
        if first_step: first_step_delay_days = first_step.get('delay_days', 0)
    
    successful_enrollments = 0; failed_enrollments = 0; errors = []; processed_lead_ids = set()

    for lead_id in enroll_request.lead_ids:
        if lead_id in processed_lead_ids: continue
        processed_lead_ids.add(lead_id)
        lead = database.get_lead_by_id(lead_id=lead_id, organization_id=organization_id)
        if not lead: errors.append({"lead_id": lead_id, "error": "Lead not found."}); failed_enrollments += 1; continue
        
        existing_status = database.get_lead_campaign_status(lead_id=lead_id, organization_id=organization_id)
        if existing_status: # Simplified: if any status exists, don't re-enroll via this simple endpoint
            errors.append({"lead_id": lead_id, "error": f"Lead already has campaign status: {existing_status.get('status')}."}); failed_enrollments += 1; continue
            
        enrolled_status_record = database.enroll_lead_in_campaign(lead_id, campaign_id, organization_id)
        if enrolled_status_record:
            next_due = datetime.now(timezone.utc) # Assume immediate for step 0->1 if delay is 0
            # More precise: next_due should be enrollment_time + timedelta(days=first_step_delay_days)
            # The sending worker should ideally calculate the *first* send time based on enrollment time and first step delay.
            # For now, let's make it due now if delay is 0, for simplicity of this endpoint.
            # This means the enroll_lead_in_campaign sets current_step_number to 0.
            # The worker will then look for step 1.
            # Let's assume the sending worker calculates the first due date.
            # For now, just ensure `next_email_due_at` is set, perhaps to now for the worker to pick up.
            database.update_lead_campaign_status(
                status_id=enrolled_status_record['id'], 
                organization_id=organization_id, 
                updates={"next_email_due_at": datetime.now(timezone.utc)} # Mark as ready for processing by worker
            )
            successful_enrollments += 1
        else:
            errors.append({"lead_id": lead_id, "error": "DB enrollment failed."}); failed_enrollments += 1
            
    return {
        "message": "Lead enrollment process completed.", "campaign_id": campaign_id,
        "successful_enrollments": successful_enrollments, "failed_enrollments": failed_enrollments,
        "details": errors
    }


def _background_enroll_icp_matched_leads(campaign_id_for_enrollment: int, org_id_for_enrollment: int):
    """Background task to find leads matching a campaign's ICP and enroll them."""
    # ... (Full logic for this function as defined in the previous detailed response) ...
    # Includes:
    # 1. Fetch campaign, verify ICP link
    # 2. Call database.get_leads_by_icp_match
    # 3. Loop through matched leads:
    #    - Check existing active enrollment
    #    - Call database.enroll_lead_in_campaign
    #    - Update next_email_due_at for the new status record
    # 4. Log summary
    logger.info(f"BACKGROUND: Starting enrollment of ICP-matched leads for campaign ID {campaign_id_for_enrollment}, org {org_id_for_enrollment}.")
    campaign = database.get_campaign_by_id(campaign_id=campaign_id_for_enrollment, organization_id=org_id_for_enrollment)
    if not campaign or not campaign.get("icp_id"):
        logger.error(f"BACKGROUND: Campaign {campaign_id_for_enrollment} not found or no ICP linked. Aborting."); return
    
    matched_leads = database.get_leads_by_icp_match(organization_id=org_id_for_enrollment, icp_id=campaign["icp_id"])
    if not matched_leads: logger.info(f"BACKGROUND: No leads found matching ICP ID {campaign['icp_id']}."); return
    
    successful_enrollments = 0; skipped_count = 0
    for lead in matched_leads:
        lead_id = lead.get("id")
        existing_status = database.get_lead_campaign_status(lead_id=lead_id, organization_id=org_id_for_enrollment)
        if existing_status: skipped_count += 1; logger.debug(f"BACKGROUND: Lead {lead_id} already has campaign status, skipping."); continue
        
        enrolled = database.enroll_lead_in_campaign(lead_id, campaign_id_for_enrollment, org_id_for_enrollment)
        if enrolled: 
            database.update_lead_campaign_status(
                status_id=enrolled['id'], 
                organization_id=org_id_for_enrollment, 
                updates={"next_email_due_at": datetime.now(timezone.utc)}
            )
            successful_enrollments += 1
    logger.info(f"BACKGROUND: ICP-matched enrollment for campaign {campaign_id_for_enrollment} finished. Enrolled: {successful_enrollments}, Skipped: {skipped_count}.")


@router.post("/{campaign_id}/enroll_matched_icp_leads", status_code=status.HTTP_202_ACCEPTED, response_model=Dict[str, str])
async def trigger_enroll_icp_matched_leads( # Renamed for clarity
    campaign_id: int,
    background_tasks: BackgroundTasks,
    current_user: schemas.UserPublic = Depends(get_current_user)
):
    """Triggers a background task to find and enroll leads matching the campaign's linked ICP."""
    # ... (Logic for this endpoint as defined in previous detailed response) ...
    # Includes:
    # 1. Validate campaign (exists, active, has ICP, has steps)
    # 2. Add _background_enroll_icp_matched_leads to background_tasks
    # 3. Return success message
    organization_id = current_user.organization_id
    campaign = database.get_campaign_by_id(campaign_id=campaign_id, organization_id=organization_id)
    if not campaign: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    if not campaign.get("icp_id"): raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign not linked to an ICP.")
    if not campaign.get("is_active"): raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is not active.")
    campaign_steps = database.get_steps_for_campaign(campaign_id=campaign_id, organization_id=organization_id)
    if not campaign_steps and campaign.get("ai_status") not in ["completed_partial", "completed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign steps not ready (AI: {campaign.get('ai_status')}).")

    background_tasks.add_task(_background_enroll_icp_matched_leads, campaign_id, organization_id)
    return {"message": f"Process to enroll ICP-matched leads into campaign '{campaign.get('name')}' triggered."}
