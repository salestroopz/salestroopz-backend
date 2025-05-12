# app/utils/config.py

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv # Keep if using .env for local dev
from pathlib import Path
import warnings
from typing import Optional, List # Added Optional, List for type hints

# Determine the base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file from the project root directory for local development
dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=dotenv_path)

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    Configured for AWS SES email sending.
    """
    # --- General Settings ---
    app_name: str = "SalesTroopz"
    admin_email: str = os.getenv("ADMIN_EMAIL", "admin@example.com") # Default for example
    environment: str = os.getenv("ENVIRONMENT", "development")

    # --- Database Settings ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'salestroopz.db'}")

    # --- OpenAI Settings ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "ENV_VAR_NOT_SET")

    # --- JWT Authentication Settings ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "ENV_VAR_NOT_SET_SECRET_KEY") # Force setting via env
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 1))) # Default 1 day

    # --- CORS Settings ---
    # ** UPDATE RENDER URL placeholder below **
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501,https://your-streamlit-app-name.onrender.com")

    # --- === AWS SES Settings === ---
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1") # Default region
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID") # Must be set in env
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY") # Must be set in env
    # Default sender for system emails / fallback (MUST BE VERIFIED IN YOUR SES ACCOUNT)
    DEFAULT_SENDER_EMAIL: Optional[str] = os.getenv("DEFAULT_SENDER_EMAIL") # Must be set in env
    DEFAULT_SENDER_NAME: str = os.getenv("DEFAULT_SENDER_NAME", "SalesTroopz Platform")
    # --- === End AWS SES Settings === ---

    ENABLE_EMAIL_SCHEDULER: bool = Field(True, description="Enable the periodic email sending worker")
    EMAIL_SCHEDULER_INTERVAL_MINUTES: int = Field(5, gt=0, description="How often the email sender runs")
    ENABLE_IMAP_REPLY_POLLER: bool = Field(True, description="Enable the periodic IMAP reply poller")
    IMAP_POLLER_INTERVAL_MINUTES: int = Field(10, gt=0, description="How often the IMAP poller runs")

    @property
    def allowed_origins_list(self) -> List[str]: # Changed return type hint
        """Parses the comma-separated ALLOWED_ORIGINS string into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        # If using python-dotenv at top, pydantic's own .env loading might be redundant
        # env_file = '.env'
        # env_file_encoding = 'utf-8'
        case_sensitive = True # Important for AWS keys

# Create a single, importable instance of the settings
settings = Settings()

# --- Configuration Warnings ---
if settings.SECRET_KEY == "ENV_VAR_NOT_SET_SECRET_KEY":
    warnings.warn("SECURITY WARNING: SECRET_KEY environment variable not set!", UserWarning)
if settings.OPENAI_API_KEY == "ENV_VAR_NOT_SET":
     warnings.warn("CONFIG WARNING: OPENAI_API_KEY environment variable not set.", UserWarning)
# Add checks for AWS SES settings
if not settings.AWS_ACCESS_KEY_ID or not settings.AWS_SECRET_ACCESS_KEY:
     warnings.warn("AWS WARNING: AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY environment variable not set. SES sending will fail.", UserWarning)
if not settings.DEFAULT_SENDER_EMAIL:
     warnings.warn("AWS WARNING: DEFAULT_SENDER_EMAIL environment variable not set. SES fallback sending may fail.", UserWarning)
# Keep CORS check
if not settings.allowed_origins_list:
    warnings.warn("CONFIG WARNING: ALLOWED_ORIGINS environment variable is not set or empty. CORS errors likely.", UserWarning)


print(f"[{settings.environment.upper()}] Settings loaded. Email sending configured for AWS SES in region: {settings.AWS_REGION}")
