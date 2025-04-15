# app/agents/emailscheduler.py

from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional
import uuid

# Mock DB (can be replaced later with real DB or file system)
email_schedule_store = []

class EmailScheduleRequest(BaseModel):
    recipient: str
    subject: str
    body: str
    send_at: Optional[datetime] = None

class EmailScheduled(BaseModel):
    id: str
    recipient: str
    subject: str
    body: str
    send_at: datetime
    status: str = "scheduled"

def schedule_email(data: EmailScheduleRequest):
    scheduled_email = EmailScheduled(
        id=str(uuid.uuid4()),
        recipient=data.recipient,
        subject=data.subject,
        body=data.body,
        send_at=data.send_at or datetime.utcnow()
    )
    email_schedule_store.append(scheduled_email)
    return scheduled_email

def list_scheduled_emails():
    return email_schedule_store
