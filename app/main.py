# app/main.py

# --- Standard Library Imports FIRST ---
import sys
import os
from pathlib import Path
import asyncio # For potential async tasks if agents are async

# --- sys.path modification ---
try:
    PROJECT_ROOT_DIR = Path(__file__).resolve().parent.parent
    if str(PROJECT_ROOT_DIR) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT_DIR))
        # Use logger after it's potentially initialized
except Exception as e_path:
    print(f"Warning: Could not modify sys.path: {e_path}")

# --- Third-Party Imports ---
try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from apscheduler.schedulers.asyncio import AsyncIOScheduler # For scheduling tasks
except ImportError as e_imp_third_party:
     print(f"FATAL ERROR: Could not import FastAPI, CORSMiddleware, or APScheduler: {e_imp_third_party}")
     raise SystemExit("Essential third-party libraries not found. Please ensure they are installed.") from e_imp_third_party

# --- Application Imports ---
# Configuration & Logger (Load FIRST - Crucial)
try:
    from app.utils.config import settings
    # Initialize logger AFTER settings might configure logging levels/handlers
    from app.utils.logger import logger # Assuming logger is configured here or in config
    logger.info(f"Settings and Logger loaded successfully for app: {settings.app_name}")
except ImportError as e_imp_app_core:
    print(f"FATAL ERROR: Could not import core 'app.utils' (config/logger): {e_imp_app_core}")
    raise SystemExit(f"Failed to load application core utilities: {e_imp_app_core}") from e_imp_app_core
except Exception as e_gen_app_core:
    print(f"FATAL ERROR: An unexpected error occurred importing core utilities: {e_gen_app_core}")
    raise SystemExit(f"Unexpected failure loading core utilities: {e_gen_app_core}") from e_gen_app_core

# Database Initialization Function
try:
    from app.db.database import initialize_db
except ImportError as e_imp_db:
    logger.warning(f"Could not import 'initialize_db' from app.db.database: {e_imp_db}. DB might not auto-init.")
    initialize_db = None

# Agent Imports for Schedulers
try:
    from app.agents.emailscheduler import EmailSchedulerAgent
    from app.agents.imap_reply_agent import ImapReplyAgent # NEW IMAP Agent
except ImportError as e_imp_agents:
    logger.error(f"Could not import one or more scheduler agents: {e_imp_agents}")
    # Decide if these are critical for startup. For now, allow startup but log error.
    EmailSchedulerAgent = None
    ImapReplyAgent = None


# API Routers/Routes
# From app.routes directory
try:
    logger.debug("Attempting to import from app.routes...")
    from app.routes import auth as auth_router_module
    from app.routes import icpmatch as icp_match_router_module
    from app.routes import workflow as workflow_router_module
    from app.routes import leadworkflow as leadworkflow_router_module
    from app.routes import crm as crm_routes_module
    from app.routes import agents as agents_router_module
    from app.routes import insidesales as insidesales_router_module
    from app.routes import scheduler as scheduler_router_module
    from app.routes import leadenrichment as leadenrichment_router_module
    logger.info("Successfully imported modules from 'app.routes'.")
except Exception as e_routes:
    logger.error(f"FATAL ERROR during import from 'app.routes': {type(e_routes).__name__} - {e_routes}", exc_info=True)
    raise SystemExit(f"Failed to import a module from app.routes: {e_routes}") from e_routes

# From app.routers directory
try:
    logger.debug("Attempting to import from app.routers...")
    from app.routers import icp as icp_crud_router_module
    from app.routers import offering as offering_router_module
    from app.routers import campaigns as campaigns_router_module
    from app.routers import email_settings as email_settings_router_module
    from app.routers import leads as leads_router_module
    # Add your new dashboard router if you create one
    # from app.routers import dashboard as dashboard_router_module
    logger.info("Successfully imported modules from 'app.routers'.")
except Exception as e_routers:
    logger.error(f"FATAL ERROR during import from 'app.routers': {type(e_routers).__name__} - {e_routers}", exc_info=True)
    raise SystemExit(f"Failed to import a module from app.routers: {e_routers}") from e_routers

# Global Agent Instances (Consider if these are better as singletons or passed via DI)
# For schedulers, a single instance is usually fine.
email_scheduler_agent_instance = None
if EmailSchedulerAgent:
    try:
        email_scheduler_agent_instance = EmailSchedulerAgent()
        logger.info("EmailSchedulerAgent instance created for scheduler.")
    except Exception as e_sa:
        logger.error(f"Failed to instantiate EmailSchedulerAgent: {e_sa}", exc_info=True)

imap_reply_agent_instance = None
if ImapReplyAgent:
    try:
        imap_reply_agent_instance = ImapReplyAgent()
        logger.info("ImapReplyAgent instance created for scheduler.")
    except Exception as e_ira:
        logger.error(f"Failed to instantiate ImapReplyAgent: {e_ira}", exc_info=True)

# ==============================================
# --- Create FastAPI App Instance ---
# ==============================================
try:
    app = FastAPI(
        title=settings.app_name,
        description="API to manage and process sales leads for multiple organizations.",
        version=getattr(settings, "app_version", "0.3.0"), # Get version from settings if available
    )
    logger.info(f"FastAPI app '{settings.app_name}' v{app.version} created successfully.")
except AttributeError as e_attr_settings:
    print(f"FATAL ERROR: Missing required attributes in settings for FastAPI app creation: {e_attr_settings}")
    raise SystemExit("FastAPI app creation failed due to missing settings.") from e_attr_settings
except Exception as e_app_create:
    print(f"FATAL ERROR: Could not create FastAPI app instance: {e_app_create}")
    raise SystemExit("FastAPI app creation failed.") from e_app_create

