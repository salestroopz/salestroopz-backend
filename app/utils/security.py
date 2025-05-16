# app/utils/security.py

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from passlib.context import CryptContext
from jose import JWTError, jwt

# Ensure settings are imported from your central config file
# This assumes that app.utils.config defines a 'settings' instance
try:
    from app.utils.config import settings
except ImportError:
    # Fallback or error if settings cannot be imported - this would be a major issue
    print("FATAL ERROR in security.py: Could not import 'settings' from 'app.utils.config'")
    # For the app to even attempt to run, we might define a dummy settings for SECRET_KEY and ALGORITHM
    # This is highly undesirable but prevents immediate crash if config.py itself has issues.
    class DummySettings:
        SECRET_KEY = "fallback_dummy_secret_key_if_config_fails"
        ALGORITHM = "HS256"
        ACCESS_TOKEN_EXPIRE_MINUTES = 15 # A short default
        environment = "unknown" # For the debug print conditions
    settings = DummySettings()
    print(f"WARNING in security.py: Using DUMMY settings because import failed. SECRET_KEY WILL BE WRONG: {settings.SECRET_KEY}")


# Ensure logger is imported or a basic one is set up
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO) # Basic config if main logger not found
    logger.info("Initialized basic logger for security.py.")


# Password Hashing Context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against a hashed password."""
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception as e:
        logger.error(f"Error during password verification: {e}", exc_info=True)
        return False

def get_password_hash(password: str) -> str:
    """Hashes a plain password."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Creates a JWT access token."""
    # --- TEMPORARY DEBUGGING ---
    # This print will execute every time a token is created.
    print(f"CREATE_TOKEN_DEBUG: Using settings.SECRET_KEY = '{settings.SECRET_KEY}' for signing.")
    print(f"CREATE_TOKEN_DEBUG: Using settings.ALGORITHM = '{settings.ALGORITHM}' for signing.")
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
        logger.error(f"Error during JWT encoding: {e}", exc_info=True)
        # In a real scenario, you might raise a specific exception or handle this gracefully.
        # For debugging, knowing it failed here is important.
        print(f"CREATE_TOKEN_DEBUG: FAILED during jwt.encode with SECRET_KEY='{settings.SECRET_KEY}', ALGORITHM='{settings.ALGORITHM}'. Error: {str(e)}")
        raise # Re-raise the exception to make the failure visible during token creation


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decodes an access token. Returns the payload if successful, None otherwise.
    """
    print(f"DEBUG - Top of decode_access_token in security.py. Token prefix: '{token[:40]}...'") # To ensure function is called

    # --- TEMPORARY DEBUGGING ---
    # These prints will execute every time token decoding is attempted.
    print(f"DECODE_TOKEN_DEBUG: Attempting to decode with settings.SECRET_KEY = '{settings.SECRET_KEY}'")
    print(f"DECODE_TOKEN_DEBUG: Attempting to decode with algorithms = ['{settings.ALGORITHM}']")
    # --- END TEMPORARY DEBUGGING ---
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM] # algorithms should be a list
        )
        email_from_payload: Optional[str] = payload.get("sub")
        print(f"DECODE_TOKEN_DEBUG: Successfully decoded. Subject (sub): {email_from_payload}")
        return payload
    except JWTError as e:
        logger.warning(f"JWTError during token decoding: {str(e)}. Token prefix: '{token[:40]}...'")
        print(f"DECODE_TOKEN_DEBUG: JWTError FAILED with SECRET_KEY='{settings.SECRET_KEY}', ALGORITHM='{settings.ALGORITHM}'. Error: {str(e)}")
        return None
    except Exception as e_unhandled: 
        logger.error(f"Unexpected error during token decoding: {str(e_unhandled)}", exc_info=True)
        print(f"DECODE_TOKEN_DEBUG: UNEXPECTED FAILED with SECRET_KEY='{settings.SECRET_KEY}', ALGORITHM='{settings.ALGORITHM}'. Error: {str(e_unhandled)}")
        return None
        # if settings.environment == "development": # Also remove 'if' for this test
        print(f"DECODE_TOKEN_DEBUG: UNEXPECTED FAILED with SECRET_KEY='{settings.SECRET_KEY}', ALGORITHM='{settings.ALGORITHM}'. Error: {str(e_unhandled)}")
        return None
