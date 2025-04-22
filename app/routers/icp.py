# app/routers/icp.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List # Added List just in case needed later, Optional needed now
from datetime import datetime # Needed for response model

# --- Import necessary project modules ---
# Use the new ICPInput/ICPResponseAPI schemas defined previously
from app.schemas import ICPInput, ICPResponseAPI, UserPublic
from app.db import database
from app.auth.dependencies import get_current_user

# --- Define Router ---
# Consistent prefix and tags for ICP management
router = APIRouter(
    prefix="/api/v1/icp",
    tags=["ICP Management"]
)

# --- GET Endpoint to retrieve the organization's ICP ---
@router.get(
    "/",
    response_model=Optional[ICPResponseAPI], # Response can be null if no ICP exists
    summary="Get Organization's ICP",
    description="Retrieves the Ideal Customer Profile (ICP) definition for the current user's organization."
)
def get_organization_icp(
    current_user: UserPublic = Depends(get_current_user) # Requires authentication
):
    """
    Fetches the currently defined ICP for the logged-in user's organization.
    Returns the ICP definition or null if none is set.
    """
    print(f"API: Fetching ICP for Org ID: {current_user.organization_id}")
    icp_data = database.get_icp_by_organization_id(current_user.organization_id)

    if not icp_data:
        print(f"API: No ICP found for Org ID: {current_user.organization_id}")
        # Return None explicitly, FastAPI handles the Optional response model
        return None

    # Return the fetched data. FastAPI validates it against ICPResponseAPI.
    return icp_data


# --- PUT Endpoint to create or update the organization's ICP ---
@router.put(
    "/",
    response_model=ICPResponseAPI, # Return the saved ICP data
    summary="Create or Update Organization's ICP",
    description="Sets (Creates or fully Updates/Replaces) the ICP definition for the current user's organization."
)
def set_organization_icp(
    icp_data: ICPInput, # Use the input schema for request body validation
    current_user: UserPublic = Depends(get_current_user) # Requires authentication
):
    """
    Creates a new ICP definition if one doesn't exist for the organization,
    or completely replaces the existing one with the provided data.
    """
    print(f"API: Setting ICP for Org ID: {current_user.organization_id}")
    # Convert the incoming Pydantic model data to a dictionary
    icp_definition_dict = icp_data.dict(exclude_unset=True) # Exclude unset fields if needed

    saved_icp = database.create_or_update_icp(
        organization_id=current_user.organization_id,
        icp_definition=icp_definition_dict
    )

    if not saved_icp:
        # This indicates a database error during the save/update attempt
        print(f"API Error: Failed to save ICP for Org ID {current_user.organization_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save ICP definition due to a server error."
        )

    print(f"API: Successfully saved/updated ICP for Org ID: {current_user.organization_id}")
    # Return the saved data (includes DB ID, timestamps)
    return saved_icp


# --- (Optional) DELETE Endpoint ---
@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Organization's ICP",
    description="Deletes the ICP definition, if one exists, for the current user's organization."
    )
def delete_organization_icp(
    current_user: UserPublic = Depends(get_current_user) # Requires auth
):
    """
    Removes the ICP definition associated with the logged-in user's organization.
    Returns a success status with no content.
    """
    print(f"API: Deleting ICP for Org ID: {current_user.organization_id}")
    deleted = database.delete_icp(current_user.organization_id)

    if not deleted:
        # If no ICP existed, it's arguably not an error for DELETE,
        # but raising 404 clarifies that nothing was found to delete.
        print(f"API: No ICP found to delete for Org ID: {current_user.organization_id}")
        # raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ICP definition not found.")

    # No response body needed for 204
    return None
