# app/routers/dashboard.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional, Dict, Any # Ensure all are imported

from app import schemas # To import response models like a potential DashboardReplyItem
from app.db import database
from app.auth.dependencies import get_current_user # Your UserPublic model from auth
from app.utils.logger import logger

router = APIRouter(
    prefix="/api/v1/dashboard",
    tags=["Dashboard Data"]
)

@router.get("/actionable_replies", response_model=List[schemas.LeadCampaignStatusResponse]) # Using existing for now
async def get_actionable_email_replies(
    current_user: schemas.UserPublic = Depends(get_current_user),
    limit: int = 50 # Add pagination if list can be very long
):
    """
    Fetches lead campaign statuses that indicate recent positive AI-classified replies
    or other statuses requiring user action, for the current user's organization.
    These are items where `is_actioned_by_user` on the `email_replies` table would be FALSE.
    """
    org_id = current_user.organization_id
    logger.info(f"API: Fetching actionable replies for dashboard, Org ID: {org_id}, Limit: {limit}")

    # The database.get_leads_with_positive_status_for_dashboard function already does the JOINs
    # and filtering by relevant statuses. We just need to ensure it also considers
    # an 'is_actioned_by_user = FALSE' type of flag if that's on the email_replies table.
    #
    # The current DB function `get_leads_with_positive_status_for_dashboard` fetches based on `lead_campaign_status.status`.
    # If an AI reply sets `lcs.status` to 'positive_reply_ai_flagged', and then the user actions it
    # to 'appointment_manually_set', the original DB function would still pick up 'appointment_manually_set'.
    # We might need a more specific DB function OR ensure the Streamlit UI, after an action,
    # calls an API to mark the underlying `email_replies.is_actioned_by_user = TRUE`.

    # For now, let's assume get_leads_with_positive_status_for_dashboard is suitable.
    # If you added 'is_actioned_by_user' to email_replies, the DB query would need to be updated.
    # The current DB function already joins with email_replies to get latest reply snippet.

    actionable_items = database.get_leads_with_positive_status_for_dashboard(
        organization_id=org_id,
        limit=limit
    )

    if actionable_items is None: # Indicates a DB error in the function
        logger.error(f"API: DB error fetching actionable replies for Org ID: {org_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve actionable replies data.")

    # The `get_leads_with_positive_status_for_dashboard` returns a list of dicts.
    # `schemas.LeadCampaignStatusResponse` needs to have all the fields returned by that DB function.
    # Let's verify the fields in LeadCampaignStatusResponse and the DB function.
    # LeadCampaignStatusResponse needs: lead_name, lead_email, lead_company, campaign_name,
    # latest_reply_id, latest_reply_snippet, latest_reply_ai_summary, latest_reply_ai_classification, latest_reply_received_at
    # These are all aliased in the DB function.

    # If you want to filter out items where user has already set an appointment directly from this list:
    # actionable_items_filtered = [item for item in actionable_items if item.get('lead_campaign_status') != 'appointment_manually_set']
    # However, it might be useful to show recently set appointments too. The UI can then decide what to do.

    logger.info(f"API: Returning {len(actionable_items)} actionable reply items for Org ID: {org_id}")
    return [schemas.LeadCampaignStatusResponse(**item) for item in actionable_items]
