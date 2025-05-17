# app/core/security.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional # For type hints

# --- Application Imports ---
# Import the CONSOLIDATED security utilities from app.utils.security
# This module should contain create_access_token, decode_access_token, etc.
# and should use app.utils.config.settings internally.
try:
    from app.utils import security as security_utils
except ImportError as e_sec_utils:
    print(f"FATAL ERROR in app/core/security.py: Could not import 'security' from 'app.utils': {e_sec_utils}")
    raise SystemExit("Core security utilities not found.") from e_sec_utils

# Import database session and models
try:
    from app.db.database import get_db # For DB session dependency
    from app.db import models as db_models # Using an alias for clarity (e.g., db_models.User)
    from app.db import database as db_ops # For calling database functions like get_user_by_email
except ImportError as e_db_core:
    print(f"FATAL ERROR in app/core/security.py: Could not import database components: {e_db_core}")
    raise SystemExit("Database components not found.") from e_db_core

# Import Pydantic schemas
try:
    from app.schemas import TokenData # Pydantic model for validating token payload
except ImportError as e_schemas:
    print(f"Warning in app/core/security.py: Could not import 'TokenData' from 'app.schemas': {e_schemas}")
    TokenData = None # Define as None; payload validation might be skipped or fail

# Import logger
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    if not logger.hasHandlers(): # Add basic handler only if no handlers are configured
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        logger.info("Initialized basic logger for app/core/security.py.")


# --- OAuth2 Scheme ---
# The tokenUrl should point to your API endpoint that issues tokens (your login route)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") # Make sure this matches your auth router

# --- FastAPI Dependency for Current User ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> db_models.User: # Return type is your ORM User model
    """
    FastAPI dependency to get current authenticated user from JWT.
    Validates token, extracts user identifier (subject), fetches user from DB.
    """
    # --- TEMPORARY DEBUGGING (Keep these for one more test run) ---
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): Received token prefix: '{token[:40]}...'")
    # --- END TEMPORARY DEBUGGING ---

    # The decode_access_token function from app.utils.security now handles
    # internal logging of SECRET_KEY and ALGORITHM used for decoding.
    payload = security_utils.decode_access_token(token)

    if payload is None:
        # decode_access_token already logs the JWTError with details.
        # No need to print SECRET_KEY here again as decode_access_token does it.
        logger.info("GET_CURRENT_USER_DEBUG (core/security.py): Payload is None after decode_access_token call (token invalid or expired).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - Token invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate payload structure using TokenData Pydantic model from schemas
    try:
        if TokenData is None: # Check if TokenData was imported
            logger.error("GET_CURRENT_USER_DEBUG (core/security.py): TokenData schema not available for validation.")
            # Fallback to direct payload access, less safe
            subject_email_or_id: Optional[str] = payload.get("sub")
        else:
            token_data_obj = TokenData.model_validate(payload) # Pydantic V2+
            # token_data_obj = TokenData(**payload) # Pydantic V1
            subject_email_or_id: Optional[str] = token_data_obj.sub # Use .sub as defined in TokenData
            print(f"GET_CURRENT_USER_DEBUG (core/security.py): Validated token_data.sub = '{subject_email_or_id}'")

    except ValidationError as ve: # Import ValidationError from pydantic
        print(f"GET_CURRENT_USER_DEBUG (core/security.py): Token payload Pydantic validation error: {ve}")
        logger.warning(f"Token payload Pydantic validation failed: {ve}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - Invalid token data structure.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if subject_email_or_id is None:
        print("GET_CURRENT_USER_DEBUG (core/security.py): 'sub' (identifier) missing from validated token data.")
        logger.warning("Token payload missing 'sub' (subject) claim.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - User identifier missing in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch user from DB using the 'sub' claim (assumed to be email)
    user = db_ops.get_user_by_email(db, email=subject_email_or_id) # Use db_ops for database functions

    if user is None:
        print(f"GET_CURRENT_USER_DEBUG (core/security.py): User not found in DB for identifier: '{subject_email_or_id}'")
        logger.warning(f"User not found in database for identifier from token: {subject_email_or_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - User not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # --- TEMPORARY DEBUGGING ---
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): User {user.email} (ID: {user.id}) authenticated successfully.")
    # --- END TEMPORARY DEBUGGING ---
    return user


async def get_current_active_user(current_user: db_models.User = Depends(get_current_user)) -> db_models.User:
    """
    FastAPI dependency: gets current user from get_current_user and checks if they are active.
    """
    if not hasattr(current_user, 'is_active'):
        logger.error(f"User model (ID: {getattr(current_user, 'id', 'Unknown')}) "
                      f"does not have 'is_active' attribute! Critical misconfiguration.")
        # This is a server error because the User model should always have is_active
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User model misconfiguration (is_active).")

    if not current_user.is_active:
        logger.warning(f"Attempt to access by inactive user: {current_user.email}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user") # Changed to 403
    return current_user

# You would no longer define create_access_token, verify_password, get_password_hash, SECRET_KEY, ALGORITHM etc. here.
# They should all reside in app.utils.security.py and be imported if needed, or used via security_utils.
