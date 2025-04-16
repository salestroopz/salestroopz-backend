from fastapi import APIRouter
from app.schemas import ICPModel
from app.agents.leadworkflow import LeadWorkflowAgent

router = APIRouter()

@router.post("/full-cycle")
def run_full_cycle_workflow(icp: ICPModel):
    agent = LeadWorkflowAgent()
    return agent.run_full_workflow(icp)
