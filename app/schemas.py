from pydantic import BaseModel, Field
from typing import Optional, List

class ICPRequest(BaseModel):
    industry: str = Field(..., example="SaaS")
    employee_range: str = Field(..., example="51-200")
    region: Optional[str] = Field(None, example="North America")
    pain_points: Optional[List[str]] = Field(default_factory=list)

class ICPResponse(BaseModel):
    message: str
    icp_summary: str
