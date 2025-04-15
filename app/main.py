from fastapi import FastAPI
from app.routers import icp
from app.config import Settings

app = FastAPI(title="Salestroopz Backend", version="0.1.0")

settings = Settings()

@app.get("/")
async def root():
    return {"status": "Salestroopz backend is live!"}

app.include_router(icp.router, prefix="/icp", tags=["ICP"])
from app.routers import offering

app.include_router(offering.router, prefix="/api", tags=["Offering"])
# Add to your FastAPI app in main.py
from app.agents.datalist import ICPModel, DataListBuilderAgent

@app.post("/generate-prospects")
def generate_prospects(icp: ICPModel):
    agent = DataListBuilderAgent()
    return agent.generate_prospects(icp)

from fastapi import FastAPI
from app.agents import datalist  # make sure import path is correct

@app.post("/generate-prospects")
def generate_prospects(data: datalist.ProspectRequest):
    return datalist.generate_prospect_data(data)
from app.routes import agents  # add this
app.include_router(agents.router)  # and this
