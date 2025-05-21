# app/routers/icp.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime # Keep if used by schemas, schemas.py handles its own imports
from sqlalchemy.orm import Session # <--- IMPORT Session

# --- Import necessary project modules ---
from app.schemas import ICPInput, ICPResponse, UserPublic # ICPResponse is the key
from app.db.database import get_db # Corrected path for get_db
from app.db import database # This could be your CRUD module or just DB setup.
                            

from app.auth.dependencies import get_current_user # Assuming this returns UserPublic
from app.utils.logger import logger

# --- Define Router ---
router = APIRouter(
    prefix="/api/v1/icps",
    tags=["icps"],
)

# --- POST Endpoint to CREATE a new ICP ---
@router.post(
    "/",
    response_model=ICPResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New ICP",
    description="Creates a new Ideal Customer Profile (ICP) for the current user's organization."
)
def create_new_icp(
    icp_data: ICPInput,
    db: Session = Depends(get_db), # <--- ADD db session
    current_user: UserPublic = Depends(get_current_user)
):
    logger.info(f"API: Attempting to create ICP '{icp_data.name}' for Org ID: {current_user.organization_id}")

    # Assuming icp_crud.create_icp(db=db, icp_in=icp_data, organization_id=current_user.organization_id)
    # Or if your app.db.database module has the create_icp function:
    # from app.db import database as icp_db_ops (or a better alias)
    created_icp = database.create_icp( # Or your direct database module call
        db=db,
        icp_in=icp_data,
        organization_id=current_user.organization_id
    )

    if not created_icp:
        logger.error(f"API Error: Failed to create ICP '{icp_data.name}' for Org ID {current_user.organization_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create ICP definition due to a server error."
        )
    # Ensure created_icp is a Pydantic model or SQLAlchemy model instance for response_model
    logger.info(f"API: Successfully created ICP ID {created_icp.id} for Org ID: {current_user.organization_id}")
    return created_icp


# --- GET Endpoint to LIST all ICPs for the organization ---
# THIS IS THE CORRECTED LIST ENDPOINT
@router.get(
    "/",
    response_model=List[ICPResponse], # <--- CORRECTED to ICPResponse
    summary="List Organization's ICPs",
    description="Retrieves all Ideal Customer Profiles (ICPs) defined for the current user's organization."
)
def list_organization_icps(
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user) # Using UserPublic for consistency
):
    logger.info(f"API: Fetching all ICPs for Org ID: {current_user.organization_id}")

    # Assuming icp_crud.get_icps_by_organization_id(db, organization_id)
    icps_list = database.get_icps_by_organization_id( # Or your direct database module call
        db=db,
        organization_id=current_user.organization_id
    )

    logger.info(f"API: Found {len(icps_list)} ICPs for Org ID: {current_user.organization_id}")
    return icps_list


# --- GET Endpoint to retrieve a SPECIFIC ICP by ID ---
@router.get(
    "/{icp_id}",
    response_model=ICPResponse, # <--- Ensure this is ICPResponse
    summary="Get Specific ICP",
    description="Retrieves a specific Ideal Customer Profile (ICP) by its ID, ensuring it belongs to the current user's organization."
)
def get_specific_icp(
    icp_id: int,
    db: Session = Depends(get_db), # <--- ADD db session
    current_user: UserPublic = Depends(get_current_user)
):
    logger.info(f"API: Fetching ICP ID {icp_id} for Org ID: {current_user.organization_id}")

    # Assuming icp_crud.get_icp(db, icp_id, organization_id)
    icp_data = database.get_icp( # Or your direct database module call
        db=db,
        id=icp_id, # Assuming your CRUD function takes 'id'
        organization_id=current_user.organization_id
    )

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
    "/{icp_id}",
    response_model=ICPResponse, # <--- Ensure this is ICPResponse
    summary="Update Specific ICP",
    description="Updates an existing Ideal Customer Profile (ICP) by its ID."
)
def update_specific_icp(
    icp_id: int,
    icp_data: ICPInput,
    db: Session = Depends(get_db), # <--- ADD db session
    current_user: UserPublic = Depends(get_current_user)
):
    logger.info(f"API: Attempting to update ICP ID {icp_id} for Org ID: {current_user.organization_id}")

    # Assuming icp_crud.update_icp(db, icp_id, organization_id, icp_in)
    updated_icp = database.update_icp( # Or your direct database module call
        db=db,
        id=icp_id, # Assuming your CRUD function takes 'id'
        organization_id=current_user.organization_id,
        obj_in=icp_data # Assuming your CRUD function takes 'obj_in' or similar
    )

    if not updated_icp:
        logger.warning(f"API: Failed to update ICP ID {icp_id} for Org ID {current_user.organization_id}. Might not exist.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to update ICP with ID {icp_id}. Not found or error occurred."
        )

    logger.info(f"API: Successfully updated ICP ID {icp_id}")
    return updated_icp


# --- DELETE Endpoint for a specific ICP by ID ---
@router.delete(
    "/{icp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Specific ICP",
    description="Deletes a specific Ideal Customer Profile (ICP) by its ID."
)
def delete_specific_icp(
    icp_id: int,
    db: Session = Depends(get_db), # <--- ADD db session
    current_user: UserPublic = Depends(get_current_user)
):
    logger.info(f"API: Attempting to delete ICP ID {icp_id} for Org ID: {current_user.organization_id}")

    # Assuming icp_crud.remove_icp(db, icp_id, organization_id)
    deleted_icp = database.remove_icp( # Or your direct database module call
        db=db,
        id=icp_id, # Assuming your CRUD function takes 'id'
        organization_id=current_user.organization_id
    ) # remove often returns the deleted object or True/False

    if not deleted_icp: # Adjust condition based on what your remove_icp returns
        logger.warning(f"API: ICP ID {icp_id} not found to delete for Org ID: {current_user.organization_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ICP with ID {icp_id} not found."
        )

    logger.info(f"API: Successfully deleted ICP ID {icp_id}")
    return None # For 204 No Content
