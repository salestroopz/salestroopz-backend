from fastapi import APIRouter
from app.schemas import OriginalICPRequest, ICPResponse

router = APIRouter()

@router.post("/", response_model=ICPResponse)
async def define_icp(icp: OriginalICPRequest):
    # Very simple example logic for now
    summary = (
        f"Targeting {icp.industry} companies with {icp.employee_range} employees"
        + (f" in {icp.region}" if icp.region else "")
        + (f" facing {', '.join(icp.pain_points)}" if icp.pain_points else "")
        + "."
    )
    return ICPResponse(message="ICP defined successfully", icp_summary=summary)
