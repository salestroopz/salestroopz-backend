# app/core/security.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any

# Import the CONSOLIDATED security utilities
from app.utils import security as security_utils # Or directly: from app.utils.security import decode_access_token, verify_password etc.
from app.db.database import get_db
from app.db import models as db_models
# from app.utils.config import settings # Not strictly needed here if security_utils uses it
from app.utils.logger import logger


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> db_models.User:
    # --- TEMPORARY DEBUGGING ---
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): Received token prefix: '{token[:40]}...'")
    # --- END TEMPORARY DEBUGGING ---

    credentials_exception = HTTPException(...)

    # Call the consolidated decode function
    payload = security_utils.decode_access_token(token) # This will have your DECODE_TOKEN_DEBUG prints

    if payload is None:
        logger.info("GET_CURRENT_USER_DEBUG: Payload is None after decode_access_token call.")
        raise credentials_exception
    
    email: Optional[str] = payload.get("sub")
    if email is None: # ... handle error ...
        raise credentials_exception

    user = db.query(db_models.User).filter(db_models.User.email == email).first()
    if user is None: # ... handle error ...
        raise credentials_exception
    return user

async def get_current_active_user(current_user: db_models.User = Depends(get_current_user)) -> db_models.User:
    if not hasattr(current_user, 'is_active') or not current_user.is_active:
        logger.warning(f"User account is inactive or 'is_active' missing: {getattr(current_user, 'email', 'Unknown')}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user or misconfigured.")
    return current_user
