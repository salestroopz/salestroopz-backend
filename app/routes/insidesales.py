# app/routes/insidesales.py

from fastapi import APIRouter
from app.agents.insidesales import generate_email, ProspectProfile

router = APIRouter()

@router.post("/generate_email")
def generate_sales_email(profile: ProspectProfile):
    return generate_email(profile)
