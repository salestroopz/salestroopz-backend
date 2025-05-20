# app/routers/campaigns.py

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query # Added Query
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session # <--- IMPORTED Session

# Import project modules
from app.schemas import ( # <--- EXPLICIT SCHEMA IMPORTS
    CampaignResponse, CampaignInput, CampaignUpdate, CampaignDetailResponse,
    CampaignStepResponse, UserPublic, CampaignEnrollLeadsRequest
)
# from app.db import database # Your CRUD functions seem to be here
# For consistency with FastAPI patterns, database functions should accept a 'db' session.
from app.db.database import get_db # For injecting DB session
from app.auth.dependencies import get_current_user
from app.agents.campaign_generator import generate_campaign_steps
from app.utils.logger import logger
# Assuming your CRUD functions are in app.db.database, let's alias it for clarity if needed
from app.db import database as campaign_db_ops # Or import specific functions

# Define Router
router = APIRouter(
    prefix="/api/v1/campaigns",
    tags=["Campaign Management"]
)

# --- Campaign Endpoints ---

@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
async def create_new_campaign_with_ai_steps(
    campaign_in: CampaignInput,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    org_id = current_user.organization_id
    logger.info(f"API: Creating campaign '{campaign_in.name}' for Org ID: {org_id}, ICP ID: {campaign_in.icp_id}, Offering ID: {campaign_in.offering_id}")

    if campaign_in.icp_id is not None:
        icp = campaign_db_ops.get_icp_by_id(db=db, icp_id=campaign_in.icp_id, organization_id=org_id) # Pass db
        if not icp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ICP with ID {campaign_in.icp_id} not found.")
    if campaign_in.offering_id is not None:
        offering = campaign_db_ops.get_offering_by_id(db=db, offering_id=campaign_in.offering_id, organization_id=org_id) # Pass db
        if not offering:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Offering with ID {campaign_in.offering_id} not found.")

    created_campaign_dict = campaign_db_ops.create_campaign( # Pass db
        db=db,
        organization_id=org_id,
        name=campaign_in.name,
        description=campaign_in.description,
        icp_id=campaign_in.icp_id,
        offering_id=campaign_in.offering_id,
        is_active=campaign_in.is_active,
        ai_status="pending"
    )
    if not created_campaign_dict:
         logger.error(f"API Error: Failed to create campaign '{campaign_in.name}' for Org ID {org_id}")
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create campaign.")

    campaign_id = created_campaign_dict['id']
    logger.info(f"API: Triggering AI step generation for Campaign ID: {campaign_id}")
    background_tasks.add_task(
        generate_campaign_steps,
        db_session_factory=get_db, # Pass a way for the background task to get a DB session
        campaign_id=campaign_id,
        organization_id=org_id
    )
    return CampaignResponse(**created_campaign_dict)


@router.get("/", response_model=List[CampaignResponse])
async def list_organization_campaigns(
    active_only: Optional[bool] = Query(None, description="Filter for active campaigns only"), # Use Query
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    logger.info(f"API: Listing campaigns for Org ID: {current_user.organization_id} (Active filter: {active_only})")
    campaigns_data = campaign_db_ops.get_campaigns_by_organization( # Pass db
        db=db,
        organization_id=current_user.organization_id,
        active_only=active_only
    )
    logger.info(f"API: Found {len(campaigns_data)} campaigns for Org ID: {current_user.organization_id}")
    return [CampaignResponse(**campaign) for campaign in campaigns_data]


@router.get("/{campaign_id}", response_model=CampaignDetailResponse)
async def get_single_campaign_details(
    campaign_id: int,
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    org_id = current_user.organization_id
    logger.info(f"API: Getting campaign ID {campaign_id} for Org ID: {org_id}")
    
    campaign_data = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    if not campaign_data:
        logger.warning(f"API: Campaign ID {campaign_id} not found for Org ID: {org_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    campaign_steps_data = campaign_db_ops.get_steps_for_campaign(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    
    response_data = {**campaign_data, "steps": [CampaignStepResponse(**step) for step in campaign_steps_data]}
    logger.info(f"API: Successfully retrieved campaign ID {campaign_id} with {len(campaign_steps_data)} steps.")
    return CampaignDetailResponse(**response_data)


@router.put("/{campaign_id}", response_model=CampaignResponse)
async def update_existing_campaign_details(
    campaign_id: int,
    campaign_update_data: CampaignUpdate,
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    org_id = current_user.organization_id
    logger.info(f"API: Updating campaign ID {campaign_id} for Org ID: {org_id} with data: {campaign_update_data.model_dump(exclude_unset=True)}")

    existing_campaign = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    if not existing_campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    update_data_dict = campaign_update_data.model_dump(exclude_unset=True) # Use model_dump for Pydantic v2
    if not update_data_dict:
        logger.info(f"API: No update data provided for campaign {campaign_id}.")
        return CampaignResponse(**existing_campaign)

    updated_campaign_dict = campaign_db_ops.update_campaign( # Pass db
        db=db,
        campaign_id=campaign_id,
        organization_id=org_id,
        updates=update_data_dict
    )
    if not updated_campaign_dict:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update campaign.")
    
    logger.info(f"API: Successfully updated campaign ID {campaign_id}.")
    return CampaignResponse(**updated_campaign_dict)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_campaign_record(
    campaign_id: int,
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    org_id = current_user.organization_id
    logger.info(f"API: Deleting campaign ID {campaign_id} for Org ID: {org_id}")

    existing_campaign = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    if not existing_campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    deleted = campaign_db_ops.delete_campaign(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    if not deleted:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete campaign.")
    
    logger.info(f"API: Successfully deleted campaign ID {campaign_id}.")
    return None


# --- Campaign Step Endpoints ---
@router.get("/{campaign_id}/steps/", response_model=List[CampaignStepResponse])
async def list_campaign_steps_read_only(
    campaign_id: int,
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    org_id = current_user.organization_id
    logger.info(f"API: Listing steps for Campaign {campaign_id}, Org {org_id}")
    
    campaign = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    if not campaign:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    steps_data = campaign_db_ops.get_steps_for_campaign(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    logger.info(f"API: Found {len(steps_data)} steps for Campaign {campaign_id}")
    return [CampaignStepResponse(**step) for step in steps_data]


@router.put("/{campaign_id}/steps/{step_id}", response_model=CampaignStepResponse)
async def update_campaign_step_details(
    campaign_id: int,
    step_id: int,
    step_update_data: schemas.CampaignStepUpdate, # Explicitly from schemas
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    org_id = current_user.organization_id
    logger.info(f"API: Updating step ID {step_id} for Campaign {campaign_id}, Org {org_id}")

    campaign = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=org_id) # Pass db
    if not campaign:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent campaign not found.")

    original_step_dict = campaign_db_ops.get_campaign_step_by_id(db=db, step_id=step_id, organization_id=org_id) # Pass db
    if not original_step_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign step not found.")
    if original_step_dict.get('campaign_id') != campaign_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Step does not belong to the specified campaign.")

    updates_dict = step_update_data.model_dump(exclude_unset=True) # Use model_dump for Pydantic v2
    if not updates_dict:
        return CampaignStepResponse(**original_step_dict)

    if "subject_template" in updates_dict or "body_template" in updates_dict:
        updates_dict['is_ai_crafted'] = False

    updated_step_dict = campaign_db_ops.update_campaign_step( # Pass db
        db=db,
        step_id=step_id,
        organization_id=org_id,
        updates=updates_dict
    )
    if not updated_step_dict:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update step.")
    
    logger.info(f"API: Successfully updated step ID {step_id} for campaign {campaign_id}")
    return CampaignStepResponse(**updated_step_dict)


# --- Lead Enrollment Endpoints ---
@router.post("/{campaign_id}/enroll_leads", status_code=status.HTTP_200_OK, response_model=Dict[str, Any])
async def enroll_specific_leads_into_campaign(
    campaign_id: int,
    enroll_request: CampaignEnrollLeadsRequest, # Explicitly from schemas
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
) -> Dict[str, Any]:
    organization_id = current_user.organization_id
    logger.info(f"API: Enrolling leads {enroll_request.lead_ids} into Campaign {campaign_id} for Org {organization_id}")

    campaign = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=organization_id) # Pass db
    if not campaign: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Campaign ID {campaign_id} not found.")
    if not campaign.get("is_active"): raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign '{campaign.get('name')}' is not active.")
    
    campaign_steps = campaign_db_ops.get_steps_for_campaign(db=db, campaign_id=campaign_id, organization_id=organization_id) # Pass db
    if not campaign_steps and campaign.get("ai_status") not in ["completed_partial", "completed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign '{campaign.get('name')}' steps not ready (AI Status: {campaign.get('ai_status')}).")
    
    successful_enrollments = 0; failed_enrollments = 0; errors = []; processed_lead_ids = set()

    for lead_id in enroll_request.lead_ids:
        if lead_id in processed_lead_ids: continue
        processed_lead_ids.add(lead_id)
        lead = campaign_db_ops.get_lead_by_id(db=db, lead_id=lead_id, organization_id=organization_id) # Pass db
        if not lead: errors.append({"lead_id": lead_id, "error": "Lead not found."}); failed_enrollments += 1; continue
        
        existing_status = campaign_db_ops.get_lead_campaign_status(db=db, lead_id=lead_id, organization_id=organization_id) # Pass db
        if existing_status:
            errors.append({"lead_id": lead_id, "error": f"Lead already has status: {existing_status.get('status')}."}); failed_enrollments += 1; continue
            
        enrolled_status_record = campaign_db_ops.enroll_lead_in_campaign(db=db, lead_id=lead_id, campaign_id=campaign_id, organization_id=organization_id) # Pass db
        if enrolled_status_record:
            campaign_db_ops.update_lead_campaign_status( # Pass db
                db=db,
                status_id=enrolled_status_record['id'], 
                organization_id=organization_id, 
                updates={"next_email_due_at": datetime.now(timezone.utc)}
            )
            successful_enrollments += 1
        else:
            errors.append({"lead_id": lead_id, "error": "DB enrollment failed."}); failed_enrollments += 1
            
    return {
        "message": "Lead enrollment process completed.", "campaign_id": campaign_id,
        "successful_enrollments": successful_enrollments, "failed_enrollments": failed_enrollments,
        "details": errors
    }


def _background_enroll_icp_matched_leads(db_session_factory, campaign_id_for_enrollment: int, org_id_for_enrollment: int):
    db: Session = next(db_session_factory()) # Get a new session for the background task
    try:
        logger.info(f"BACKGROUND: Starting enrollment of ICP-matched leads for campaign ID {campaign_id_for_enrollment}, org {org_id_for_enrollment}.")
        campaign = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id_for_enrollment, organization_id=org_id_for_enrollment)
        if not campaign or not campaign.get("icp_id"):
            logger.error(f"BACKGROUND: Campaign {campaign_id_for_enrollment} not found or no ICP. Aborting."); return
        
        matched_leads = campaign_db_ops.get_leads_by_icp_match(db=db, organization_id=org_id_for_enrollment, icp_id=campaign["icp_id"])
        if not matched_leads: logger.info(f"BACKGROUND: No leads found matching ICP ID {campaign['icp_id']}."); return
        
        successful_enrollments = 0; skipped_count = 0
        for lead in matched_leads:
            lead_id = lead.get("id")
            existing_status = campaign_db_ops.get_lead_campaign_status(db=db, lead_id=lead_id, organization_id=org_id_for_enrollment)
            if existing_status: skipped_count += 1; logger.debug(f"BACKGROUND: Lead {lead_id} already has status, skipping."); continue
            
            enrolled = campaign_db_ops.enroll_lead_in_campaign(db=db, lead_id=lead_id, campaign_id=campaign_id_for_enrollment, organization_id=org_id_for_enrollment)
            if enrolled: 
                campaign_db_ops.update_lead_campaign_status(
                    db=db,
                    status_id=enrolled['id'], 
                    organization_id=org_id_for_enrollment, 
                    updates={"next_email_due_at": datetime.now(timezone.utc)}
                )
                successful_enrollments += 1
        logger.info(f"BACKGROUND: ICP-matched enrollment for campaign {campaign_id_for_enrollment} finished. Enrolled: {successful_enrollments}, Skipped: {skipped_count}.")
    finally:
        db.close()


@router.post("/{campaign_id}/enroll_matched_icp_leads", status_code=status.HTTP_202_ACCEPTED, response_model=Dict[str, str])
async def trigger_enroll_icp_matched_leads(
    campaign_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db), # <--- ADDED db
    current_user: UserPublic = Depends(get_current_user)
):
    organization_id = current_user.organization_id
    campaign = campaign_db_ops.get_campaign_by_id(db=db, campaign_id=campaign_id, organization_id=organization_id) # Pass db
    if not campaign: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")
    if not campaign.get("icp_id"): raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign not linked to an ICP.")
    if not campaign.get("is_active"): raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Campaign is not active.")
    campaign_steps = campaign_db_ops.get_steps_for_campaign(db=db, campaign_id=campaign_id, organization_id=organization_id) # Pass db
    if not campaign_steps and campaign.get("ai_status") not in ["completed_partial", "completed"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Campaign steps not ready (AI: {campaign.get('ai_status')}).")

    background_tasks.add_task(_background_enroll_icp_matched_leads, get_db, campaign_id, organization_id) # Pass db_session_factory
    return {"message": f"Process to enroll ICP-matched leads into campaign '{campaign.get('name')}' triggered."}
