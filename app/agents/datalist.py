# app/agents/datalist.py

from typing import List
from pydantic import BaseModel
import random

class ICPModel(BaseModel):
    industry: str
    company_size: str
    title_keywords: List[str]

class Prospect(BaseModel):
    name: str
    title: str
    company: str
    email: str

class DataListBuilderAgent:
    def generate_prospects(self, icp: ICPModel) -> List[Prospect]:
        sample_names = ["Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona"]
        sample_companies = ["Acme Inc", "Globex", "Initech", "Umbrella Corp", "Stark Industries"]
        
        prospects = []
        for _ in range(5):  # Generate 5 dummy prospects
            name = random.choice(sample_names)
            company = random.choice(sample_companies)
            title = f"{random.choice(icp.title_keywords)} Manager"
            email = f"{name.lower()}@{company.replace(' ', '').lower()}.com"
            prospect = Prospect(name=name, title=title, company=company, email=email)
            prospects.append(prospect)
        
        return prospects
