# app/routers/dashboard.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any # Ensure all necessary types are imported

# Consolidate imports
from app import schemas # For Pydantic response models
from app.db import database as db_ops # Use an alias for database operations
from app.db.models import User as UserModel
from app.core.security import get_current_active_user # Assuming this is your main auth dependency
from app.auth.dependencies import get_current_active_user
# from app.utils.logger import logger # Assuming you have a configured logger utility
import logging # Using standard logging if app.utils.logger is not set up

# Configure logger (if not using a custom utility)
logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO) # Basic config, adjust as needed

router = APIRouter(
    prefix="/api/v1/dashboard",  # Prefix for all routes in this file
    tags=["dashboard"],          # Tag for OpenAPI docs
    dependencies=[Depends(get_current_active_user)] # Protect all routes in this router
)

# --- API Endpoints ---

@router.get("/appointment_stats", response_model=schemas.AppointmentStatsResponse)
async def get_appointment_stats(
    db: Session = Depends(db_ops.get_db),
    current_user: UserModel = Depends(get_current_active_user), # Changed to get_current_active_user
):
    """
    Provides statistics on appointments set and positive replies for the current user's organization.
    """
    if not current_user.organization_id:
        logger.warning(f"API: User {current_user.email} (ID: {current_user.id}) has no organization_id for appointment_stats.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with an organization")
    
    org_id = current_user.organization_id
    logger.info(f"API: Fetching appointment stats for Org ID: {org_id}")

    try:
        appointments = db_ops.count_appointments_set(db, organization_id=org_id)
        positive_replies = db_ops.count_positive_replies_status(db, organization_id=org_id)
    except Exception as e:
        logger.error(f"API: Database error fetching stats for Org ID {org_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching dashboard statistics.")

    conversion_rate = None
    if positive_replies > 0:
        conversion_rate = round((appointments / positive_replies) * 100, 2)

    return schemas.AppointmentStatsResponse(
        total_appointments_set=appointments,
        total_positive_replies=positive_replies,
        conversion_rate_percent=conversion_rate
    )

@router.get("/recent_appointments", response_model=List[schemas.RecentAppointment])
async def get_recent_appointments(
    limit: int = 5, # Allow overriding the limit via query param
    db: Session = Depends(db_ops.get_db),
    current_user: UserModel = Depends(get_current_active_user), # Changed to get_current_active_user
):
    """
    Fetches a list of recently marked appointments for the current user's organization.
    """
    if not current_user.organization_id:
        logger.warning(f"API: User {current_user.email} (ID: {current_user.id}) has no organization_id for recent_appointments.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with an organization")

    org_id = current_user.organization_id
    logger.info(f"API: Fetching {limit} recent appointments for Org ID: {org_id}")

    try:
        recent_appts_data = db_ops.get_recent_appointments_list(db, organization_id=org_id, limit=limit)
    except Exception as e:
        logger.error(f"API: Database error fetching recent appointments for Org ID {org_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error fetching recent appointments.")
    
    return recent_appts_data


@router.get("/actionable_replies", response_model=List[schemas.ActionableReply]) # Assuming ActionableReply schema exists
async def get_dashboard_actionable_replies(
    limit: int = 50, # Default limit
    db: Session = Depends(db_ops.get_db),
    current_user: UserModel = Depends(get_current_active_user) # Changed to get_current_active_user
):
    """
    Fetches actionable email replies for the current user's organization.
    These are items where `is_actioned_by_user` on the `email_replies` table would be FALSE,
    and the status indicates AI flagged it for review (e.g., 'positive_reply_ai_flagged').
    """
    if not current_user.organization_id:
        logger.warning(f"API: User {current_user.email} (ID: {current_user.id}) has no organization_id for actionable_replies.")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with an organization")

    org_id = current_user.organization_id
    logger.info(f"API: Fetching actionable replies for dashboard, Org ID: {org_id}, Limit: {limit}")

    try:
        # IMPORTANT: You need a database function like `get_actionable_email_replies_db`
        # that specifically fetches replies based on criteria like:
        # - Belongs to the organization
        # - LeadCampaignStatus.status is 'positive_reply_ai_flagged' (or similar)
        # - EmailReply.is_actioned_by_user is False (or NULL)
        # The function `get_leads_with_positive_status_for_dashboard` might be too broad
        # if it doesn't filter by `is_actioned_by_user`.
        #
        # Replace this with your actual, correctly filtered DB function:
        # For example, if you have a function `get_actionable_email_replies_for_dashboard`
        actionable_items = db_ops.get_actionable_email_replies(db, organization_id=org_id, limit=limit)
        # ^^^ Ensure this function exists in app/db/database.py and does the right filtering
        # based on `email_replies.is_actioned_by_user = False` and appropriate `lead_campaign_status.status`.

    except AttributeError as ae: # If db_ops.get_actionable_email_replies doesn't exist
        logger.error(f"API: Missing database function for actionable replies: {ae}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Actionable replies functionality is misconfigured.")
    except Exception as e:
        logger.error(f"API: Database error fetching actionable replies for Org ID {org_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not retrieve actionable replies data.")

    if actionable_items is None: # Should be caught by exception, but good check
        logger.error(f"API: DB function returned None for actionable replies for Org ID: {org_id}")
        # This case might indicate the DB function itself returned None instead of an empty list on no results
        return [] # Return empty list if DB function might return None for "no data"

    logger.info(f"API: Returning {len(actionable_items)} actionable reply items for Org ID: {org_id}")
    # The Pydantic models in schemas.ActionableReply will handle data conversion if orm_mode/from_attributes is True
    return actionable_items


# --- Placeholder for Campaign Performance Summary ---
# @router.get("/campaign_performance_summary", response_model=List[schemas.CampaignPerformanceSummaryItem])
# async def get_dashboard_campaign_performance(
#     db: Session = Depends(db_ops.get_db),
#     current_user: UserModel = Depends(get_current_active_user)
# ):
#     if not current_user.organization_id:
#         raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not associated with an organization")
#     org_id = current_user.organization_id
#     logger.info(f"API: Fetching campaign performance summary for Org ID: {org_id}")
#     # summary_data = db_ops.get_campaign_performance_summary_db(db, organization_id=org_id)
#     # return summary_data
#     return [] # Placeholder
