# app/routers/email_settings.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

# Import project modules
from app.schemas import EmailSettingsInput, EmailSettingsResponse, UserPublic
from app.db import database
from app.db.database import get_db
from app.schemas.email_settings import EmailSettings
from app.auth.dependencies import get_current_user
from app.utils.logger import logger

# Define Router
router = APIRouter(
    prefix="/api/v1/email-settings",
    tags=["email-settings"],
)

@router.get("/", response_model=EmailSettings) # Or your specific response model
def get_email_settings( # Changed to 'def' as per original traceback
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve email settings for the current user's organization.
    """

org_id = current_user.organization_id
print(f"API: Getting email settings for Org ID: {org_id}")

settings_data = email_settings_crud.get_org_email_settings_from_db(
    db=db,
    organization_id=org_id
    )
if not settings_data:
    raise HTTPException(status_code=404, detail="Email settings not found for this organization")
return settings_data

# --- GET Endpoint to retrieve email settings ---
@router.get("/", response_model=Optional[EmailSettingsResponse])
def get_email_settings(
    current_user: UserPublic = Depends(get_current_user)
):
    """Retrieves the email sending settings for the current user's organization."""
    org_id = current_user.organization_id
    logger.info(f"API: Getting email settings for Org ID: {org_id}")

    settings_data = database.get_org_email_settings_from_db(org_id)

    if not settings_data:
        logger.info(f"API: No email settings found for Org ID: {org_id}")
        return None # Return None if no settings exist yet

    # Basic check to indicate if necessary credentials *appear* to be set
    # Doesn't validate the actual credentials
    credentials_are_set = False
    provider = settings_data.get("provider_type")
    if provider == 'smtp':
        if settings_data.get("smtp_host") and settings_data.get("smtp_port") and settings_data.get("smtp_username") and settings_data.get("smtp_password"):
            credentials_are_set = True
    elif provider == 'aws_ses':
        # Assuming API keys are stored securely, check if they were ever set (e.g., not None in DB after placeholder decryption)
        # NOTE: Placeholder decryption just returns the value, so check if value exists
        if settings_data.get("api_key") or settings_data.get("access_token"): # Placeholder check - needs real implementation
             # In a real scenario, you might check aws_access_key_id and aws_secret_access_key presence
             # For now, assume if api_key was ever set (even via placeholder) it's configured
             # This logic needs refinement based on how you store SES keys (e.g., separate fields)
             # Let's adjust the DB schema and this check if using dedicated AWS key fields
             # Assuming we store AWS keys in encrypted_api_key for now
             if settings_data.get("api_key"): # Using the decrypted placeholder name
                 credentials_are_set = True

    settings_data["credentials_set"] = credentials_are_set

    # Ensure response model compatibility (handle potential decryption None values)
    # Pydantic should handle Optional fields correctly based on the schema

    logger.info(f"API: Returning email settings for Org ID: {org_id}, Provider: {provider}, Configured: {settings_data.get('is_configured')}")
    return settings_data


# --- PUT Endpoint to create or update email settings ---
@router.put("/", response_model=EmailSettingsResponse)
def set_email_settings(
    settings_input: EmailSettingsInput,
    current_user: UserPublic = Depends(get_current_user)
):
    """
    Creates or updates the email sending settings for the current user's organization.
    Performs an UPSERT based on organization_id.
    """
    org_id = current_user.organization_id
    logger.info(f"API: Saving email settings for Org ID: {org_id}, Provider: {settings_input.provider_type}")

    settings_dict = settings_input.dict(exclude_unset=True) # Exclude fields not sent by client

    # --- TODO: Add validation based on provider_type ---
    # e.g., if provider_type == 'smtp', ensure host, port, user, pass are present
    #       if provider_type == 'aws_ses', ensure relevant keys/region are present

    # Prepare data, potentially separating secrets if DB function expects them differently
    # For now, assume save_org_email_settings handles the dictionary structure
    # Map input fields to potentially different DB storage fields if necessary
    # Example for SES keys if stored differently:
    db_data_to_save = settings_dict.copy()
    if settings_input.provider_type == 'aws_ses':
         # Assuming placeholder _encrypt stores AWS key in 'encrypted_api_key' field
         db_data_to_save['api_key'] = settings_input.aws_access_key_id # Pass to placeholder encryption
         db_data_to_save['smtp_password'] = settings_input.aws_secret_access_key # Reuse password field for secret key
         # Remove the specific AWS keys if not directly stored by those names
         db_data_to_save.pop('aws_access_key_id', None)
         db_data_to_save.pop('aws_secret_access_key', None)


    saved_settings = database.save_org_email_settings(
        organization_id=org_id,
        settings_data=db_data_to_save # Pass the prepared data
    )

    if not saved_settings:
        logger.error(f"API Error: Failed to save email settings for Org ID {org_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save email settings."
        )

    # Re-fetch to return the response model structure (without secrets)
    # Use the same logic as the GET endpoint for consistency
    final_settings = get_email_settings(current_user=current_user) # Reuse GET logic
    if not final_settings: # Should not happen if save succeeded but as failsafe
         logger.error(f"API Error: Saved email settings but failed to retrieve for Org ID {org_id}")
         raise HTTPException(status_code=500, detail="Settings saved but failed to retrieve.")


    logger.info(f"API: Successfully saved email settings for Org ID: {org_id}")
    return final_settings
