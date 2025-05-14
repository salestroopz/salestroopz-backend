# app/core/security.py

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict, List # Ensure all necessary types are imported

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, ValidationError # Make sure BaseModel is imported
from sqlalchemy.orm import Session

# Import your User model and get_db dependency
from app.db.database import get_db
from app.db.models import User as UserModel

# --- Configuration ---
# Load sensitive values from environment variables.
# On Render, set these in your service's Environment Variables settings.

# JWT Secret Key:
# This key is used for signing and verifying JWTs. It MUST be kept secret.
# Generate a strong random key (e.g., using 'openssl rand -hex 32' in your terminal)
# and store it in an environment variable named JWT_SECRET_KEY.
SECRET_KEY = os.getenv("JWT_SECRET_KEY")

# Critical check: If JWT_SECRET_KEY is not set in the environment, the application
# cannot securely handle authentication and should not start.
if not SECRET_KEY:
    # This error will be raised when the module is first imported if the env var is missing.
    raise ValueError(
        "FATAL SECURITY ERROR: JWT_SECRET_KEY environment variable is not set or is empty. "
        "Application cannot start securely. Please set this environment variable."
    )

ALGORITHM = "HS256"  # Algorithm for signing the JWT
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")) # Default to 30 minutes

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
# The tokenUrl should point to your API endpoint that issues tokens (your login route)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") # Adjust if your login path is different

# --- Pydantic model for Token Payload (data inside the JWT) ---
class TokenData(BaseModel): # Ensure this inherits from pydantic.BaseModel
    sub: Optional[str] = None # 'sub' (subject) usually stores the unique identifier (e.g., email)
    # You can add other custom claims here if needed:
    # user_id: Optional[int] = None
    # scopes: List[str] = []


# --- Security Utility Functions ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a new JWT access token.
    'data' dictionary should contain the claims (e.g., {"sub": user_email}).
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    # Use the SECRET_KEY loaded from the environment for encoding
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def _get_user_by_subject(db: Session, subject: str) -> Optional[UserModel]:
    """
    Helper to fetch a user from DB by subject claim (e.g., email).
    Assumes 'sub' claim in JWT is the user's email. Adjust if different.
    """
    return db.query(UserModel).filter(UserModel.email == subject).first()

# --- FastAPI Dependency for Current User ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserModel:
    """
    FastAPI dependency to get current authenticated user from JWT.
    Validates token, extracts user identifier (subject), fetches user from DB.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials - Invalid token or authentication failure.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    # The SECRET_KEY check at the module level should prevent the app from starting
    # if it's not set. This internal check is an additional safeguard, though redundant
    # if the initial check works as expected.
    if not SECRET_KEY:
        # This path should ideally not be reached if the module-level check is effective.
        print("CRITICAL INTERNAL ERROR in get_current_user: SECRET_KEY is unexpectedly None or empty.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server misconfiguration for authentication."
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]) # Use SECRET_KEY for decoding
        subject: Optional[str] = payload.get("sub")
        
        if subject is None:
            print("Token decoding error: 'sub' claim missing from JWT payload.")
            raise credentials_exception
        
        # Optional: Validate payload structure if using TokenData for more complex claims
        # try:
        #     token_data = TokenData(sub=subject, ...) # Add other fields if validating
        # except ValidationError as ve:
        #     print(f"Token payload validation error: {ve}")
        #     raise credentials_exception

    except JWTError as e:
        # This includes signature verification errors, expired tokens, etc.
        print(f"JWTError during token decoding: {e}. Token: '{token[:30]}...'") # Log part of token for context
        raise credentials_exception
    
    user = _get_user_by_subject(db, subject=subject)
    
    if user is None:
        print(f"User not found in DB for subject/identifier: '{subject}' from token.")
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    """
    FastAPI dependency: gets current user and checks if they are active.
    Assumes UserModel has an 'is_active' boolean attribute.
    """
    # It's good practice to check if the attribute exists before accessing it
    if not hasattr(current_user, 'is_active'):
        print(f"WARNING: User model (ID: {getattr(current_user, 'id', 'Unknown')}) "
              f"does not have 'is_active' attribute. Assuming active by default for now.")
        # Depending on your security policy, you might want to:
        # 1. Raise an error: raise HTTPException(status_code=500, detail="User model misconfiguration")
        # 2. Treat as inactive: raise HTTPException(status_code=400, detail="User status cannot be determined")
        # 3. Or proceed (as done here, with a warning)
        return current_user # Proceeding, assuming active if attribute is missing

    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user
