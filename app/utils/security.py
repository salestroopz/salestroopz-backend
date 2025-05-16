# app/utils/security.py
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import JWTError, jwt
from app.utils.config import settings # Import your settings
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
    # This block should be indented correctly under the function definition
    if settings.environment == "development":
        print(f"DECODE_TOKEN_DEBUG: Using settings.SECRET_KEY = '{settings.SECRET_KEY}' and ALGORITHMS: ['{settings.ALGORITHM}']")
    # --- END TEMPORARY DEBUGGING ---

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Optional: You could log the decoded payload subject for further confirmation
        # if settings.environment == "development" and payload and payload.get("sub"):
        #     print(f"DECODE_TOKEN_DEBUG: Decoded subject (sub): {payload.get('sub')}")
        return payload
    except JWTError as e:
        # Log the specific JWT error for debugging
        logger.warning(f"JWTError during token decoding: {str(e)}. Token prefix: '{token[:30]}...'")
        return None
    except Exception as e_unhandled: # Catch other potential errors during decoding
        logger.error(f"Unexpected error during token decoding: {str(e_unhandled)}", exc_info=True)
        return None
