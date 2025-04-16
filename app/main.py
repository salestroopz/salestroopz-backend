from fastapi import FastAPI
from app.config import Settings

# Import routers from the correct folders
from app.routers import icp, offering
from app.routes import crm, agents, emailcampaign, insidesales, scheduler, leadenrichment

# If you need datalist agent separately
from app.agents import datalist  # for direct calls if needed

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
