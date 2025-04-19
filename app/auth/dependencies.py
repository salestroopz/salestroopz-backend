# app/auth/dependencies.py

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError # JWTError is used by security.decode_access_token but not directly here typically
from typing import Optional

# --- Import necessary modules ---
from app.utils import security       # For decode_access_token
from app.db import database          # For get_user_by_email
from app.schemas import TokenData, UserPublic # For Pydantic models

# --- Define the OAuth2 Scheme ---
# This tells FastAPI how to find the token.
# The tokenUrl should point to your actual login endpoint.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# --- Define the Dependency Function ---
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserPublic:
    """
    FastAPI dependency to verify JWT token from the Authorization header
    and return the current authenticated user's public data.

    Raises HTTPException 401 if the token is invalid, expired, or the user
    associated with the token doesn't exist.
    """
    # Define the exception to raise if authentication fails
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}, # Standard header for 401 Bearer auth
    )

    # Decode the token using the utility function
    payload = security.decode_access_token(token)
    if payload is None: # Token invalid or expired
        print("Auth Error: Token decode failed (invalid or expired)")
        raise credentials_exception

    # Extract the subject (email) from the token payload
    # We used 'sub' when creating the token in auth.py
    email: Optional[str] = payload.get("sub")
    if email is None:
        print("Auth Error: Email ('sub') not found in token payload")
        raise credentials_exception

    # Use the TokenData schema (optional but good for clarity)
    token_data = TokenData(email=email)

    # Fetch the user from the database using the email from the token
    # Note: This hits the DB for every authenticated request.
    user_dict = database.get_user_by_email(email=token_data.email)
    if user_dict is None:
        print(f"Auth Error: User with email '{token_data.email}' from token not found in DB")
        raise credentials_exception

    # Convert the dictionary returned from the DB into our Pydantic UserPublic model
    # This ensures the function returns a consistent, typed object.
    # It also implicitly validates that the DB returned the expected fields.
    try:
        user = UserPublic(**user_dict)
    except Exception as e: # Catch potential validation errors if DB dict mismatches schema
         print(f"Auth Error: Failed to map DB user data to UserPublic schema for email '{token_data.email}': {e}")
         raise credentials_exception # Treat mapping failure as an auth failure

    # Return the authenticated user object
    return user
