# app/routers/offering.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from datetime import datetime # Needed for response model

# --- Import necessary project modules ---
# Use the Input/Response schemas designed for DB interaction
from app.schemas import OfferingInput, OfferingResponse, UserPublic
from app.db import database
from app.database import get_db
from app.crud import offering as offering_crud
# Import the authentication dependency
from app.auth.dependencies import get_current_user

# --- Define Router ---
# Consistent prefix and tags for Offering management
router = APIRouter(
    prefix="/api/v1/offerings",
    tags=["offerings"],
)

@router.get("/", response_model=List[Offering]) # Or your specific response model
def list_organization_offerings( # Changed to 'def' as per original traceback
    active_only: Optional[bool] = Query(True, description="Filter for active offerings only. Defaults to True."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve all offerings for the current user's organization.
    Optionally filter by active status (defaults to active only).
    """

print(f"API: Listing offerings for Org ID: {current_user.organization_id} (Active only: {active_only})")
    offerings = offering_crud.get_offerings_by_organization(
        db=db,
        organization_id=current_user.organization_id,
        active_only=active_only
    )
    if not offerings:
        return []
    return offerings

# --- POST Endpoint to create a NEW Offering ---
@router.post("/", response_model=OfferingResponse, status_code=status.HTTP_201_CREATED)
def create_new_offering(
    offering_data: OfferingInput, # Validate request body against OfferingInput
    current_user: UserPublic = Depends(get_current_user) # Require authentication
):
    """
    Creates a new offering for the current user's organization.
    Requires authentication.
    """
    print(f"API: Attempting to create offering '{offering_data.name}' for Org ID: {current_user.organization_id}")
    # Convert Pydantic model to dict for the database function
    offering_dict = offering_data.dict()
    # Call the database function to create the offering
    created_offering = database.create_offering(
        organization_id=current_user.organization_id,
        offering_data=offering_dict
    )
    # Handle potential database errors
    if not created_offering:
        print(f"API Error: Failed to create offering in DB for Org ID {current_user.organization_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create offering.")
    # Return the data of the created offering (validated by response_model)
    print(f"API: Successfully created offering ID {created_offering.get('id')} for Org ID {current_user.organization_id}")
    return created_offering


# --- GET Endpoint to list Offerings for the Organization ---
@router.get("/", response_model=List[OfferingResponse])
def list_organization_offerings(
    active_only: bool = True, # Optional query parameter to filter by is_active flag
    current_user: UserPublic = Depends(get_current_user) # Require authentication
):
    """
    Lists all offerings (active by default) for the current user's organization.
    Requires authentication.
    """
    print(f"API: Listing offerings for Org ID: {current_user.organization_id} (Active only: {active_only})")
    # Call the database function to get offerings for the specific organization
    offerings = database.get_offerings_by_organization( # <--- Correct name
    organization_id=current_user.organization_id,
    active_only=active_only
    )
    # FastAPI validates the list of dictionaries against List[OfferingResponse]
    return offerings


# --- GET Endpoint for a specific Offering ---
@router.get("/{offering_id}", response_model=OfferingResponse)
def get_single_offering(
    offering_id: int, # Path parameter for the offering ID
    current_user: UserPublic = Depends(get_current_user) # Require authentication
):
    """
    Gets a specific offering by ID, ensuring it belongs to the user's organization.
    Requires authentication.
    """
    # --- CORRECTED PRINT STATEMENT ---
    print(f"API: Getting offering ID {offering_id} for Org ID: {current_user.organization_id}")
    # --- END CORRECTION ---

    # Call database function, passing both IDs for authorization check
    offering = database.get_offering_by_id(offering_id, current_user.organization_id)
    # Handle case where offering doesn't exist or doesn't belong to the org
    if not offering:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found.")
    # Return the fetched offering data
    return offering


# --- PUT Endpoint to update an Offering ---
@router.put("/{offering_id}", response_model=OfferingResponse)
def update_existing_offering(
    offering_id: int, # Path parameter for the offering ID
    offering_data: OfferingInput, # Use input schema for update data validation
    current_user: UserPublic = Depends(get_current_user) # Require authentication
):
    """
    Updates an existing offering by ID, ensuring it belongs to the user's organization.
    Requires authentication.
    """
    print(f"API: Updating offering ID {offering_id} for Org ID: {current_user.organization_id}")
    # Call database function to update, passing IDs and data dict
    updated_offering = database.update_offering(
        offering_id=offering_id,
        organization_id=current_user.organization_id,
        offering_data=offering_data.dict(exclude_unset=True) # Allow partial updates if desired
    )
    # Handle case where offering wasn't found or update failed
    if not updated_offering:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found or failed to update.")
    # Return the updated offering data
    print(f"API: Successfully updated offering ID {offering_id} for Org ID {current_user.organization_id}")
    return updated_offering


# --- DELETE Endpoint for an Offering ---
@router.delete("/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_single_offering(
    offering_id: int, # Path parameter for the offering ID
    current_user: UserPublic = Depends(get_current_user) # Require authentication
):
    """
    Deletes a specific offering by ID, ensuring it belongs to the user's organization.
    Requires authentication. Returns No Content on success.
    """
    print(f"API: Deleting offering ID {offering_id} for Org ID: {current_user.organization_id}")
    # Call database function to delete
    deleted = database.delete_offering(offering_id, current_user.organization_id)
    # Handle case where offering wasn't found to be deleted
    if not deleted:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found.")
    # No response body for 204 status code
    return None
