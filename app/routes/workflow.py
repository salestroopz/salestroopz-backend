from fastapi import APIRouter
from app.schemas import ICPRequest
from app.agents.leadworkflow import LeadWorkflowAgent
from app.db.sqlhelper import get_all_leads  # 👈 make sure this is imported

router = APIRouter()

@router.post("/full-cycle")
def run_full_cycle_workflow(icp: ICPRequest):
    agent = LeadWorkflowAgent()
    return agent.run_full_workflow(icp)

@router.get("/leads", tags=["Leads"])
def list_saved_leads():
    leads = get_all_leads()
    return {"total": len(leads), "data": leads}
