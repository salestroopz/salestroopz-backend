from fastapi import FastAPI
from app.config import Settings
from fastapi.middleware.cors import CORSMiddleware # <--- Import CORS Middleware
from app.routes import workflow
from app.db.database import initialize_db


# Import routers from the correct folders
from app.routers import icp, offering
from app.routes import crm, agents, emailcampaign, insidesales, scheduler, leadenrichment, leadenrichment, icpmatch , leadworkflow 

# If you need datalist agent separately
from app.agents import datalist  # for direct calls if needed

from app.agents.crmagent import CRMConnectorAgent

# Create a single instance to be used throughout the app
crm_agent_instance = CRMConnectorAgent()

# Pass crm_agent_instance to other agents/functions that need it
# (e.g., pass it to the LeadWorkflowAgent during its initialization)

app = FastAPI(title="Salestroopz Backend", version="0.1.0")
settings = Settings()

@app.get("/")
async def root():
    return {"status": "Salestroopz backend is live!"}

# Include all routers
app.include_router(icp.router, prefix="/icp", tags=["ICP"])
app.include_router(offering.router, prefix="/offering", tags=["Offering"])
app.include_router(crm.router, prefix="/crm", tags=["CRM"])
app.include_router(agents.router)
app.include_router(emailcampaign.router, prefix="/email", tags=["Email Campaign Manager"])
app.include_router(insidesales.router, prefix="/sales", tags=["Inside Sales Agent"])
app.include_router(scheduler.router, prefix="/campaigns", tags=["Email Scheduler Agent"])
app.include_router(leadenrichment.router, prefix="/leads", tags=["Lead Enrichment Agent"])
app.include_router(icpmatch.router)
app.include_router(leadworkflow.router)
app.include_router(workflow.router, prefix="/workflow", tags=["Lead Workflow"])

app = FastAPI(
    title="SalesTroopz Lead Workflow API",
    description="API to manage and process sales leads.",
    version="0.1.0",
)

# --- Configure CORS --- <--- ADD THIS SECTION
# List of origins allowed to make requests to this backend.
# IMPORTANT: Replace "YOUR_STREAMLIT_APP_URL" with the actual URL
# Render gives your Streamlit service (e.g., https://salestroopz-chatbot-ui.onrender.com)
# You might also need to add http://localhost:8501 if you ever test locally
origins = [
    "https://salestroopz-chatbot-ui.onrender.com", # Replace with your Streamlit service URL
    # "http://localhost:8501", # Uncomment if you run Streamlit locally for testing
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # Allows specific origins
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods (GET, POST, etc.)
    allow_headers=["*"], # Allows all headers
)
# --- END OF CORS CONFIGURATION ---


@app.on_event("startup")
async def startup_event():
    print("Application starting up...")
    initialize_db()
    print("Database initialization complete.")

app.include_router(workflow.router)

@app.get("/", tags=["Root"])
async def read_root():
    return {
        "message": "Welcome to the SalesTroopz Lead Workflow API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
