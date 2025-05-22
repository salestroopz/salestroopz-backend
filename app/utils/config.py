# app/utils/config.py

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from pathlib import Path
import warnings
from pydantic import Field # Keep this if used elsewhere
from typing import Optional, List

# Determine the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file from the project root directory for local development
dotenv_path = BASE_DIR / '.env'
if dotenv_path.exists(): # Only load if .env exists
    load_dotenv(dotenv_path=dotenv_path)
else:
    # Use basic print as logger might not be initialized yet
    print(f"Info: .env file not found at {dotenv_path}, skipping python-dotenv load.")


def get_secret_key_from_file_or_env(default_value="ENV_VAR_NOT_SET_SECRET_KEY") -> str:
    """
    Tries to read SECRET_KEY from Render's secret file path first,
    then falls back to environment variable, then to a default.
    """
    secret_file_path = Path("/etc/secrets/SECRET_KEY")
    secret_key_value = None

    if secret_file_path.exists() and secret_file_path.is_file():
        try:
            secret_key_value = secret_file_path.read_text().strip()
            if secret_key_value:
                print(f"Info: Loaded SECRET_KEY from secret file: {str(secret_file_path)}") # Use print before logger
                return secret_key_value
            else:
                print(f"Warning: Secret file {str(secret_file_path)} is empty.")
        except Exception as e:
            print(f"Warning: Could not read secret file {str(secret_file_path)}: {e}")

    # Fallback to environment variable if file method fails or doesn't yield a value
    secret_key_value = os.getenv("SECRET_KEY")
    if secret_key_value:
        print(f"Info: Loaded SECRET_KEY from environment variable.") # Use print before logger
        return secret_key_value
    
    print(f"Warning: SECRET_KEY not found in secret file or environment variable. Using default.") # Use print
    return default_value


class Settings(BaseSettings):
    app_name: str = "SalesTroopz"
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@example.com")
    environment: str = os.getenv("ENVIRONMENT", "development")

    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'salestroopz.db'}")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "ENV_VAR_NOT_SET")

    # Use the helper function to get SECRET_KEY
    SECRET_KEY: str = get_secret_key_from_file_or_env() # <--- MODIFIED HERE
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 1)))

    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,https://your-streamlit-app-name.onrender.com")

    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    DEFAULT_SENDER_EMAIL: Optional[str] = os.getenv("DEFAULT_SENDER_EMAIL")
    DEFAULT_SENDER_NAME: str = os.getenv("DEFAULT_SENDER_NAME", "SalesTroopz Platform")

    ENABLE_EMAIL_SCHEDULER: bool = Field(default=True, description="Enable the periodic email sending worker")
    EMAIL_SCHEDULER_INTERVAL_MINUTES: int = Field(default=5, gt=0, description="How often the email sender runs")
    ENABLE_IMAP_REPLY_POLLER: bool = Field(default=True, description="Enable the periodic IMAP reply poller")
    IMAP_POLLER_INTERVAL_MINUTES: int = Field(default=10, gt=0, description="How often the IMAP poller runs")

    STRIPE_PUBLISHABLE_KEY: Optional[str] = os.getenv("STRIPE_PUBLISHABLE_KEY")
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET") # For later webhook verification
  
    
    @property
    def allowed_origins_list(self) -> List[str]:
        if not self.ALLOWED_ORIGINS: # Handle if ALLOWED_ORIGINS itself could be None/empty
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        case_sensitive = True
        # If using python-dotenv at top, pydantic's own .env loading is not strictly needed here
        # but can be a fallback if you prefer Pydantic to manage .env.
        # env_file = '.env'
        # env_file_encoding = 'utf-8'


settings = Settings()
# Debug print for Stripe key (can be removed after verification)
print(f"CONFIG_DEBUG: Loaded settings.STRIPE_SECRET_KEY = '{settings.STRIPE_SECRET_KEY}'")
print(f"CONFIG_DEBUG: Loaded settings.STRIPE_PUBLISHABLE_KEY = '{settings.STRIPE_PUBLISHABLE_KEY}'")
print(f"CONFIG_DEBUG: Loaded settings.SECRET_KEY = '{settings.SECRET_KEY}'")
# --- Configuration Warnings (Adjust default value used in check) ---
if settings.SECRET_KEY == "ENV_VAR_NOT_SET_SECRET_KEY": # This check remains valid for the default case
    warnings.warn("SECURITY WARNING: SECRET_KEY could not be loaded from secret file or environment, using placeholder!", UserWarning)
# ... (rest of your warnings - they are good)
if settings.OPENAI_API_KEY == "ENV_VAR_NOT_SET":
     warnings.warn("CONFIG WARNING: OPENAI_API_KEY environment variable not set.", UserWarning)
if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
     warnings.warn("AWS WARNING: AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY environment variable not set. SES sending will fail.", UserWarning)
if not settings.DEFAULT_SENDER_EMAIL:
     warnings.warn("AWS WARNING: DEFAULT_SENDER_EMAIL environment variable not set. SES fallback sending may fail.", UserWarning)
if not settings.allowed_origins_list and "*" not in getattr(settings, "ALLOWED_ORIGINS", ""): # Check if actual list is empty and not wildcard
    warnings.warn("CONFIG WARNING: ALLOWED_ORIGINS environment variable is not set or empty (and not wildcard). CORS errors likely.", UserWarning)

# Add warnings for Stripe keys if not set
if not settings.STRIPE_PUBLISHABLE_KEY:
    warnings.warn("STRIPE WARNING: STRIPE_PUBLISHABLE_KEY environment variable not set. Stripe.js will fail.", UserWarning)
if not settings.STRIPE_SECRET_KEY:
    warnings.warn("STRIPE WARNING: STRIPE_SECRET_KEY environment variable not set. Stripe backend operations will fail.", UserWarning)

# Use logger carefully here as it's initialized after settings
# The print statements in get_secret_key_from_file_or_env will show up earlier in logs.
try:
    from app.utils.logger import logger # Try to use your app's logger if available
    logger.info(f"[{settings.environment.upper()}] Settings loaded. Email sending configured for AWS SES in region: {settings.AWS_REGION}")
    logger.info(f"SECRET_KEY loaded: {'Yes' if settings.SECRET_KEY != 'ENV_VAR_NOT_SET_SECRET_KEY' else 'No (Using Default/Placeholder)'}")
    logger.info(f"STRIPE_SECRET_KEY loaded: {'Yes' if settings.STRIPE_SECRET_KEY else 'No'}")
    logger.info(f"STRIPE_PUBLISHABLE_KEY loaded: {'Yes' if settings.STRIPE_PUBLISHABLE_KEY else 'No'}")
except ImportError:
    print(f"[{settings.environment.upper()}] Settings loaded (basic print). Email sending configured for AWS SES in region: {settings.AWS_REGION}")
    print(f"SECRET_KEY loaded (basic print): {'Yes' if settings.SECRET_KEY != 'ENV_VAR_NOT_SET_SECRET_KEY' else 'No (Using Default/Placeholder)'}")
    print(f"STRIPE_SECRET_KEY loaded (basic print): {'Yes' if settings.STRIPE_SECRET_KEY else 'No'}")
    print(f"STRIPE_PUBLISHABLE_KEY loaded (basic print): {'Yes' if settings.STRIPE_PUBLISHABLE_KEY else 'No'}")
