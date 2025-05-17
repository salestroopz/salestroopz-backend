# app/core/security.py

import os # Keep for other potential uses, but not for direct SECRET_KEY loading here
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy.orm import Session

# Import your User model and get_db dependency
from app.db.database import get_db # Assuming db_ops is not used here, get_db is standard
from app.db import models as db_models # Use an alias for models to avoid conflict if UserModel is defined here too

# --- Configuration ---
# NOW, WE IMPORT AND USE THE CENTRAL SETTINGS OBJECT
try:
    from app.utils.config import settings
    # Add debug print here to see what settings this file gets
    print(f"CORE_SECURITY_DEBUG: Imported settings.SECRET_KEY = '{settings.SECRET_KEY}'")
    print(f"CORE_SECURITY_DEBUG: Imported settings.ALGORITHM = '{settings.ALGORITHM}'")
except ImportError:
    # This should ideally not happen if your project structure is correct
    print("FATAL ERROR in app/core/security.py: Could not import 'settings' from 'app.utils.config'.")
    # Define dummy settings to prevent immediate crash during further parsing, but app won't work.
    class DummySettings:
        SECRET_KEY = "core_security_dummy_secret_key_if_config_import_fails"
        ALGORITHM = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES = 15
    settings = DummySettings()
    print(f"WARNING in app/core/security.py: Using DUMMY settings for JWT. SECRET_KEY WILL BE WRONG: {settings.SECRET_KEY}")


# The SECRET_KEY check is now effectively handled by config.py and its loading mechanism
# if not settings.SECRET_KEY or settings.SECRET_KEY == "ENV_VAR_NOT_SET_SECRET_KEY" : # Check against your placeholder from config.py
#     # config.py should raise an error or log a critical warning if SECRET_KEY isn't properly set.
#     # This module will now rely on settings.SECRET_KEY being correctly populated.
#     pass


# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# --- Pydantic model for Token Payload ---
class TokenData(BaseModel):
    sub: Optional[EmailStr] = None # Changed from str to EmailStr for consistency
    user_id: Optional[int] = None # If you add user_id to token
    organization_id: Optional[int] = None # If you add org_id to token
    # scopes: List[str] = []


# --- Security Utility Functions ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password: return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception: return False

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    # --- TEMPORARY DEBUGGING (from previous security.py, good to keep for one more test) ---
    print(f"CREATE_TOKEN_DEBUG (core/security.py): Using settings.SECRET_KEY = '{settings.SECRET_KEY}' for signing.")
    print(f"CREATE_TOKEN_DEBUG (core/security.py): Using settings.ALGORITHM = '{settings.ALGORITHM}' for signing.")
    # --- END TEMPORARY DEBUGGING ---

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt
    except Exception as e:
        print(f"CREATE_TOKEN_DEBUG (core/security.py): FAILED during jwt.encode. Error: {str(e)}")
        raise


# --- FastAPI Dependency for Current User ---
async def get_current_user( # This is the primary token decoding point
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> db_models.User: # Use the aliased models.User
    
    # --- TEMPORARY DEBUGGING ---
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): Received token prefix: '{token[:40]}...'")
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): Attempting to decode with settings.SECRET_KEY = '{settings.SECRET_KEY}'")
    print(f"GET_CURRENT_USER_DEBUG (core/security.py): Attempting to decode with algorithms = ['{settings.ALGORITHM}']")
    # --- END TEMPORARY DEBUGGING ---

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials - Invalid token or authentication failure.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        subject: Optional[str] = payload.get("sub")
        
        if subject is None:
            print("GET_CURRENT_USER_DEBUG (core/security.py): Token decoding error: 'sub' claim missing.")
            raise credentials_exception
        
        # Optional: Validate payload structure
        try:
            token_data = TokenData(sub=subject, user_id=payload.get("user_id"), organization_id=payload.get("organization_id"))
            print(f"GET_CURRENT_USER_DEBUG (core/security.py): Successfully decoded. Subject: {token_data.sub}")
        except ValidationError as ve:
            print(f"GET_CURRENT_USER_DEBUG (core/security.py): Token payload validation error: {ve}")
            raise credentials_exception

    except JWTError as e:
        print(f"GET_CURRENT_USER_DEBUG (core/security.py): JWTError FAILED with SECRET_KEY='{settings.SECRET_KEY}'. Error: {str(e)}")
        raise credentials_exception from e
    except Exception as e_unhandled:
        print(f"GET_CURRENT_USER_DEBUG (core/security.py): UNEXPECTED FAILED decoding. Error: {str(e_unhandled)}")
        raise credentials_exception from e_unhandled
    
    # Use db_models.User here
    user = db.query(db_models.User).filter(db_models.User.email == token_data.sub).first()
    
    if user is None:
        print(f"GET_CURRENT_USER_DEBUG (core/security.py): User not found in DB for subject: '{token_data.sub}'")
        raise credentials_exception
    
    return user


async def get_current_active_user(current_user: db_models.User = Depends(get_current_user)) -> db_models.User:
    # Using aliased db_models.User
    if not hasattr(current_user, 'is_active') or not current_user.is_active: # Combine checks
        # Log this scenario
        logger = logging.getLogger(__name__) # Get logger instance if not already available globally
        logger.warning(f"User account is inactive or 'is_active' attribute missing: {getattr(current_user, 'email', 'Unknown Email')}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user or user status misconfigured.")
    return current_user
