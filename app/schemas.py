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


class LeadEnrichmentRequest(BaseModel):
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[str] = None

class LeadEnrichmentResponse(BaseModel):
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[str] = None
    linkedin_profile: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
