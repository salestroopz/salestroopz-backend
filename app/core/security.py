# app/core/security.py

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Any, Dict, List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, ValidationError
from sqlalchemy.orm import Session

# Import your User model and get_db dependency
# Adjust these imports based on your project structure
from app.db.database import get_db # Standard get_db dependency
from app.db.models import User as UserModel # Your SQLAlchemy User model

# --- Configuration ---
# Load sensitive values from environment variables for security
# For local development, you can set these in a .env file and use python-dotenv
# On Render, set these in your service's Environment Variables settings.

# JWT Secret Key: Generate a strong random key (e.g., using openssl rand -hex 32)
# and store it in an environment variable like JWT_SECRET_KEY.
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    # Fallback for local development only - DO NOT USE THIS IN PRODUCTION
 #  print("WARNING: JWT_SECRET_KEY not set, using a default insecure key. SET THIS IN PRODUCTION!")
 #  SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7" # Example, replace
raise ValueError("FATAL: JWT_SECRET_KEY environment variable is not set or is empty. Application cannot start.")
ALGORITHM = "HS256" # Algorithm for signing the JWT
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")) # Default to 30 minutes
# --- Password Hashing ---
# Uses bcrypt as the hashing scheme
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# --- OAuth2 Scheme ---
# The tokenUrl should point to your endpoint that issues tokens (e.g., your login route)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token") # Adjust if your path is different

# --- Pydantic model for Token Payload (data inside the JWT) ---
class TokenData(BaseModel):
    # 'sub' (subject) usually stores the unique identifier of the user, e.g., email or user_id
    sub: Optional[str] = None
    # You can add other custom claims like user_id, scopes, etc.
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
    The 'data' dictionary should contain the claims for the token (e.g., {"sub": user_email}).
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def _get_user_by_subject(db: Session, subject: str) -> Optional[UserModel]:
    """
    Helper function to fetch a user from the database by their subject claim (e.g., email).
    Adjust this if your 'sub' claim stores something other than email, or if your User model
    has a different unique identifier (e.g., username).
    """
    # Assuming 'sub' claim in your JWT is the user's email
    return db.query(UserModel).filter(UserModel.email == subject).first()

# --- FastAPI Dependency for Current User ---
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> UserModel:
    """
    FastAPI dependency to get the current authenticated user from the JWT in the Authorization header.
    Validates the token, extracts the user identifier (subject), and fetches the user from the database.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not SECRET_KEY: # Should have been caught at startup, but good to double check
        print("FATAL ERROR IN get_current_user: JWT_SECRET_KEY is not configured.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server configuration error related to authentication."
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject: Optional[str] = payload.get("sub") # 'sub' (subject) typically holds the username/email
        
        if subject is None:
            print("Token decoding error: 'sub' claim missing from JWT payload.")
            raise credentials_exception
        
        # You might parse into TokenData for validation if you have more complex claims
        # token_data = TokenData(sub=subject)

    except JWTError as e:
        print(f"JWTError during token decoding: {e}")
        raise credentials_exception
    except ValidationError as e: # If using Pydantic model for payload
        print(f"TokenData ValidationError: {e}")
        raise credentials_exception
    
    user = _get_user_by_subject(db, subject=subject)
    
    if user is None:
        print(f"User not found in DB for subject: {subject}")
        raise credentials_exception
    
    return user

async def get_current_active_user(current_user: UserModel = Depends(get_current_user)) -> UserModel:
    """
    FastAPI dependency that builds on get_current_user to also check if the user is active.
    Assumes your UserModel has an 'is_active' boolean attribute.
    """
    if not hasattr(current_user, 'is_active'):
        # This indicates a mismatch between the UserModel and this function's expectation.
        # For now, we'll assume if is_active is missing, the user is considered active.
        # Log a warning in a real scenario.
        print(f"WARNING: User model (ID: {current_user.id}) does not have 'is_active' attribute. Assuming active.")
        return current_user

    if not current_user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user

# --- Example of how you might use this in a router ---
# from fastapi import APIRouter
# from .security import get_current_active_user
# from ..models import User as UserModel
#
# router = APIRouter()
#
# @router.get("/users/me/", response_model=YourUserReadSchema) # Replace YourUserReadSchema
# async def read_users_me(current_user: UserModel = Depends(get_current_active_user)):
#     return current_user
