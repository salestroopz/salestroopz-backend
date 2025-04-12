import logging # <-- Add this
from fastapi import FastAPI

# Configure basic logging (optional but helpful)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

@app.get("/")
async def home(): # <-- Changed to async def (good practice)
    logger.info("====== Root route '/' is being executed! ======") # <-- Add this log line
    return {"status": "Salestroopz backend is live!"}

# Optional: Add another simple test route
@app.get("/ping")
async def ping():
    logger.info("====== Ping route '/ping' is being executed! ======")
    return {"ping": "pong"}
