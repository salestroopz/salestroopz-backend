# app/main.py

# --- Standard Library Imports FIRST ---
import sys
import os
from pathlib import Path
import warnings # Using warnings module for config warnings

# app/main.py
# ... (standard imports like sys, os, Path) ...

# ... (sys.path modification and debug prints for CWD/sys.path) ...

print("--- DEBUG: Attempting imports ---")

# --- Third-Party Imports ---
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    print("Successfully imported FastAPI and CORSMiddleware.")
except ImportError as e:
     print(f"FATAL ERROR: Could not import FastAPI or CORSMiddleware: {e}")
     raise SystemExit("FastAPI framework not found.") from e

# --- Application Imports (within try...except blocks) ---

# Configuration (Critical - Load FIRST)
print("--- DEBUG: Checking existence of config files ---")
utils_dir = project_root_dir / 'app' / 'utils' # project_root_dir calculated earlier
config_file = utils_dir / 'config.py'
utils_init_file = utils_dir / '__init__.py'
app_init_file = project_root_dir / 'app' / '__init__.py'

print(f"DEBUG: Checking app/__init__.py: {app_init_file} | Exists: {app_init_file.is_file()}")
print(f"DEBUG: Checking app/utils/__init__.py: {utils_init_file} | Exists: {utils_init_file.is_file()}")
print(f"DEBUG: Checking app/utils/config.py: {config_file} | Exists: {config_file.is_file()}")
print("---")

try:
    from app.utils.config import settings # The failing import
    print("Successfully imported settings from app.utils.config.")
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings from app.utils.config: {e}")
    # The debug prints above might give clues why
    print("Check CWD, sys.path in logs above, and file existence checks.")
    raise SystemExit(f"Failed to load settings: {e}") from e

# ... (rest of the imports and main.py code) ...

# --- ADD DEBUG PRINTS (Optional but keep for now) ---
print("--- DEBUG: main.py starting ---")
print(f"Current Working Directory: {os.getcwd()}")
print("System Path (sys.path) BEFORE modification:")
for p in sys.path:
    print(f"  - {p}")
print("---")

# --- sys.path modification (Ensures 'app' package is findable) ---
# Calculate project root assuming main.py is inside app/
project_root_dir = Path(__file__).resolve().parent.parent
print(f"DEBUG: Calculated project root for sys.path: {project_root_dir}")

if str(project_root_dir) not in sys.path:
    print(f"DEBUG: Adding project root to sys.path: {project_root_dir}")
    sys.path.insert(0, str(project_root_dir))
    print("System Path (sys.path) AFTER modification:")
    for p in sys.path: print(f"  - {p}")
    print("---")
else:
     print("DEBUG: Project root already in sys.path.")

print("--- DEBUG: Attempting imports ---")

# --- Third-Party Imports ---
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    print("Successfully imported FastAPI and CORSMiddleware.")
except ImportError as e:
     print(f"FATAL ERROR: Could not import FastAPI or CORSMiddleware: {e}")
     raise SystemExit("FastAPI framework not found.") from e


# --- Application Imports (within try...except blocks) ---

# Configuration (Critical - Load FIRST)
try:
    from app.utils.config import settings
    print("Successfully imported settings from app.utils.config.")
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings from app.utils.config: {e}")
    print("Check CWD, sys.path, and ensure app/utils/__init__.py and app/utils/config.py exist.")
    raise SystemExit(f"Failed to load settings: {e}") from e

# Database Initialization
try:
    from app.db.database import initialize_db
    print("Successfully imported initialize_db from app.db.database.")
except ImportError as e:
    print(f"ERROR: Could not import database initialization: {e}")
    initialize_db = None # Allow app to start but warn later

# API Routers
try:
    from app.routes import auth
    from app.routes import workflow
    from app.routes import leadworkflow
    from app.routers import icp
    from app.routers import offering
    from app.routes import crm
    from app.routes import agents
    from app.routes import emailcampaign
    from app.routes import insidesales
    from app.routes import scheduler
    from app.routes import leadenrichment
    from app.routes import icpmatch
    print("Successfully imported API routers.")
except ImportError as e:
    print(f"ERROR: Could not import one or more routers: {e}")
    # Decide if this is fatal - probably is if core routes missing
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
# Define the app instance ONCE
app = FastAPI(
    title=settings.app_name,
    description="API to manage and process sales leads for multiple organizations.",
    version="0.2.0", # Example version
)
print(f"FastAPI app created with title: {settings.app_name}")

# ==============================================
# --- Configure CORS Middleware ---
# ==============================================
if not settings.allowed_origins_list:
    print("WARNING: No CORS origins specified via ALLOWED_ORIGINS env var. Frontend API calls may fail.")
    origins = ["*"] # Default to allow all if unset (Use with caution in production!)
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

# ==============================================
# --- Database Initialization on Startup ---
# ==============================================
@app.on_event("startup")
async def startup_database_initialization():
    """Initializes the database when the application starts."""
    print("Application startup event: Initializing database...")
    if initialize_db:
        try:
            initialize_db() # Run the function from database.py
            print("Database initialization logic executed.")
        except Exception as e:
            print(f"ERROR DURING DATABASE INITIALIZATION: {e}")
            # Consider if app should stop if DB init fails critically
    else:
        print("WARNING: Database initialization function was not imported correctly.")
    print("Startup event sequence complete.")


# ==============================================
# --- Include API Routers ---
# ==============================================
# Include each router ONCE. Prefixes/tags should ideally be defined
# within the APIRouter() in each router's file.
print("Including API routers...")
try:
    app.include_router(auth.router)         # Expects prefix="/api/v1/auth", tags=["Authentication"]
    app.include_router(workflow.router)     # Expects prefix="/api/v1", tags=["Lead Workflow & Data"]
    app.include_router(leadworkflow.router, prefix="/api/v1/leadworkflow", tags=["Lead Workflow Specific"]) # Example - adjust in file if possible
    app.include_router(icp.router, prefix="/api/v1/icp", tags=["ICP"])
    app.include_router(offering.router, prefix="/api/v1/offering", tags=["Offering"])
    app.include_router(crm.router, prefix="/api/v1/crm", tags=["CRM"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["Agents"])
    app.include_router(emailcampaign.router, prefix="/api/v1/email", tags=["Email Campaign Manager"])
    app.include_router(insidesales.router, prefix="/api/v1/sales", tags=["Inside Sales Agent"])
    app.include_router(scheduler.router, prefix="/api/v1/campaigns", tags=["Email Scheduler Agent"])
    app.include_router(leadenrichment.router, prefix="/api/v1/enrichment", tags=["Lead Enrichment Agent"])
    app.include_router(icpmatch.router, prefix="/api/v1/icpmatch", tags=["ICP Match"])
    print("Routers included successfully.")
except Exception as e:
    # Catching potential errors during include_router (e.g., if router variable missing)
    print(f"ERROR INCLUDING ROUTERS: {e}")
    # Depending on severity, you might want to stop the app
    # raise SystemExit(f"Failed to include routers: {e}") from e


# ==============================================
# --- Root Endpoint ---
# ==============================================
@app.get("/", tags=["Root"])
async def read_root():
    """Provides a simple welcome message and links to docs."""
    return {
        "status": f"{settings.app_name} backend is live!",
        "environment": settings.environment,
        "docs": app.docs_url,
        "redoc": app.redoc_url
    }

# --- Final Confirmation Log ---
print(f"--- {settings.app_name} FastAPI application configuration complete ---")
