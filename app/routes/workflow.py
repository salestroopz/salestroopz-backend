from fastapi import APIRouter
from app.schemas import ICPRequest
from app.agents.leadworkflow import LeadWorkflowAgent
from app.db.sqlhelper import get_all_leads  # 👈 make sure this is imported
from app.auth.dependencies import get_current_user
from app.schemas import UserPublic # Also needed for type hin

router = APIRouter()

@router.post("/full-cycle")
def run_full_cycle_workflow(icp: ICPRequest):
    agent = LeadWorkflowAgent()
    return agent.run_full_workflow(icp)

@router.get("/leads", tags=["Leads"])
def list_saved_leads():
    leads = get_all_leads()
    return {"total": len(leads), "data": leads}

# ... router definition ...

@router.get("/leads", response_model=List[LeadResponse])
def list_saved_leads(current_user: UserPublic = Depends(get_current_user)): # <-- Usage
    # ... function body ...
    leads = database.get_all_leads(organization_id=current_user.organization_id)
    return leads
