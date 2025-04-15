# app/routes/scheduler.py

from fastapi import APIRouter
from app.agents.emailscheduler import schedule_email, list_scheduled_emails, EmailScheduleRequest

router = APIRouter()

@router.post("/schedule_email")
def schedule(data: EmailScheduleRequest):
    return schedule_email(data)

@router.get("/scheduled_emails")
def get_scheduled():
    return list_scheduled_emails()
