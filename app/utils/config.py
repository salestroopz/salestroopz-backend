# app/utils/config.py

import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from pathlib import Path
import warnings # For security warnings

# Determine the base directory of the project
# Assumes config.py is in app/utils/, so ../.. goes to project root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env file from the project root directory for local development
dotenv_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=dotenv_path)

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    Combines original settings with requirements for DB, Auth, OpenAI, CORS.
    """
    # --- Existing Settings ---
    app_name: str = "SalesTroopz"
    admin_email: str = "admin@salestroopz.com"
    environment: str = os.getenv("ENVIRONMENT", "development") # Prefer loading from env

    # --- Database Settings ---
    # Default to a local SQLite file relative to the project root
    # Render will override this with DATABASE_URL env var for PostgreSQL etc.
    DATABASE_URL: str = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{BASE_DIR / 'salestroopz.db'}")

    # --- OpenAI Settings ---
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "NOT_SET") # Avoid default key

    # --- JWT Authentication Settings ---
    # **IMPORTANT**: Generate a strong secret key (e.g., `openssl rand -hex 32`)
    # and set it via the SECRET_KEY environment variable!
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default_secret_key_change_immediately") # **CHANGE THIS**
    ALGORITHM: str = "HS256" # Standard algorithm for HS256 JWTs
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 1 # Default: 1 day expiry

    EMAIL_HOST: Optional[str] = os.getenv("EMAIL_HOST")
    EMAIL_PORT: int = int(os.getenv("EMAIL_PORT", 587)) # Default to 587 if not set
    EMAIL_USERNAME: Optional[str] = os.getenv("EMAIL_USERNAME")
    EMAIL_PASSWORD: Optional[str] = os.getenv("EMAIL_PASSWORD") # Use App Password for Gmail
    EMAIL_SENDER_ADDRESS: Optional[str] = os.getenv("EMAIL_SENDER_ADDRESS") # e.g., your sending address
    EMAIL_SENDER_NAME: str = os.getenv("EMAIL_SENDER_NAME", "SalesTroopz Agent") # Default sender name

    # --- CORS Settings ---
    # Define allowed origins (frontend URL). Comma-separated string in env var.
    # ** UPDATE the default Render URL placeholder below **
    ALLOWED_ORIGINS: str = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8501,https://your-streamlit-app-name.onrender.com"
    )

   
    @property
    def allowed_origins_list(self) -> list[str]:
        """Parses the comma-separated ALLOWED_ORIGINS string into a list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        # Configure Pydantic BaseSettings
        env_file = ".env" # Specifies the default env file to load
        env_file_encoding = 'utf-8'
        case_sensitive = True # Match environment variable names exactly

# Create a single, importable instance of the settings
settings = Settings()

# --- Security Warnings ---
# Add checks to warn if critical secrets are using defaults or are missing

if settings.SECRET_KEY == "default_secret_key_change_immediately":
    warnings.warn(
        "SECURITY WARNING: Using default SECRET_KEY. "
        "Generate a strong random key (e.g., `openssl rand -hex 32`) and set the SECRET_KEY environment variable!",
        UserWarning
    )

if settings.OPENAI_API_KEY == "NOT_SET":
     warnings.warn(
        "CONFIGURATION WARNING: OPENAI_API_KEY is not set in environment variables. OpenAI features will fail.",
        UserWarning
     )

# Optional: Print a confirmation that settings are loaded during startup
# Useful for debugging environment issues
print(f"[{settings.environment.upper()}] Settings loaded.")
# print(f"Allowed CORS Origins: {settings.allowed_origins_list}")
