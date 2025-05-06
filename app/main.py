# app/main.py

# --- Standard Library Imports FIRST ---
import sys
import os
from pathlib import Path
import warnings

# --- sys.path modification (Good practice for robustness) ---
try:
    project_root_dir = Path(__file__).resolve().parent.parent
    if str(project_root_dir) not in sys.path:
        sys.path.insert(0, str(project_root_dir))
        print(f"DEBUG: Added project root to sys.path: {project_root_dir}")
except Exception as e:
    print(f"Warning: Could not modify sys.path: {e}")

# --- Third-Party Imports ---
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as e:
     print(f"FATAL ERROR: Could not import FastAPI or CORSMiddleware: {e}")
     raise SystemExit("FastAPI framework not found.") from e

# --- Application Imports ---
# Configuration (Load FIRST)
try:
    from app.utils.config import settings
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings from app.utils.config: {e}")
    raise SystemExit(f"Failed to load settings: {e}") from e
except Exception as e_generic:
    print(f"FATAL ERROR: An unexpected error occurred importing settings: {e_generic}")
    raise SystemExit(f"Failed loading settings: {e_generic}") from e_generic

# Database Initialization
try:
    from app.db.database import initialize_db
except ImportError as e:
    print(f"ERROR: Could not import database initialization: {e}")
    initialize_db = None

# API Routers
try:
    # Import all router modules
    from app.routes import auth, workflow, leadworkflow, crm, agents, insidesales, scheduler, leadenrichment, icpmatch
    from app.routers import icp, offering, campaigns, email_settings
except ImportError as e:
    print(f"ERROR: Could not import one or more routers: {e}")
    raise SystemExit(f"Failed to import routers: {e}") from e

# Global Agent Instances (Optional)
try:
    from app.agents.crmagent import CRMConnectorAgent
    crm_agent_instance = CRMConnectorAgent()
    print("CRMConnectorAgent instance created.")
except ImportError as e:
     print(f"Warning: Could not import or instantiate CRMConnectorAgent: {e}")
     crm_agent_instance = None


# ==============================================
# --- Create FastAPI App Instance ---
# ==============================================
try:
    app = FastAPI(
        title=settings.app_name,
        description="API to manage and process sales leads for multiple organizations.",
        version="0.2.0", # Example version
    )
    print(f"FastAPI app created: {settings.app_name}")
except Exception as e:
    print(f"ERROR creating FastAPI app instance. Settings loaded?: {'settings' in locals()}. Error: {e}")
    raise SystemExit("Failed to create FastAPI app.") from e

# ==============================================
# --- Configure CORS Middleware ---
# ==============================================
try:
    if not settings.allowed_origins_list:
        print("WARNING: No CORS origins specified via ALLOWED_ORIGINS env var.")
        origins = ["*"] # Allow all if unset - BE CAREFUL in production
    else:
        origins = settings.allowed_origins_list
    print(f"Configuring CORS for origins: {origins}")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
except Exception as e:
    print(f"ERROR configuring CORS middleware: {e}")

# ==============================================
# --- Database Initialization on Startup ---
# ==============================================
@app.on_event("startup")
async def startup_database_initialization():
    print("Application startup event: Initializing database...")
    if initialize_db:
        try:
            initialize_db()
            print("Database initialization logic executed.")
        except Exception as e:
            print(f"ERROR DURING DATABASE INITIALIZATION: {e}")
    else:
        print("WARNING: Database initialization function was not imported correctly.")
    print("Startup event sequence complete.")


# ==============================================
# --- Include API Routers ---
# ==============================================
# Assumes prefixes and tags are defined within each router file's
# APIRouter() definition for cleaner code organization.
print("Including API routers...")
try:
    app.include_router(auth.router)
    app.include_router(workflow.router)
    app.include_router(leadworkflow.router)
    app.include_router(icp.router)
    app.include_router(offering.router)
    app.include_router(crm.router)
    app.include_router(agents.router)
    app.include_router(insidesales.router)
    app.include_router(scheduler.router)
    app.include_router(leadenrichment.router)
    app.include_router(icpmatch.router)
    app.include_router(campaigns.router)
    app.include_router(email_settings.router)
    print("Routers included successfully.")
except Exception as e:
    print(f"ERROR INCLUDING ROUTERS: {e}")


# ==============================================
# --- Root Endpoint ---
# ==============================================
@app.get("/", tags=["Root"], summary="API Root/Health Check") # Added summary
async def read_root():
    """Provides a simple status message indicating the API is live."""
    # Safely access settings attributes
    app_name = getattr(settings, 'app_name', 'API')
    environment = getattr(settings, 'environment', 'unknown')
    return {
        "status": f"{app_name} backend is live!",
        "environment": environment,
    }

# --- Final Confirmation Log ---
print(f"--- {settings.app_name} FastAPI application configuration complete ---")