# ==============================================
# --- Configure CORS Middleware ---
# ==============================================
origins_to_allow = getattr(settings, "allowed_origins_list", [])
if not origins_to_allow:
    origins_to_allow = ["*"]
    logger.warning("ALLOWED_ORIGINS not specified or empty in settings. Defaulting CORS to allow all origins ('*'). Not recommended for production.")
else:
    logger.info(f"Configuring CORS for specified origins: {origins_to_allow}")

try:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins_to_allow,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"], # Be explicit
        allow_headers=["*"], # Or specify allowed headers
    )
    logger.info("CORS middleware configured.")
except Exception as e_cors:
    logger.error(f"Failed to configure CORS middleware: {e_cors}", exc_info=True)

# ==============================================
# --- Scheduler Instance ---
# ==============================================
scheduler = None # Global scheduler instance

# ==============================================
# --- Startup & Shutdown Events ---
# ==============================================
@app.on_event("startup")
async def on_app_startup():
    global scheduler # Allow modification of the global scheduler instance
    logger.info("Application startup event triggered.")
    
    # 1. Database Initialization
    if initialize_db:
        logger.info("Attempting database initialization...")
        try:
            initialize_db()
            logger.info("Database initialization logic executed successfully.")
        except Exception as e_db_init:
            logger.error(f"An error occurred during database initialization on startup: {e_db_init}", exc_info=True)
    else:
        logger.warning("'initialize_db' function not available. Database auto-initialization skipped.")

    # 2. Initialize and Start Schedulers
    scheduler = AsyncIOScheduler(timezone=str(timezone.utc)) # Explicitly UTC

    # Email Sending Scheduler
    if getattr(settings, "ENABLE_EMAIL_SCHEDULER", False) and email_scheduler_agent_instance:
        interval_send = int(getattr(settings, "EMAIL_SCHEDULER_INTERVAL_MINUTES", 10))
        scheduler.add_job(
            email_scheduler_agent_instance.run_scheduler_cycle, # Direct call to method
            "interval",
            minutes=interval_send,
            id="email_sending_job", # Give job an ID
            replace_existing=True
        )
        logger.info(f"Email sending job added to scheduler. Interval: {interval_send} minutes.")
    else:
        logger.info("Email sending scheduler is disabled or agent instance failed.")

    # IMAP Reply Polling Scheduler
    if getattr(settings, "ENABLE_IMAP_REPLY_POLLER", False) and imap_reply_agent_instance:
        interval_poll = int(getattr(settings, "IMAP_POLLER_INTERVAL_MINUTES", 15))
        scheduler.add_job(
            imap_reply_agent_instance.trigger_imap_polling_for_all_orgs, # Direct call to method
            "interval",
            minutes=interval_poll,
            id="imap_reply_polling_job", # Give job an ID
            replace_existing=True
        )
        logger.info(f"IMAP reply polling job added to scheduler. Interval: {interval_poll} minutes.")
    else:
        logger.info("IMAP reply polling scheduler is disabled or agent instance failed.")
    
    if scheduler.get_jobs(): # Start scheduler only if there are jobs
        try:
            scheduler.start()
            logger.info("APScheduler started.")
        except Exception as e_scheduler_start:
            logger.error(f"Failed to start APScheduler: {e_scheduler_start}", exc_info=True)
    else:
        logger.info("APScheduler not started as no jobs were added.")
        
    logger.info("Application startup sequence complete.")


@app.on_event("shutdown")
async def on_app_shutdown():
    logger.info("Application shutdown event triggered.")
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False) # wait=False for quicker shutdown
        logger.info("APScheduler shut down.")
    logger.info("Application shutdown sequence complete.")

# ==============================================
# --- Include API Routers ---
# ==============================================
logger.info("Including API routers...")
router_modules_to_include = {
    # From app.routes
    "Auth": auth_router_module, "ICP Matching": icp_match_router_module,
    "Workflow": workflow_router_module, "Lead Workflow": leadworkflow_router_module,
    "CRM Routes": crm_routes_module, "Agents Routes": agents_router_module,
    "Inside Sales": insidesales_router_module, "Scheduler Routes": scheduler_router_module,
    "Lead Enrichment": leadenrichment_router_module,
    # From app.routers
    "ICP CRUD": icp_crud_router_module, "Offerings": offering_router_module,
    "Campaigns": campaigns_router_module, "Email Settings": email_settings_router_module,
    "Leads": leads_router_module,
    # "Dashboard Data": dashboard_router_module # Add when you create it
}

for name, module_instance in router_modules_to_include.items():
    try:
        if module_instance and hasattr(module_instance, 'router'):
            app.include_router(module_instance.router)
            logger.debug(f"Successfully included router for '{name}'.")
        elif module_instance:
            logger.warning(f"Module '{name}' imported but has no 'router' attribute. Skipping inclusion.")
        else: # Module instance is None (likely due to an earlier caught import error that wasn't fatal)
            logger.warning(f"Module for '{name}' was not successfully imported (is None). Cannot include router.")
    except Exception as e_include_router:
        logger.error(f"ERROR: Failed to include router for '{name}': {e_include_router}", exc_info=True)

# ==============================================
# --- Root Endpoint ---
# ==============================================
@app.get("/", tags=["Root"], summary="API Root/Health Check")
async def read_root():
    return {
        "status": f"{getattr(settings, 'app_name', 'SalesTroopz API')} backend is live!",
        "environment": getattr(settings, 'environment', 'unknown'),
        "version": app.version
    }

# --- Final Confirmation Log ---
logger.info(f"--- {getattr(settings, 'app_name', 'SalesTroopz API')} FastAPI application module loading complete. Awaiting Uvicorn startup events. ---")
