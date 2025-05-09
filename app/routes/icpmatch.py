# app/routers/icpmatch.py

from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status
from typing import List, Dict, Any
from pydantic import BaseModel # 

# Correctly import the agent from its actual location
from app.agents.icp_matcher import ICPMatcherAgent
from app.db import database
from app.auth.dependencies import get_current_user
from app.schemas import UserPublic 
from app.utils.logger import logger

router = APIRouter(prefix="/api/v1/icp-matching", tags=["ICP Matching"])
agent = ICPMatcherAgent()

class LeadMatchRequest(BaseModel): # Now BaseModel is defined
    lead_ids: List[int]


def _background_match_and_update_leads(lead_ids_to_process: List[int], org_id: int):
    """Background function to perform matching and DB updates."""
    logger.info(f"BACKGROUND TASK: Starting ICP matching for {len(lead_ids_to_process)} leads in org {org_id}.")
    
    leads_data_dicts: List[Dict[str, Any]] = []
    for lead_id in lead_ids_to_process:
        lead_db_data = database.get_lead_by_id(lead_id=lead_id, organization_id=org_id)
        if lead_db_data:
            leads_data_dicts.append(dict(lead_db_data)) # Ensure it's a dict
        else:
            logger.warning(f"BACKGROUND TASK: Lead ID {lead_id} not found or not accessible for org {org_id}.")
            
    if not leads_data_dicts:
        logger.info(f"BACKGROUND TASK: No valid leads to process for org {org_id}.")
        return

    # The agent processes these leads against the organization's ICPs
    match_processing_results = agent.process_leads_for_icp_matching(leads_data_dicts, org_id)
    
    updated_leads_count = 0
    for result_item in match_processing_results:
        original_lead_data = result_item["original_lead_data"]
        lead_id_to_update = original_lead_data.get("id")
        match_info = result_item["icp_match_result"]

        if not lead_id_to_update:
            logger.warning("BACKGROUND TASK: Processed lead item missing original lead ID.")
            continue

        db_update_payload: Dict[str, Any] = {}
        if match_info["is_match"]:
            db_update_payload = {
                "matched": True,
                "reason": f"Matches ICP: {match_info.get('matched_icp_name')} (Score: {match_info.get('score_percentage')}%). Reasons: {'; '.join(match_info.get('reasons',[]))}",
                "icp_match_id": match_info.get("matched_icp_id") # Ensure this key exists in match_info
            }
        else:
            # If you want to clear previous matches if a lead no longer matches any ICP
            if original_lead_data.get("icp_match_id") is not None or original_lead_data.get("matched"):
                db_update_payload = {
                    "matched": False,
                    "reason": match_info.get("message", "Does not match current ICP criteria."),
                    "icp_match_id": None
                }
        
        if db_update_payload: # Only update if there's something to change
            updated_lead = database.update_lead_partial(
                lead_id=lead_id_to_update,
                organization_id=org_id,
                updates=db_update_payload
            )
            if updated_lead:
                updated_leads_count += 1
                logger.debug(f"BACKGROUND TASK: Lead ID {lead_id_to_update} updated with ICP match info.")
            else:
                logger.error(f"BACKGROUND TASK: Failed to update lead ID {lead_id_to_update} in database.")
                
    logger.info(f"BACKGROUND TASK: Finished. {updated_leads_count}/{len(leads_data_dicts)} leads updated for org {org_id}.")


@router.post("/trigger_matching_for_leads", status_code=status.HTTP_202_ACCEPTED)
async def trigger_lead_icp_matching_task(
    request_data: LeadMatchRequest, # Expects a list of lead_ids
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user) # Assuming User is your Pydantic model for auth
):
    """
    Triggers a background task to match the provided list of leads
    against all ICPs for the current user's organization and updates them in the DB.
    """
    if not request_data.lead_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No lead_ids provided.")

    # You could add a check here to ensure lead_ids belong to current_user.organization_id
    # or let the background task handle it (get_lead_by_id will fail for wrong org).

    background_tasks.add_task(
        _background_match_and_update_leads,
        request_data.lead_ids,
        current_user.organization_id
    )
    
    return {"message": f"ICP matching process triggered for {len(request_data.lead_ids)} leads. Results will be updated in the background."}

# You might also want an endpoint to trigger matching for ALL leads in an organization
@router.post("/trigger_matching_for_all_org_leads", status_code=status.HTTP_202_ACCEPTED)
async def trigger_all_leads_icp_matching_task(
    background_tasks: BackgroundTasks,
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Triggers a background task to match ALL leads for the current user's organization
    against all its ICPs and updates them in the DB.
    """
    # Fetch all lead IDs for the organization
    # Note: For very large orgs, fetching all leads might be memory intensive.
    # Consider pagination or processing in smaller batches within the background task if needed.
    all_org_leads_raw = database.get_leads_by_organization(organization_id=current_user.organization_id, limit=100000) # High limit
    if not all_org_leads_raw:
        return {"message": "No leads found for the organization to match."}
    
    all_org_lead_ids = [lead['id'] for lead in all_org_leads_raw if 'id' in lead]

    if not all_org_lead_ids:
        return {"message": "No leads with valid IDs found for the organization to match."}

    background_tasks.add_task(
        _background_match_and_update_leads,
        all_org_lead_ids,
        current_user.organization_id
    )
    return {"message": f"ICP matching process triggered for all ({len(all_org_lead_ids)}) leads in the organization. Results will be updated in the background."}
