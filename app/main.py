# app/main.py

# --- Standard Library Imports FIRST ---
import sys
import os
from pathlib import Path
import warnings # If using warnings

# --- ADD DEBUG PRINTS ---
print("--- DEBUG: main.py starting ---")
print(f"Current Working Directory: {os.getcwd()}")
print("System Path (sys.path) BEFORE modification:")
# Use repr(p) in case paths have unusual characters
for p in sys.path:
    print(f"  - {repr(p)}")
print("---")

# --- sys.path modification (Ensures 'app' package is findable) ---
# Calculate project root assuming main.py is inside app/
# project_root_dir should be the directory CONTAINING the 'app' folder
try:
    # Resolve the path of the current file (main.py)
    current_file_path = Path(__file__).resolve()
    # parent is the directory containing main.py (app/)
    # parent.parent is the directory containing app/ (the project root)
    project_root_dir = current_file_path.parent.parent
    print(f"DEBUG: Calculated project root for sys.path: {project_root_dir}")

    if str(project_root_dir) not in sys.path:
        print(f"DEBUG: Adding project root to sys.path: {project_root_dir}")
        sys.path.insert(0, str(project_root_dir))
        print("System Path (sys.path) AFTER modification:")
        for p in sys.path: print(f"  - {repr(p)}")
        print("---")
    else:
         print("DEBUG: Project root already in sys.path.")
except Exception as e:
    print(f"ERROR calculating or modifying sys.path: {e}")
    project_root_dir = None # Indicate failure

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
if project_root_dir: # Only check if path calculation succeeded
    utils_dir = project_root_dir / 'app' / 'utils'
    config_file = utils_dir / 'config.py'
    utils_init_file = utils_dir / '__init__.py'
    app_init_file = project_root_dir / 'app' / '__init__.py' # Check app's init too

    print(f"DEBUG: Checking app/__init__.py: {app_init_file} | Exists: {app_init_file.is_file()}")
    print(f"DEBUG: Checking app/utils/__init__.py: {utils_init_file} | Exists: {utils_init_file.is_file()}")
    print(f"DEBUG: Checking app/utils/config.py: {config_file} | Exists: {config_file.is_file()}")
else:
    print("DEBUG: Skipping file existence checks because project_root_dir calculation failed.")
print("---")

try:
    # THE FAILING IMPORT
    from app.utils.config import settings
    print("Successfully imported settings from app.utils.config.")
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings from app.utils.config: {e}")
    print("Check CWD, sys.path in logs above, and file existence checks.")
    # Add more detail based on checks if possible
    if project_root_dir:
         if not app_init_file.is_file(): print("-> 'app/__init__.py' seems MISSING!")
         if not utils_init_file.is_file(): print("-> 'app/utils/__init__.py' seems MISSING!")
         if not config_file.is_file(): print("-> 'app/utils/config.py' seems MISSING!")
    raise SystemExit(f"Failed to load settings: {e}") from e
except Exception as e_generic: # Catch other potential errors during import/init of config
    print(f"FATAL ERROR: An unexpected error occurred importing settings: {e_generic}")
    raise SystemExit(f"Failed loading settings: {e_generic}") from e_generic


# Database Initialization Import
try:
    from app.db.database import initialize_db
    print("Successfully imported initialize_db from app.db.database.")
except ImportError as e:
    print(f"ERROR: Could not import database initialization: {e}")
    initialize_db = None # Allow app to start but warn later

# API Routers Import
try:
    from app.routes import auth, workflow, leadworkflow, crm, agents, emailcampaign, insidesales, scheduler, leadenrichment, icpmatch
    from app.routers import icp, offering
    print("Successfully imported API routers.")
except ImportError as e:
    print(f"ERROR: Could not import one or more routers: {e}")
    raise SystemExit(f"Failed to import routers: {e}") from e

# Global Agent Instances Import (Optional)
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
try:
    app = FastAPI(
        title=settings.app_name,
        description="API to manage and process sales leads for multiple organizations.",
        version="0.2.0", # Example version
    )
    print(f"FastAPI app created with title: {settings.app_name}")
except Exception as e:
    print(f"ERROR creating FastAPI app instance. Settings loaded?: {'settings' in locals()}. Error: {e}")
    raise SystemExit("Failed to create FastAPI app.") from e

# ==============================================
# --- Configure CORS Middleware ---
# ==============================================
try:
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
except Exception as e:
    print(f"ERROR configuring CORS middleware: {e}")
    # Decide if this is critical

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
    # Include routers using variables imported above
    app.include_router(auth.router)         # Assumes prefix/tags defined inside
    app.include_router(workflow.router)     # Assumes prefix/tags defined inside
    app.include_router(leadworkflow.router, prefix="/api/v1/leadworkflow", tags=["Lead Workflow Specific"]) # Example - adjust
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
    print(f"ERROR INCLUDING ROUTERS: {e}")


# ==============================================
# --- Root Endpoint ---
# ==============================================
@app.get("/", tags=["Root"])
async def read_root():
    """Provides a simple welcome message and links to docs."""
    # Check if settings object exists before accessing it
    app_name = getattr(settings, 'app_name', 'SalesTroopz API (Settings Load Failed)')
    environment = getattr(settings, 'environment', 'unknown')
    return {
        "status": f"{app_name} backend is live!",
        "environment": environment,
        "docs": getattr(app, 'docs_url', '/docs'), # Use getattr for safety
        "redoc": getattr(app, 'redoc_url', '/redoc')
    }

# --- Final Confirmation Log ---
print(f"--- FastAPI application configuration potentially complete (check logs for errors) ---")
