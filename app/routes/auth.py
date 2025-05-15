# app/routes/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from sqlalchemy.orm import Session # Import Session for type hinting

# --- Import your project modules ---
from app.schemas import UserCreate, UserPublic, Token # Pydantic models
from app.utils import security
from app.db import database # Your database module
from app.db.database import get_db # Dependency to get DB session
from app.utils.config import settings
from app.db import models # Import your ORM models for type hinting if needed, though database functions return them

# --- Create Router ---
router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"]
)

# --- Registration Endpoint ---
@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
async def register_user(user_in: UserCreate, db: Session = Depends(get_db)): # <--- ADDED db: Session
    """
    Handles new user registration.
    - Checks if user email already exists.
    - Creates the organization (or finds existing).
    - Hashes the password.
    - Creates the user in the database linked to the organization.
    - Returns public data of the newly created user.
    """
    # 1. Check if user email already exists
    existing_user_obj: Optional[models.User] = database.get_user_by_email(db=db, email=user_in.email) # <--- PASS db
    if existing_user_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )

    # 2. Handle Organization
    org_obj: Optional[models.Organization] = database.create_organization(db=db, name=user_in.organization_name) # <--- PASS db
    if not org_obj or not hasattr(org_obj, 'id'): # Check if ORM object and id attribute exist
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create or find organization: {user_in.organization_name}."
        )
    org_id = org_obj.id # <--- Access attribute

    # 3. Hash Password
    hashed_password = security.get_password_hash(user_in.password)

    # 4. Create User in Database
    created_user_obj: Optional[models.User] = database.create_user( # <--- PASS db
        db=db,
        email=user_in.email,
        hashed_password=hashed_password,
        organization_id=org_id
    )

    if not created_user_obj:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account after organization check."
        )

    # 5. Return Public User Data
    # Pydantic's UserPublic can be created from the ORM object if orm_mode=True (Config.orm_mode = True) is set in UserPublic schema
    # If UserPublic is already configured with orm_mode=True:
    return UserPublic.from_orm(created_user_obj)
    # Alternatively, manually construct the dictionary if orm_mode is not set or for explicit mapping:
    # return UserPublic(
    #     id=created_user_obj.id,
    #     email=created_user_obj.email,
    #     organization_id=created_user_obj.organization_id,
    #     # Add any other fields UserPublic expects from the User model
    #     # For example, if UserPublic needs organization_name:
    #     # organization_name=org_obj.name # Assuming org_obj is still in scope and correct
    # )


# --- Login/Token Endpoint ---
@router.post("/token", response_model=Token)
# async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()): # OLD
async def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    user_obj = database.get_user_by_email(db=db, email=form_data.username)

    if not user_obj or not user_obj.is_active or not security.verify_password(form_data.password, user_obj.hashed_password): # ADDED user_obj.is_active CHECK
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password, or account disabled", # Updated detail
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Create JWT Token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    # Prepare data for the token. Add more claims if needed (e.g., user_id, organization_id)
    token_data = {
        "sub": user_obj.email, # Subject is typically the username/email
        "user_id": user_obj.id,
        "organization_id": user_obj.organization_id # Assuming User model has organization_id
    }
    access_token = security.create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )

    # 4. Return the token
    return Token(access_token=access_token, token_type="bearer") # Use Pydantic model for response
