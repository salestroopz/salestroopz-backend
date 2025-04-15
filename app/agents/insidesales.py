# app/agents/insidesales.py

from pydantic import BaseModel
from typing import Optional

class ProspectProfile(BaseModel):
    name: str
    company: str
    title: str
    industry: Optional[str] = None
    pain_points: Optional[str] = None

def generate_email(profile: ProspectProfile):
    # Simple mock personalization logic
    subject = f"{profile.name}, can we help {profile.company}?"
    body = f"""
Hi {profile.name},

I noticed you're the {profile.title} at {profile.company}.
We work with teams like yours in {profile.industry or 'your industry'} to solve challenges like:
{profile.pain_points or '- Improving lead quality\n- Reducing time spent on outreach\n- Boosting response rates'}

Let me know if you'd be open to a quick call!

Best,  
SalesTroopz.ai

    return {"subject": subject.strip(), "body": body.strip()}
