from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Salestroopz backend is live!"}

# Define the ICP schema
class ICPRequest(BaseModel):
    industry: str
    company_size: str
    locations: List[str]
    job_titles: List[str]
    tech_stack: Optional[List[str]] = []
    buying_triggers: Optional[List[str]] = []

class ICPSuggestion(BaseModel):
    refined_industry: str
    suggested_job_titles: List[str]
    keywords: List[str]

@app.post("/define_icp", response_model=ICPSuggestion)
def define_icp(icp: ICPRequest):
    # Dummy logic to simulate AI suggestion
    refined_industry = icp.industry.strip().title()
    suggested_job_titles = list(set(icp.job_titles + ["Head of Growth", "VP Sales"]))
    keywords = [refined_industry.lower(), *icp.company_size.split(), *icp.locations]

    return ICPSuggestion(
        refined_industry=refined_industry,
        suggested_job_titles=suggested_job_titles,
        keywords=keywords
    )
