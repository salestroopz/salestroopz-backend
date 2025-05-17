# app/auth/dependencies.py (or app/core/dependencies.py)

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import ValidationError # For catching Pydantic validation errors

# --- Application Imports ---
from app.utils import security as security_utils # Your consolidated security utilities
from app.db.database import get_db               # For DB session dependency
from app.db import models as db_models           # Your ORM models (e.g., db_models.User)
from app.db import database as db_ops            # For database operations (e.g., db_ops.get_user_by_email)
from app.schemas import TokenData                # Pydantic model for token payload
from app.utils.logger import logger              # Your application logger

# --- OAuth2 Scheme ---
# Points to your login endpoint that issues tokens
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# --- Dependency Function to Get Current User ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)  # <--- INJECT DATABASE SESSION
) -> db_models.User: # <--- RETURN TYPE IS THE ORM USER MODEL
    """
    FastAPI dependency to verify JWT, extract user identifier, and return the ORM User model.
    Raises HTTPException 401 if authentication fails.
    """
    # --- TEMPORARY DEBUGGING (Keep for one more test run) ---
    print(f"GET_CURRENT_USER_DEBUG (dependencies.py): Received token prefix: '{token[:40]}...'")
    # --- END TEMPORARY DEBUGGING ---

    # Decode the token using the utility function from app.utils.security
    # This function should contain the DECODE_TOKEN_DEBUG prints and use settings.SECRET_KEY
    payload = security_utils.decode_access_token(token)

    if payload is None:
        logger.info("GET_CURRENT_USER_DEBUG (dependencies.py): Payload is None after decode_access_token (token invalid/expired).")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - Token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate payload structure using TokenData Pydantic model
    try:
        # Ensure TokenData schema expects 'sub', 'user_id', 'organization_id' from the payload
        token_data = TokenData.model_validate(payload) # Pydantic V2+
        # token_data = TokenData(**payload) # Pydantic V1 (if payload keys exactly match TokenData fields)
        print(f"GET_CURRENT_USER_DEBUG (dependencies.py): Validated token_data.sub = '{token_data.sub}'")
    except ValidationError as ve:
        print(f"GET_CURRENT_USER_DEBUG (dependencies.py): TokenData Pydantic validation error: {ve}")
        logger.warning(f"Token payload Pydantic validation failed: {ve}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - Malformed token data.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if token_data.sub is None: # 'sub' field (subject, typically email) is essential
        print("GET_CURRENT_USER_DEBUG (dependencies.py): 'sub' (identifier) missing from validated token data.")
        logger.warning("Token payload missing 'sub' (subject) claim.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - User identifier missing in token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fetch the user ORM object from the database using the email from token_data.sub
    user: Optional[db_models.User] = db_ops.get_user_by_email(db=db, email=token_data.sub) # <--- PASS db AND USE .sub

    if user is None:
        print(f"GET_CURRENT_USER_DEBUG (dependencies.py): User not found in DB for identifier: '{token_data.sub}'")
        logger.warning(f"User not found in database for identifier from token: {token_data.sub}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials - User not found.", # User from token does not exist
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # --- TEMPORARY DEBUGGING ---
    print(f"GET_CURRENT_USER_DEBUG (dependencies.py): User {user.email} (ID: {user.id}) authenticated.")
    # --- END TEMPORARY DEBUGGING ---
    return user # Return the ORM User model instance

async def get_current_active_user(
    current_user: db_models.User = Depends(get_current_user) # Depends on the above function
) -> db_models.User: # Return type is the ORM User model
    """
    FastAPI dependency: gets current user from get_current_user and checks if they are active.
    """
    if not hasattr(current_user, 'is_active'):
        logger.error(f"User model (ID: {getattr(current_user, 'id', 'Unknown')}) "
                      f"does not have 'is_active' attribute! Critical misconfiguration.")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User model misconfiguration (is_active).")

    if not current_user.is_active:
        logger.warning(f"Attempt to access by inactive user: {current_user.email}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return current_user
