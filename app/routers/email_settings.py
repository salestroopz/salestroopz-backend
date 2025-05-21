# app/routers/email_settings.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy.orm import Session # <--- IMPORTED Session

# Import project modules
from app.schemas import EmailSettingsInput, EmailSettingsResponse, UserPublic # Use these
from app.db.database import get_db
# Assuming your CRUD functions are in app.db.database, let's use it directly or alias
from app.db import database as email_settings_db_ops # Alias for clarity
from app.auth.dependencies import get_current_user
from app.utils.logger import logger

# Define Router
router = APIRouter(
    prefix="/api/v1/email-settings",
    tags=["email-settings"],
)

# --- GET Endpoint to retrieve email settings ---
# This is the single, corrected version of this endpoint
@router.get("/", response_model=Optional[EmailSettingsResponse])
def get_email_settings_route( # Renamed to avoid conflict if you keep the helper
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user)
):
    """Retrieves the email sending settings for the current user's organization."""
    org_id = current_user.organization_id
    logger.info(f"API: Getting email settings for Org ID: {org_id}")

    # Assuming get_org_email_settings_from_db takes (db, organization_id)
    settings_dict = email_settings_db_ops.get_org_email_settings_from_db(
        db=db,
        organization_id=org_id
    )

    if not settings_dict:
        logger.info(f"API: No email settings found for Org ID: {org_id}")
        return None

    # Your logic for credentials_set (ensure it doesn't modify settings_dict directly
    # if settings_dict is a SQLAlchemy model instance without this field)
    # It's better if EmailSettingsResponse handles this or if it's a derived property.
    # For now, let's assume settings_dict is a plain dict from your DB function.
    
    # Example: If you want to add 'credentials_set' to the response dynamically
    # This part of your original logic needs to be careful about mutating the
    # object that Pydantic will use for validation if it's an ORM model.
    # If settings_dict is already a dictionary, this is safer.
    
    # provider = settings_dict.get("provider_type")
    # credentials_are_set = False
    # if provider == 'smtp':
    #     if all(settings_dict.get(k) for k in ["smtp_host", "smtp_port", "smtp_username", "encrypted_smtp_password"]): # Check encrypted field
    #         credentials_are_set = True
    # elif provider == 'aws_ses':
    #     if settings_dict.get("encrypted_api_key"): # Check for encrypted AWS key placeholder
    #         credentials_are_set = True
    # settings_dict_for_response = settings_dict.copy()
    # settings_dict_for_response["credentials_set"] = credentials_are_set # Add to a copy

    # Pydantic will create EmailSettingsResponse from the dictionary.
    # Ensure settings_dict keys match EmailSettingsResponse fields.
    logger.info(f"API: Returning email settings for Org ID: {org_id}, Provider: {settings_dict.get('provider_type')}, Configured: {settings_dict.get('is_configured')}")
    return EmailSettingsResponse(**settings_dict)


# --- PUT Endpoint to create or update email settings ---
@router.put("/", response_model=EmailSettingsResponse)
def set_email_settings_route( # Renamed
    settings_input: EmailSettingsInput,
    db: Session = Depends(get_db), # <--- ADDED db session
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Creates or updates the email sending settings for the current user's organization.
    """
    org_id = current_user.organization_id
    logger.info(f"API: Saving email settings for Org ID: {org_id}, Provider: {settings_input.provider_type}")

    # Assuming save_org_email_settings takes (db, organization_id, settings_data_dict)
    # Your original logic for db_data_to_save might be complex if secrets are handled.
    # For simplicity, assume settings_input.model_dump() is mostly what's needed.
    # The actual encryption/decryption should happen closer to the DB or in a service layer.

    settings_data_for_db = settings_input.model_dump(exclude_unset=True) # Pydantic v2
    # If Pydantic v1: settings_data_for_db = settings_input.dict(exclude_unset=True)


    # Your original logic for AWS key mapping:
    # if settings_input.provider_type == 'aws_ses':
    #      settings_data_for_db['encrypted_api_key'] = settings_input.aws_access_key_id
    #      settings_data_for_db['encrypted_secret_key'] = settings_input.aws_secret_access_key
    #      settings_data_for_db.pop('aws_access_key_id', None)
    #      settings_data_for_db.pop('aws_secret_access_key', None)
    # This mapping should ideally happen in a service layer or within save_org_email_settings
    # if it needs to transform input for DB storage (e.g., encrypting passwords/keys).

    saved_settings_dict = email_settings_db_ops.save_org_email_settings(
        db=db,
        organization_id=org_id,
        settings_data=settings_data_for_db # Pass the Pydantic model or its dict
    )

    if not saved_settings_dict:
        logger.error(f"API Error: Failed to save email settings for Org ID {org_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save email settings."
        )

    logger.info(f"API: Successfully saved email settings for Org ID: {org_id}")
    # Return the saved data, Pydantic will validate against EmailSettingsResponse
    return EmailSettingsResponse(**saved_settings_dict)
