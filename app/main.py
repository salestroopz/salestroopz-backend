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
