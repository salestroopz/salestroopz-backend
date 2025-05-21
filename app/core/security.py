# app/core/security.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any # Consolidated typing imports

# --- Application Imports ---
# Import the CONSOLIDATED security utilities from app.utils.security
try:
    from app.utils import security as security_utils # Contains decode_access_token
except ImportError as e_sec_utils:
    # Using print as logger might not be configured yet if this fails during initial imports
    print(f"FATAL ERROR in app/core/security.py: Could not import 'security' from 'app.utils': {e_sec_utils}")
    raise SystemExit("Core security utilities not found.") from e_sec_utils

# Import database session and models
try:
    from app.db.database import get_db               # For DB session dependency
    from app.db import models as db_models           # Using an alias for ORM models (e.g., db_models.User)
    from app.db import database as db_ops            # For calling database functions (e.g., db_ops.get_user_by_email)
except ImportError as e_db_core:
    print(f"FATAL ERROR in app/core/security.py: Could not import database components: {e_db_core}")
    raise SystemExit("Database components not found.") from e_db_core

# Import Pydantic schemas for token data validation
try:
    from app.schemas import TokenData
    from pydantic import ValidationError # For catching Pydantic validation errors
except ImportError as e_schemas:
    print(f"Warning in app/core/security.py: Could not import 'TokenData' or 'ValidationError' from 'app.schemas': {e_schemas}")
    TokenData = None # Define as None; payload validation might be skipped or fail
    ValidationError = None # Define as None; will cause issues if try-except relies on it

# Import logger
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers():
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.info("Initialized basic logger for app/core/security.py.")


# --- OAuth2 Scheme ---
# The tokenUrl should point to your API endpoint that issues tokens (your login route)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# --- FastAPI Dependency for Current User ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)  # Injects database session
) -> db_models.User: # Return type is your ORM User model
    """
    FastAPI dependency to get current authenticated user from JWT.
    Validates token, extracts user identifier (subject), fetches user from DB.
    """
    # --- TEMPORARY DEBUGGING (Remove after verifying JWT flow) ---
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): Received token prefix: '{token[:40]}...'")
    # --- END TEMPORARY DEBUGGING ---

    # Call the centralized decode_access_token function from app.utils.security
    # This function should contain its own DECODE_TOKEN_DEBUG prints
    payload: Optional[Dict[str, Any]] = security_utils.decode_access_token(token)

    if payload is None:
        # security_utils.decode_access_token already logs/prints JWTError details
        logger.info("GET_CURRENT_USER_DEBUG (core/security.py): Payload is None (token invalid, expired, or decode failed).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject_email_or_id: Optional[str] = None
    # Validate payload structure using TokenData Pydantic model from schemas
    if TokenData and ValidationError: # Check if schema and exception were imported
        try:
            token_data_obj = TokenData.model_validate(payload) # Pydantic V2+
            # token_data_obj = TokenData(**payload) # Pydantic V1 (if payload keys exactly match)
            subject_email_or_id = token_data_obj.sub # Use .sub as defined in TokenData for the email/identifier
            print(f"GET_CURRENT_USER_DEBUG (core/security.py): Validated token_data.sub = '{subject_email_or_id}'")
        except ValidationError as ve:
            print(f"GET_CURRENT_USER_DEBUG (core/security.py): Token payload Pydantic validation error: {ve}")
            logger.warning(f"Token payload Pydantic validation failed: {ve}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials - Invalid token data structure.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif TokenData is None: # Fallback if TokenData schema couldn't be imported
        logger.warning("GET_CURRENT_USER_DEBUG (core/security.py): TokenData schema not available, falling back to direct payload access for 'sub'.")
        subject_email_or_id = payload.get("sub")
    else: # ValidationError not imported, implies Pydantic might not be fully available
        logger.error("GET_CURRENT_USER_DEBUG (core/security.py): Pydantic ValidationError not imported, cannot validate token payload robustly.")
        subject_email_or_id = payload.get("sub")


    if subject_email_or_id is None:
        print("GET_CURRENT_USER_DEBUG (core/security.py): 'sub' (identifier) missing from token payload after validation/access.")
        logger.warning("Token payload missing 'sub' (subject) claim.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - User identifier missing in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user ORM object from the database
    user: Optional[db_models.User] = db_ops.get_user_by_email(db=db, email=subject_email_or_id)

    if user is None:
        print(f"GET_CURRENT_USER_DEBUG (core/security.py): User not found in DB for identifier: '{subject_email_or_id}'")
        logger.warning(f"User not found in database for identifier from token: {subject_email_or_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # --- TEMPORARY DEBUGGING (Remove after verifying JWT flow) ---
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): User {user.email} (ID: {user.id}) authenticated successfully.")
    # --- END TEMPORARY DEBUGGING ---
    return user


async def get_current_active_user(
    current_user: db_models.User = Depends(get_current_user) # Depends on the above function
) -> db_models.User: # Return type is the ORM User model
    """
    FastAPI dependency: gets current user from get_current_user and checks if they are active.
    """
    if not hasattr(current_user, 'is_active'):
        # This indicates a problem with the User model definition itself.
        logger.error(f"CRITICAL User model (ID: {getattr(current_user, 'id', 'Unknown')}) "
                      f"does not have 'is_active' attribute! Check app/db/models.py.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User model misconfiguration (is_active attribute missing)."
        )

    if not current_user.is_active:
        logger.warning(f"Attempt to access by inactive user: {current_user.email}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user

# Note: Core JWT logic like SECRET_KEY, ALGORITHM, create_access_token, verify_password,
# get_password_hash, and pwd_context should now exclusively reside in 'app.utils.security.py'.
# This file, 'app.core.security.py', now only defines the FastAPI dependencies
# that consume those utilities.
