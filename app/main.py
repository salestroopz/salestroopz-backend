# app/main.py
# app/main.py
import sys
import os # <--- Add import os
from pathlib import Path
# --- ADD DEBUG PRINTS ---
print("--- DEBUG: main.py starting ---")
print(f"Current Working Directory: {os.getcwd()}")
print("System Path (sys.path) BEFORE modification:")
for p in sys.path:
    print(f"  - {p}")
print("---")
# --- END DEBUG PRINTS ---

project_root = Path(__file__).resolve().parent.parent # This is app/
# The parent of app/ is the project root which should contain 'app' package
project_root_for_sys_path = project_root.parent
print(f"DEBUG: Calculated project root for sys.path: {project_root_for_sys_path}") # Debug the calculated root

if str(project_root_for_sys_path) not in sys.path:
    print(f"DEBUG: Adding project root to sys.path: {project_root_for_sys_path}")
    sys.path.insert(0, str(project_root_for_sys_path))
    print("System Path (sys.path) AFTER modification:")
    for p in sys.path:
        print(f"  - {p}")
    print("---")
else:
     print("DEBUG: Project root already in sys.path.")


print("--- DEBUG: Attempting imports ---")
from fastapi import FastAPI
# ... rest of imports ...
try:
    # This is where it fails
    from app.utils.config import settings
    print("Successfully imported settings in main.py")




import sys
from pathlib import Path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# --- Import Configuration FIRST ---
try:
    from app.utils.config import settings
    print("Successfully imported settings in main.py")
except ImportError as e:
    print(f"FATAL ERROR: Could not import settings from app.utils.config: {e}")
    raise SystemExit(f"Failed to load settings: {e}") from e

# --- Import Database Initialization ---
try:
    from app.db.database import initialize_db
except ImportError as e:
    print(f"ERROR: Could not import database initialization: {e}")
    initialize_db = None

# --- Import API Routers ---
try:
    # Routers defined during Phase 0
    from app.routes import auth
    # Your workflow routers (now distinct)
    from app.routes import workflow          # Assumes app/routes/workflow.py
    from app.routes import leadworkflow     # Assumes app/routes/leadworkflow.py

    # Your existing routers
    from app.routers import icp                 # Assumes app/routers/icp.py
    from app.routers import offering            # Assumes app/routers/offering.py
    from app.routes import crm                  # Assumes app/routes/crm.py
    from app.routes import agents               # Assumes app/routes/agents.py
    from app.routes import emailcampaign        # Assumes app/routes/emailcampaign.py
    from app.routes import insidesales          # Assumes app/routes/insidesales.py
    from app.routes import scheduler            # Assumes app/routes/scheduler.py
    from app.routes import leadenrichment       # Assumes app/routes/leadenrichment.py
    from app.routes import icpmatch             # Assumes app/routes/icpmatch.py

    print("Successfully imported API routers.")
except ImportError as e:
    print(f"ERROR: Could not import one or more routers: {e}")
    raise SystemExit(f"Failed to import routers: {e}") from e

# --- Global Agent Instances (Use with caution) ---
# ... (Keep CRM agent instantiation if needed) ...
try:
    from app.agents.crmagent import CRMConnectorAgent
    crm_agent_instance = CRMConnectorAgent()
    print("CRMConnectorAgent instance created.")
except ImportError as e:
     print(f"Warning: Could not import or instantiate CRMConnectorAgent: {e}")
     crm_agent_instance = None

# --- Create SINGLE FastAPI App Instance ---
app = FastAPI(
    title=settings.app_name,
    description="API to manage and process sales leads for multiple organizations.",
    version="0.2.0",
)

# --- Configure CORS Middleware ---
# ... (Keep CORS setup using settings.allowed_origins_list) ...
if not settings.allowed_origins_list:
    print("WARNING: No CORS origins specified via ALLOWED_ORIGINS env var. Frontend API calls may fail.")
    origins = ["*"] # Example: Allow all if empty (use caution)
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


# --- Database Initialization on Startup ---
@app.on_event("startup")
async def startup_database_initialization():
    # ... (Keep startup logic) ...
    print("Application startup: Initializing database...")
    if initialize_db:
        try:
            initialize_db()
            print("Database initialization attempted successfully.")
        except Exception as e:
            print(f"ERROR DURING DATABASE INITIALIZATION: {e}")
    else:
        print("WARNING: Database initialization function not found or failed to import.")
    print("Application startup sequence complete.")


# --- Include ALL API Routers ONCE ---
# It's cleaner if prefixes/tags are defined *within* the APIRouter()
# initialization in each respective router file. Add them here ONLY
# if they are NOT defined within the router files themselves.
print("Including API routers...")
try:
    # Phase 0 Routers
    app.include_router(auth.router)         # Assumes prefix="/api/v1/auth", tags=["Authentication"] defined inside
    app.include_router(workflow.router)     # Assumes prefix="/api/v1", tags=["Lead Workflow & Data"] defined inside

    # Your Distinct Lead Workflow Router
    app.include_router(leadworkflow.router, prefix="/api/v1/leadworkflow", tags=["Lead Workflow Specific"]) # Example prefix/tag - ADJUST

    # Your Existing Routers (Add consistent prefixes/tags, preferably inside the files)
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


# --- Root Endpoint ---
@app.get("/", tags=["Root"])
async def read_root():
    """Provides a simple welcome message and links to docs."""
    return {
        "status": f"{settings.app_name} backend is live!",
        "environment": settings.environment,
        "docs": app.docs_url,
        "redoc": app.redoc_url
    }

print(f"{settings.app_name} FastAPI application configured.")
