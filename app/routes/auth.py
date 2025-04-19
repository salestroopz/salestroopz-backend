# app/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm # For the standard login form
from datetime import timedelta

# --- Import your project modules ---
from app.schemas import UserCreate, UserPublic, Token # Pydantic models for request/response
from app.utils import security                   # Password hashing, token creation
from app.db import database                      # Database interaction functions
from app.utils.config import settings              # Configuration (token expiry)

# --- Create Router ---
router = APIRouter(
    prefix="/api/v1/auth", # Base path for all routes in this file
    tags=["Authentication"] # Tag for grouping in API documentation (/docs)
)

# --- Registration Endpoint ---
@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate):
    """
    Handles new user registration.
    - Checks if user email already exists.
    - Creates the organization (or finds existing - current basic logic creates).
    - Hashes the password.
    - Creates the user in the database linked to the organization.
    - Returns public data of the newly created user.
    """
    # 1. Check if user email already exists
    existing_user = database.get_user_by_email(user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )

    # 2. Handle Organization
    # Attempt to create organization. The DB function handles potential name conflicts
    # by returning the existing org data if the name is already taken.
    org_data = database.create_organization(user_in.organization_name)
    if org_data is None or 'id' not in org_data:
         # This might happen if DB error occurs during creation/lookup
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail=f"Could not create or find organization: {user_in.organization_name}."
         )
    org_id = org_data['id']

    # 3. Hash Password
    hashed_password = security.get_password_hash(user_in.password)

    # 4. Create User in Database
    created_user_dict = database.create_user(
        email=user_in.email,
        hashed_password=hashed_password,
        organization_id=org_id
    )

    if created_user_dict is None:
         # This could happen if there was a race condition or unexpected DB error
         raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="Failed to create user account after organization check."
         )

    # 5. Return Public User Data (using Pydantic model for validation/structure)
    # The create_user function now returns a dict matching UserPublic needs
    try:
        return UserPublic(**created_user_dict)
    except Exception as e:
        print(f"Error mapping created user dict to UserPublic: {e} - Data: {created_user_dict}")
        raise HTTPException(
             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
             detail="User created but failed preparing response."
         )


# --- Login/Token Endpoint ---
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticates user based on email (passed as 'username') and password.
    Uses standard OAuth2 password flow form data.
    Returns a JWT access token upon successful authentication.
    """
    # 1. Fetch user by email (form_data.username contains the email)
    user = database.get_user_by_email(email=form_data.username)

    # 2. Verify user exists and password is correct
    if not user or not security.verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            # Standard header required for OAuth2 Password Bearer flow on failure
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Create JWT Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = security.create_access_token(
        # Data to encode in the token payload. "sub" (subject) is standard.
        data={"sub": user["email"]}, # Using email as the subject identifier
        expires_delta=access_token_expires
    )

    # 4. Return the token
    return {"access_token": access_token, "token_type": "bearer"}
