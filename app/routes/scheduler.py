from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import Any, List, Optional, Dict

# Import project modules
from app.auth.dependencies import get_current_user # Secure the endpoint (optional, could be admin-only)
from app.schemas import UserPublic # For type hinting current_user
# Import the agent containing the cycle logic
from app.agents.emailscheduler import EmailSchedulerAgent
from app.utils.logger import logger

# Define Router
router = APIRouter(
    prefix="/api/v1/scheduler",
    tags=["Scheduler (Admin/System)"] # Tag appropriately
)

# Endpoint to manually trigger the scheduler cycle
# Added BackgroundTasks to run it without blocking the API response
@router.post("/run-cycle", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scheduler_cycle(
    background_tasks: BackgroundTasks,
    # Optional: Add authentication to restrict who can run this
    # current_user: UserPublic = Depends(get_current_user)
):
    """
    Manually triggers one cycle of the email sending scheduler.
    The actual processing happens in the background.
    """
    logger.info("API: Received request to trigger scheduler cycle.")

    def run_cycle_in_background():
        try:
            scheduler = EmailSchedulerAgent()
            scheduler.run_scheduler_cycle()
        except Exception as e:
            logger.error(f"Error running scheduler cycle in background: {e}", exc_info=True)

    background_tasks.add_task(run_cycle_in_background)

    return {"message": "Scheduler cycle trigger request accepted. Processing runs in background."}
