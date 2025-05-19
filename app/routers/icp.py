# app/routers/icp.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List # Changed Optional to List for listing ICPs
from datetime import datetime # Needed for response model

# --- Import necessary project modules ---
# Assuming these schemas exist and ICPResponseAPI handles potential None values for JSON fields
from app.schemas import ICPInput, ICPResponse, UserPublic
from app.db import database
from app.database import get_db
from app.crud import icp as icp_crud
from app.auth.dependencies import get_current_user
from app.utils.logger import logger # Assuming logger is setup

# --- Define Router ---
# Changed prefix to /icps for standard REST pluralization
router = APIRouter(
    prefix="/api/v1/icps",
    tags=["icps"],
)

@router.get("/", response_model=List[ICP]) # Or your specific response model
def list_organization_icps( # Note: Changed to 'def' as per original traceback showing run_in_threadpool
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve all ICPs (Ideal Customer Profiles) for the current user's organization.
    """

    print(f"API: Fetching all ICPs for Org ID: {current_user.organization_id}")
    icps_list = icp_crud.get_icps_by_organization_id(
        db=db,
        organization_id=current_user.organization_id
    )
    if not icps_list:
        return []
    return icps_list

# --- POST Endpoint to CREATE a new ICP ---
@router.post(
    "/",
    response_model=ICPResponse,
    status_code=status.HTTP_201_CREATED, # Correct status code for creation
    summary="Create New ICP",
    description="Creates a new Ideal Customer Profile (ICP) for the current user's organization."
)
def create_new_icp(
    icp_data: ICPInput, # Request body with ICP details
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Creates a new ICP associated with the logged-in user's organization.
    Requires ICP name in the input data.
    """
    logger.info(f"API: Attempting to create ICP '{icp_data.name}' for Org ID: {current_user.organization_id}")
    icp_definition_dict = icp_data.dict(exclude_unset=True)

    # Call the new database function for creation
    created_icp = database.create_icp(
        organization_id=current_user.organization_id,
        icp_definition=icp_definition_dict
    )

    if not created_icp:
        logger.error(f"API Error: Failed to create ICP '{icp_data.name}' for Org ID {current_user.organization_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ICP definition due to a server error."
        )

    logger.info(f"API: Successfully created ICP ID {created_icp.get('id')} for Org ID: {current_user.organization_id}")
    return created_icp

# --- GET Endpoint to LIST all ICPs for the organization ---
@router.get(
    "/",
    response_model=List[ICPResponse], # Returns a list of ICPs
    summary="List Organization's ICPs",
    description="Retrieves all Ideal Customer Profiles (ICPs) defined for the current user's organization."
)
def list_organization_icps(
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Fetches all ICPs associated with the logged-in user's organization.
    Returns an empty list if none are defined.
    """
    logger.info(f"API: Fetching all ICPs for Org ID: {current_user.organization_id}")
    # Call the new database function to get a list
    icps_list = database.get_icps_by_organization_id(current_user.organization_id)

    # No error needed if list is empty, just return the empty list
    logger.info(f"API: Found {len(icps_list)} ICPs for Org ID: {current_user.organization_id}")
    return icps_list

# --- GET Endpoint to retrieve a SPECIFIC ICP by ID ---
@router.get(
    "/{icp_id}", # Path parameter for the specific ICP ID
    response_model=ICPResponse,
    summary="Get Specific ICP",
    description="Retrieves a specific Ideal Customer Profile (ICP) by its ID, ensuring it belongs to the current user's organization."
)
def get_specific_icp(
    icp_id: int, # Get ID from path
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Fetches a specific ICP by its ID for the logged-in user's organization.
    Returns 404 if the ICP is not found or doesn't belong to the organization.
    """
    logger.info(f"API: Fetching ICP ID {icp_id} for Org ID: {current_user.organization_id}")
    # Call the new database function to get by specific ID and org ID
    icp_data = database.get_icp_by_id(icp_id=icp_id, organization_id=current_user.organization_id)

    if not icp_data:
        logger.warning(f"API: ICP ID {icp_id} not found for Org ID: {current_user.organization_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ICP with ID {icp_id} not found."
        )

    logger.info(f"API: Successfully fetched ICP ID {icp_id}")
    return icp_data

# --- PUT Endpoint to UPDATE a specific ICP by ID ---
@router.put(
    "/{icp_id}", # Path parameter for the specific ICP ID
    response_model=ICPResponse,
    summary="Update Specific ICP",
    description="Updates an existing Ideal Customer Profile (ICP) by its ID."
)
def update_specific_icp(
    icp_id: int, # Get ID from path
    icp_data: ICPInput, # Get updated data from request body
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Updates an existing ICP identified by `icp_id`.
    Ensures the ICP belongs to the logged-in user's organization.
    Returns the updated ICP data or 404 if not found.
    """
    logger.info(f"API: Attempting to update ICP ID {icp_id} for Org ID: {current_user.organization_id}")
    icp_definition_dict = icp_data.dict(exclude_unset=True)

    # Call the new database function for updating
    updated_icp = database.update_icp(
        icp_id=icp_id,
        organization_id=current_user.organization_id,
        icp_definition=icp_definition_dict
    )

    if not updated_icp:
        # This could mean not found (rowcount was 0) or DB error
        # Check if it existed first to return 404 vs 500 (optional enhancement)
        # For now, assume 404 is the most likely if update returns None after checking rowcount
        logger.warning(f"API: Failed to update ICP ID {icp_id} for Org ID {current_user.organization_id}. Might not exist.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, # Or 500 if DB error is suspected
            detail=f"Failed to update ICP with ID {icp_id}. Not found or error occurred."
        )

    logger.info(f"API: Successfully updated ICP ID {icp_id}")
    return updated_icp

# --- DELETE Endpoint for a specific ICP by ID ---
@router.delete(
    "/{icp_id}", # Path parameter for the specific ICP ID
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Specific ICP",
    description="Deletes a specific Ideal Customer Profile (ICP) by its ID."
)
def delete_specific_icp(
    icp_id: int, # Get ID from path
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Deletes an existing ICP identified by `icp_id`.
    Ensures the ICP belongs to the logged-in user's organization.
    Returns 204 No Content on success, 404 if not found.
    """
    logger.info(f"API: Attempting to delete ICP ID {icp_id} for Org ID: {current_user.organization_id}")
    # Call the new database function for deletion
    deleted = database.delete_icp(
        icp_id=icp_id,
        organization_id=current_user.organization_id
    )

    if not deleted:
        logger.warning(f"API: ICP ID {icp_id} not found to delete for Org ID: {current_user.organization_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ICP with ID {icp_id} not found."
        )

    logger.info(f"API: Successfully deleted ICP ID {icp_id}")
    # No response body needed for 204
    return None # FastAPI handles sending the 204 status code
