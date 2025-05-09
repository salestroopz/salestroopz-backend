# app/main.py

# --- Standard Library Imports FIRST ---
import sys
import os
from pathlib import Path
# import warnings # Not used, can be removed

# --- sys.path modification (Consider alternatives if possible) ---
# This is generally okay for local dev but might not be ideal for all deployment scenarios.
# Ensure your run command (e.g., uvicorn) is executed from the project root.
# Or use `PYTHONPATH=.` or `pip install -e .`
try:
    PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent # Assuming main.py is in app/
    if str(PROJECT_ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT_DIR))
        print(f"DEBUG: Added project root to sys.path: {PROJECT_ROOT_DIR}") # For debugging, consider logging
except Exception as e:
    print(f"Warning: Could not modify sys.path: {e}") # For debugging, consider logging

# --- Third-Party Imports ---
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
except ImportError as e:
     print(f"FATAL ERROR: Could not import FastAPI or CORSMiddleware: {e}") # Consider logging
     raise SystemExit("FastAPI framework not found. Please ensure it's installed.") from e

# --- Application Imports ---

# Configuration (Load FIRST - Crucial)
try:
    from app.utils.config import settings
    print(f"INFO: Settings loaded successfully for app: {settings.app_name}") # For debugging, consider logging
except ImportError as e_import:
    print(f"FATAL ERROR: Could not import settings from app.utils.config: {e_import}") # Consider logging
    raise SystemExit(f"Failed to load application settings: {e_import}") from e_import
except Exception as e_generic:
    print(f"FATAL ERROR: An unexpected error occurred importing settings: {e_generic}") # Consider logging
    raise SystemExit(f"Unexpected failure loading application settings: {e_generic}") from e_generic

# Database Initialization Function
try:
    from app.db.database import initialize_db
except ImportError as e:
    print(f"WARNING: Could not import 'initialize_db' from app.db.database: {e}. Database might not be auto-initialized.") # Consider logging
    initialize_db = None # Define as None so startup event can check

# API Routers/Routes (Grouped by their location)
# It's good practice to have an __init__.py in 'routes' and 'routers' to mark them as packages.

# From app.routes directory
try:
    print("DEBUG: Attempting to import from app.routes...")
    from app.routes import auth as auth_router_module
    print(f"DEBUG: Imported auth. Type: {type(auth_router_module)}")
    from app.routes import icpmatch as icp_match_router_module
    print(f"DEBUG: Imported icpmatch. Type: {type(icp_match_router_module)}")
    
    from app.routes import workflow as workflow_router_module # <<< The line in question
    print(f"DEBUG: Imported workflow. workflow_router_module IS DEFINED HERE. Type: {type(workflow_router_module)}") # <<< ADD THIS
    
    from app.routes import leadworkflow as leadworkflow_router_module
    print(f"DEBUG: Imported leadworkflow. Type: {type(leadworkflow_router_module)}")
    from app.routes import leadenrichment as leadenrichment_router_module
    print("DEBUG: Imported leadenrichment.") # Add this
    print("INFO: Successfully imported modules from 'app.routes'.")

    print(f"FATAL ERROR during import from 'app.routes': {type(e).__name__} - {e}")
    import traceback
    traceback.print_exc() # Print the full traceback of the actual error
    # For now, let the program exit if a critical router fails to load
    raise SystemExit(f"Failed to import a module from app.routes: {e}")
    from app.routes import leadworkflow as leadworkflow_router_module
    print(f"DEBUG: Imported leadworkflow. Type: {type(leadworkflow_router_module)}")
    # ... continue for other imports in this block ...
    print("INFO: Successfully imported modules from 'app.routes'.")
except ImportError as e:
    print(f"ERROR: Could not import one or more modules from 'app.routers': {e}")

# From app.routers directory
try:
    from app.routers import icp as icp_crud_router_module
    from app.routers import offering as offering_router_module
    from app.routers import campaigns as campaigns_router_module
    from app.routers import email_settings as email_settings_router_module
    from app.routers import leads as leads_router_module # Corrected typo from 'leads_router_modul'
    print("INFO: Successfully imported modules from 'app.routers'.") # For debugging
except ImportError as e:
    print(f"ERROR: Could not import one or more modules from 'app.routers': {e}") # Consider logging
    # Depending on criticality, you might raise SystemExit here


# Global Agent Instances (Optional - consider dependency injection for better testability)
# If these agents are only used by specific routers, they could be instantiated there.
try:
    from app.agents.crmagent import CRMConnectorAgent # Assuming path is app/agents/crmagent.py
    crm_agent_instance = CRMConnectorAgent() # Instantiate if needed globally
    print("INFO: CRMConnectorAgent instance created.") # For debugging
except ImportError as e:
     print(f"WARNING: Could not import or instantiate CRMConnectorAgent: {e}. CRM features might be affected.") # Consider logging
     crm_agent_instance = None # Define as None so dependent code can check


