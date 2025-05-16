# app/utils/security.py
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.utils.config import settings # Import your settings
from app.utils.logger import logger
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from passlib.context import CryptContext

# Password Hashing Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    print(f"CREATE_TOKEN_DEBUG: Using settings.SECRET_KEY = '{settings.SECRET_KEY}'")
    """Creates a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    # --- TEMPORARY DEBUGGING ---
    # Ensure settings are imported correctly and are the same instance
    if settings.environment == "development": # Or remove the if for one test
        print(f"DECODE_TOKEN_DEBUG: Attempting to decode using settings.SECRET_KEY = '{settings.SECRET_KEY}'")
        print(f"DECODE_TOKEN_DEBUG: Attempting to decode using settings.ALGORITHM = '{settings.ALGORITHM}'")
    # --- END TEMPORARY DEBUGGING ---
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY, # Must be the same as used in create_access_token
            algorithms=[settings.ALGORITHM] # Must be the same
        )
        # You could also print the email from payload here to see if decoding gets that far before signature check
        # email: Optional[str] = payload.get("sub")
        # if settings.environment == "development" and email:
        #    print(f"DECODE_TOKEN_DEBUG: Successfully decoded subject (sub): {email}")
        return payload
    except JWTError as e:
        logger.warning(f"JWTError during token decoding: {str(e)}. Token prefix: '{token[:30]}...'") # Keep this log
        # If you added the print above, you can see if the keys were different before this exception
        if settings.environment == "development":
            print(f"DECODE_TOKEN_DEBUG: FAILED with SECRET_KEY = '{settings.SECRET_KEY}' and ALGORITHM = '{settings.ALGORITHM}'")
        return None
    except Exception as e_unhandled:
        logger.error(f"Unexpected error during token decoding: {str(e_unhandled)}", exc_info=True)
        if settings.environment == "development":
            print(f"DECODE_TOKEN_DEBUG: UNEXPECTED FAILED with SECRET_KEY = '{settings.SECRET_KEY}' and ALGORITHM = '{settings.ALGORITHM}'")
        return None
