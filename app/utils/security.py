# app/utils/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any # Combined typing imports

from passlib.context import CryptContext
from jose import JWTError, jwt

from app.utils.config import settings # Import your settings instance
from app.utils.logger import logger # Your application's logger

# Password Hashing Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e: # Catch potential errors from passlib, e.g., if hash is malformed or unknown scheme
        logger.error(f"Error during password verification: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    # --- TEMPORARY DEBUGGING ---
    # Remove 'if' condition temporarily to ensure it always prints during this test
    # if settings.environment == "development":
    print(f"CREATE_TOKEN_DEBUG: Using settings.SECRET_KEY = '{settings.SECRET_KEY}' for signing.")
    print(f"CREATE_TOKEN_DEBUG: Using settings.ALGORITHM = '{settings.ALGORITHM}' for signing.")
    # --- END TEMPORARY DEBUGGING ---

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)}) # Add 'iat' (issued at) claim
    
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes an access token. Returns the payload if successful, None otherwise.
    """
    # --- TEMPORARY DEBUGGING ---
    # Remove 'if' condition temporarily to ensure it always prints during this test
    # if settings.environment == "development":
    print(f"DECODE_TOKEN_DEBUG: Attempting to decode with settings.SECRET_KEY = '{settings.SECRET_KEY}'")
    print(f"DECODE_TOKEN_DEBUG: Attempting to decode with algorithms = ['{settings.ALGORITHM}']")
    # --- END TEMPORARY DEBUGGING ---
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM] # algorithms should be a list
        )
        # Optional: Log successful decoding subject
        # email_from_payload: Optional[str] = payload.get("sub")
        # if settings.environment == "development" and email_from_payload:
        # print(f"DECODE_TOKEN_DEBUG: Successfully decoded. Subject (sub): {email_from_payload}")
        return payload
    except JWTError as e:
        # This is where "Signature verification failed" and other JWT errors (like expired) are caught
        logger.warning(f"JWTError during token decoding: {str(e)}. Token prefix: '{token[:40]}...'")
        # if settings.environment == "development": # Also remove 'if' for this test
        print(f"DECODE_TOKEN_DEBUG: JWTError FAILED with SECRET_KEY='{settings.SECRET_KEY}', ALGORITHM='{settings.ALGORITHM}'. Error: {str(e)}")
        return None
    except Exception as e_unhandled: # Catch any other unexpected errors during decoding
        logger.error(f"Unexpected error during token decoding: {str(e_unhandled)}", exc_info=True)
        # if settings.environment == "development": # Also remove 'if' for this test
        print(f"DECODE_TOKEN_DEBUG: UNEXPECTED FAILED with SECRET_KEY='{settings.SECRET_KEY}', ALGORITHM='{settings.ALGORITHM}'. Error: {str(e_unhandled)}")
        return None