# ==============================================
# --- Create FastAPI App Instance ---
# ==============================================
try:
    app = FastAPI(
        title=settings.app_name,
        description="API to manage and process sales leads for multiple organizations.",
        version="0.2.0", # Consider moving version to settings or a __version__.py
        # openapi_url=f"{settings.api_v1_prefix}/openapi.json" # Example for namespacing docs
    )
    print(f"INFO: FastAPI app '{settings.app_name}' created successfully.") # For debugging
except AttributeError as e_attr: # If settings or settings.app_name is not found
    print(f"FATAL ERROR: Missing required attributes in settings (e.g., app_name) for FastAPI app creation: {e_attr}")
    raise SystemExit("FastAPI app creation failed due to missing settings.") from e_attr
except Exception as e_app:
    print(f"FATAL ERROR: Could not create FastAPI app instance: {e_app}") # Consider logging
    raise SystemExit("FastAPI app creation failed.") from e_app

# ==============================================
# --- Configure CORS Middleware ---
# ==============================================
# Ensure settings.allowed_origins_list is defined in your config (can be empty list)
if hasattr(settings, 'allowed_origins_list') and settings.allowed_origins_list:
    origins_to_allow = settings.allowed_origins_list
    print(f"INFO: Configuring CORS for specified origins: {origins_to_allow}") # For debugging
else:
    origins_to_allow = ["*"] # Default to allow all if not specified or empty
    print("WARNING: ALLOWED_ORIGINS not specified or empty in settings. Defaulting CORS to allow all origins ('*'). This is not recommended for production.") # Consider logging

try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins_to_allow,
        allow_credentials=True,
        allow_methods=["*"], # Or specify ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        allow_headers=["*"], # Or specify common headers
    )
    print("INFO: CORS middleware configured.") # For debugging
except Exception as e:
    print(f"ERROR: Failed to configure CORS middleware: {e}") # Consider logging

# ==============================================
# --- Database Initialization on Startup ---
# ==============================================
@app.on_event("startup")
async def on_startup():
    """Actions to perform on application startup."""
    print("INFO: Application startup event triggered.") # For debugging
    if initialize_db:
        print("INFO: Attempting database initialization...") # For debugging
        try:
            initialize_db()
            print("INFO: Database initialization logic executed successfully.") # For debugging
        except Exception as e:
            print(f"ERROR: An error occurred during database initialization on startup: {e}") # Consider logging
    else:
        print("WARNING: 'initialize_db' function not available. Database auto-initialization skipped.") # Consider logging
    print("INFO: Application startup sequence complete.") # For debugging

# ==============================================
# --- Include API Routers ---
# ==============================================
print("INFO: Including API routers...") # For debugging
router_modules_to_include = {
    # From app.routes
    "Auth": auth_router_module,
    "ICP Matching": icp_match_router_module,
    "Workflow": workflow_router_module,
    "Lead Workflow": leadworkflow_router_module,
    "CRM Routes": crm_routes_module,
    "Agents Routes": agents_router_module, # Assuming this is a router module
    "Inside Sales": insidesales_router_module,
    "Scheduler": scheduler_router_module,
    "Lead Enrichment": leadenrichment_router_module,
    # From app.routers
    "ICP CRUD": icp_crud_router_module,
    "Offerings": offering_router_module,
    "Campaigns": campaigns_router_module,
    "Email Settings": email_settings_router_module,
    "Leads": leads_router_module
}

for name, module_instance in router_modules_to_include.items():
    try:
        if module_instance and hasattr(module_instance, 'router'):
            app.include_router(module_instance.router)
            print(f"INFO: Included router for '{name}'.") # For debugging
        elif module_instance:
            print(f"WARNING: Module '{name}' imported but does not have a 'router' attribute. Skipping inclusion.") # Consider logging
        # else: # Module instance itself might be None if import failed and wasn't critical
            # print(f"DEBUG: Module for '{name}' was not imported, cannot include router.")
    except Exception as e:
        print(f"ERROR: Failed to include router for '{name}': {e}") # Consider logging
        # Decide if this should be a fatal error for critical routers


# ==============================================
# --- Root Endpoint ---
# ==============================================
@app.get("/", tags=["Root"], summary="API Root/Health Check")
async def read_root():
    """Provides a simple status message indicating the API is live."""
    return {
        "status": f"{getattr(settings, 'app_name', 'SalesTroopz API')} backend is live!",
        "environment": getattr(settings, 'environment', 'unknown_environment'),
        "version": app.version # Access version from the app instance
    }

# --- Final Confirmation Log ---
# This will print when the module is first loaded by Uvicorn, before startup events for worker processes.
print(f"--- {getattr(settings, 'app_name', 'SalesTroopz API')} FastAPI application module loading complete. ---")
