# app/routers/offering.py

from fastapi import APIRouter, Depends, HTTPException, status, Query # Added Query
from typing import List, Optional
from sqlalchemy.orm import Session # <--- IMPORTED Session

# --- Import necessary project modules ---
from app.schemas import OfferingInput, OfferingResponse, UserPublic # OfferingResponse is key
# from app.db import database # This might be where your CRUD functions are if not in a dedicated crud module
from app.db.database import get_db
from app.auth.dependencies import get_current_user
# from app.utils.logger import logger # Uncomment if you have a logger

# --- Define Router ---
router = APIRouter(
    prefix="/api/v1/offerings",
    tags=["offerings"],
)

# --- GET Endpoint to list Offerings for the Organization ---
# This is the single, corrected version of this endpoint
@router.get("/", response_model=List[OfferingResponse])
def list_organization_offerings(
    active_only: Optional[bool] = Query(None, description="Filter by active status. If not provided, returns all."), # Made it truly optional
    db: Session = Depends(get_db), # <--- ADDED db session dependency
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Lists all offerings for the current user's organization.
    Optionally filters by active status.
    """
    # logger.info(f"API: Listing offerings for Org ID: {current_user.organization_id} (Active only: {active_only})")
    print(f"API: Listing offerings for Org ID: {current_user.organization_id} (Active only: {active_only})")

    offerings = offering_crud.get_offerings_by_organization(
        db=db,
        organization_id=current_user.organization_id,
        active_only=active_only # Pass the active_only filter
    )
    return offerings


# --- POST Endpoint to create a NEW Offering ---
@router.post("/", response_model=OfferingResponse, status_code=status.HTTP_201_CREATED)
def create_new_offering(
    offering_data: OfferingInput,
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Creates a new offering for the current user's organization.
    """
    # logger.info(f"API: Attempting to create offering '{offering_data.name}' for Org ID: {current_user.organization_id}")
    print(f"API: Attempting to create offering '{offering_data.name}' for Org ID: {current_user.organization_id}")

    # Assuming offering_crud.create_offering expects db, obj_in, and organization_id
    created_offering = offering_crud.create_offering(
        db=db,
        obj_in=offering_data, # Pass the Pydantic model directly
        organization_id=current_user.organization_id
    )

    if not created_offering:
        # logger.error(f"API Error: Failed to create offering in DB for Org ID {current_user.organization_id}")
        print(f"API Error: Failed to create offering in DB for Org ID {current_user.organization_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create offering.")

    # logger.info(f"API: Successfully created offering ID {created_offering.id} for Org ID {current_user.organization_id}")
    print(f"API: Successfully created offering ID {created_offering.id} for Org ID {current_user.organization_id}")
    return created_offering


# --- GET Endpoint for a specific Offering ---
@router.get("/{offering_id}", response_model=OfferingResponse)
def get_single_offering(
    offering_id: int,
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Gets a specific offering by ID, ensuring it belongs to the user's organization.
    """
    # logger.info(f"API: Getting offering ID {offering_id} for Org ID: {current_user.organization_id}")
    print(f"API: Getting offering ID {offering_id} for Org ID: {current_user.organization_id}")

    # Assuming offering_crud.get_offering expects db, id, and organization_id
    offering = offering_crud.get_offering(
        db=db,
        id=offering_id,
        organization_id=current_user.organization_id
    )

    if not offering:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found.")
    return offering


# --- PUT Endpoint to update an Offering ---
@router.put("/{offering_id}", response_model=OfferingResponse)
def update_existing_offering(
    offering_id: int,
    offering_data: OfferingInput, # Use input schema for update data validation
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Updates an existing offering by ID, ensuring it belongs to the user's organization.
    """
    # logger.info(f"API: Updating offering ID {offering_id} for Org ID: {current_user.organization_id}")
    print(f"API: Updating offering ID {offering_id} for Org ID: {current_user.organization_id}")

    # Check if offering exists first
    db_offering = offering_crud.get_offering(db=db, id=offering_id, organization_id=current_user.organization_id)
    if not db_offering:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found.")

    # Assuming offering_crud.update_offering expects db, db_obj (the existing offering), and obj_in (update data)
    updated_offering = offering_crud.update_offering(
        db=db,
        db_obj=db_offering,
        obj_in=offering_data # Pass Pydantic model; CRUD function can convert to dict if needed
    )
    # The update_offering function should handle the actual update and commit if successful.
    # It should return the updated SQLAlchemy model instance.

    # logger.info(f"API: Successfully updated offering ID {offering_id} for Org ID {current_user.organization_id}")
    print(f"API: Successfully updated offering ID {offering_id} for Org ID {current_user.organization_id}")
    return updated_offering


# --- DELETE Endpoint for an Offering ---
@router.delete("/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_single_offering(
    offering_id: int,
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Deletes a specific offering by ID, ensuring it belongs to the user's organization.
    Returns No Content on success.
    """
    # logger.info(f"API: Deleting offering ID {offering_id} for Org ID: {current_user.organization_id}")
    print(f"API: Deleting offering ID {offering_id} for Org ID: {current_user.organization_id}")

    # Assuming offering_crud.remove_offering expects db, id, and organization_id
    # and returns the deleted object or raises an exception if not found.
    deleted_offering = offering_crud.remove_offering(
        db=db,
        id=offering_id,
        organization_id=current_user.organization_id
    )

    if not deleted_offering: # Adjust if your remove_offering returns True/False or raises
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found.")

    return None # For 204 No Content
