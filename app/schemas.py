from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any, Literal # Added types we need
from enum import Enum #

# --- Authentication & User Schemas ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase): # <--- IS THIS EXACTLY PRESENT?
    password: str
    organization_name: str

class UserPublic(UserBase):
    id: int
    organization_id: int
    organization_name: str # Include org name for convenience

    class Config:
        orm_mode = True # Allow mapping from dict/db rows

# --- Existing Schemas (from your image) ---

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
    email: Optional[str] = None # Consider changing to Optional[EmailStr] = None for validation

class LeadEnrichmentResponse(BaseModel):
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[str] = None # Consider changing to Optional[EmailStr] = None
    linkedin_profile: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None


# --- Schemas for Core Lead Workflow & API (from our previous steps) ---

# Model for data expected when CREATING/INPUTTING a lead via /workflow/start API
class LeadInput(BaseModel):
    name: Optional[str] = None
    email: EmailStr  # Use EmailStr for basic email validation
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = "API Input" # Default source if not provided

# Model for data RETURNED when GETTING leads from the DB via /leads API
class LeadResponse(BaseModel):
    id: int
    name: Optional[str] = None
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    matched: Optional[int] = None # Reflects DB column (INTEGER 0 or 1)
    reason: Optional[str] = None
    crm_status: Optional[str] = None
    appointment_confirmed: Optional[int] = None # Reflects DB column (INTEGER 0 or 1)

    # This config helps FastAPI convert DB objects/dicts to this model
    class Config:
        orm_mode = True # Helps map ORM objects or dicts easily


# --- Schemas for Chatbot Interaction (Phases 1 & 2) ---

class ICPDefinition(BaseModel):
    """Defines the Ideal Customer Profile details collected via chatbot."""
    industry: Optional[str] = Field(None, description="Target industry")
    title: Optional[str] = Field(None, description="Target job title(s)")
    company_size: Optional[str] = Field(None, description="Target company size range (e.g., '11-50', '51-200')")
    # Add other fields collected via chat if necessary, e.g., region, pain_points
    # region: Optional[str] = Field(None, ...)
    # pain_points: Optional[List[str]] = Field(default_factory=list, ...)

class WorkflowInitiateRequest(BaseModel):
    """Request body for the /workflow/initiate endpoint driven by chatbot."""
    icp: ICPDefinition # Use the ICP details collected by the chatbot
    source_type: Literal["file_upload", "apollo", "crm", "manual_entry"] # Define allowed source types
    source_details: Optional[Dict[str, Any]] = Field(None, description="Additional details specific to the source type (e.g., filename, search ID)")

class AppointmentStatus(str, Enum):
    """Enumeration for possible appointment statuses."""
    PENDING = "pending"           # Initial state or waiting for confirmation
    CONFIRMED = "confirmed"       # Appointment details agreed upon
    SCHEDULED = "scheduled"       # Added to calendar / specific time set
    CANCELLED = "cancelled"       # Appointment cancelled
    COMPLETED = "completed"       # Appointment took place
    NO_SHOW = "no_show"           # Scheduled but attendee did not show up
