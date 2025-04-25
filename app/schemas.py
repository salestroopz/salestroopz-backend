# app/schemas.py

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from datetime import datetime # <--- IMPORT datetime

# --- Authentication & User Schemas ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str
    organization_name: str

class UserPublic(UserBase):
    id: int
    organization_id: int
    organization_name: str

    class Config:
        # --- UPDATE: Use from_attributes for Pydantic v2 ---
        from_attributes = True # Changed from orm_mode

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None


# --- Manual Lead Entry Schema ---
class ManualLeadData(BaseModel):
    name: Optional[str] = None
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None


# --- Lead Enrichment Schemas (Keep if used by enrichment agent) ---
class LeadEnrichmentRequest(BaseModel):
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[EmailStr] = None # Changed to EmailStr

class LeadEnrichmentResponse(BaseModel):
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[EmailStr] = None # Changed to EmailStr
    linkedin_profile: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None


# --- Core Lead Workflow Schemas ---
class LeadInput(BaseModel): # For direct lead input/processing trigger
    name: Optional[str] = None
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = "API Input"

class LeadResponse(BaseModel): # For returning leads from DB
    id: int
    name: Optional[str] = None
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    # Added enrichment fields to response
    linkedin_profile: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    # Workflow fields
    matched: Optional[int] = None
    reason: Optional[str] = None
    crm_status: Optional[str] = None
    appointment_confirmed: Optional[int] = None
    created_at: Optional[datetime] = None # Added created_at

    class Config:
        # --- UPDATE: Use from_attributes for Pydantic v2 ---
        from_attributes = True # Changed from orm_mode


# --- Chatbot Interaction Schemas ---
class ICPDefinition(BaseModel): # Used internally for chatbot flow
    industry: Optional[str] = Field(None, description="Target industry")
    title: Optional[str] = Field(None, description="Target job title(s)")
    company_size: Optional[str] = Field(None, description="Target company size range")

class WorkflowInitiateRequest(BaseModel): # For the /initiate endpoint
    # Correct Indent Level (e.g., 4 spaces)
    icp: ICPDefinition
    # Correct Indent Level
    source_type: Literal["file_upload", "apollo", "crm", "manual_entry"]

    # Correct Indent Level (Align with icp and source_type)
    source_details: Optional[Dict[str, Any]] = Field(
        # Further Indent for arguments within Field()
        default=None,
        description="""
        Additional details.
        If source_type='file_upload', expected: {'filename': 'unique_uuid.ext'}.
        If source_type='manual_entry', expected: {'manual_leads': List[ManualLeadData]}.
        """ # Close the multi-line string properly
    ) # Close the Field() parenthesis

# --- Appointment Status Enum ---
class AppointmentStatus(str, Enum):
    PENDING = "pending"           # Initial state or waiting for confirmation
    CONFIRMED = "confirmed"       # Appointment details agreed upon
    SCHEDULED = "scheduled"       # Added to calendar / specific time set
    CANCELLED = "cancelled"       # Appointment cancelled
    COMPLETED = "completed"       # Appointment took place
    NO_SHOW = "no_show"           # Scheduled but attendee did not show up
  

# --- === NEW SCHEMAS FOR ICP MANAGEMENT API === ---

class ICPInput(BaseModel):
    """Schema for validating data when Creating/Updating an ICP via the API."""
    name: Optional[str] = Field('Default ICP', description="A name for this ICP definition", examples=["Tech Startup ICP"])
    title_keywords: List[str] = Field(default_factory=list, description="List of target job titles/keywords", examples=[["VP Engineering", "CTO"]])
    industry_keywords: List[str] = Field(default_factory=list, description="List of target industries/keywords", examples=[["SaaS", "Cloud Computing"]])
    company_size_rules: Dict[str, Any] = Field(default_factory=dict, description='Rules for company size (e.g., {"min": 50, "max": 500})', examples=[{"min": 51, "max": 200}])
    location_keywords: List[str] = Field(default_factory=list, description="List of target locations/keywords", examples=[["London", "Remote"]])
    # Add other fields corresponding to icps table columns (e.g., pain_points) if needed


class ICPResponseAPI(BaseModel): # Renamed to avoid conflict with original ICPResponse
    """Schema for returning an ICP definition from the API."""
    id: int
    organization_id: int
    name: str
    # Fields are parsed from JSON by the DB layer, so use Python types here
    title_keywords: Optional[List[str]] = None
    industry_keywords: Optional[List[str]] = None
    company_size_rules: Optional[Dict[str, Any]] = None
    location_keywords: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Use this for Pydantic v2

# --- === END OF NEW ICP SCHEMAS === ---

# --- === NEW SCHEMAS FOR OFFERING MANAGEMENT API === ---

class OfferingInput(BaseModel):
    """Schema for validating data when Creating/Updating an Offering via API."""
    name: str = Field(..., min_length=1, examples=["Cloud Migration Assessment"])
    description: Optional[str] = Field(None, examples=["Detailed analysis of your current infrastructure..."])
    key_features: List[str] = Field(default_factory=list, examples=[["Cost Projection", "Security Audit"]])
    target_pain_points: List[str] = Field(default_factory=list, examples=[["High AWS Bills", "Compliance Concerns"]])
    call_to_action: Optional[str] = Field(None, examples=["Schedule a 15-min discovery call"])
    is_active: bool = Field(True, description="Whether this offering is currently active")

class OfferingResponse(BaseModel):
    """Schema for returning an Offering definition from the API."""
    id: int
    organization_id: int
    name: str
    description: Optional[str] = None
    key_features: Optional[List[str]] = None # Parsed from JSON
    target_pain_points: Optional[List[str]] = None # Parsed from JSON
    call_to_action: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Pydantic v2

# app/schemas.py
# ... (keep all existing imports and schemas) ...
from datetime import datetime

# --- === NEW SCHEMAS FOR CAMPAIGN/STEP MANAGEMENT === ---

# --- Campaign Schemas ---
class CampaignStepInput(BaseModel):
    """Input for creating a single campaign step."""
    step_number: int = Field(..., gt=0, description="Order of the step (1, 2, ...)")
    delay_days: int = Field(..., ge=0, description="Days to wait after previous step/enrollment")
    subject_template: Optional[str] = Field(None, description="Subject line template (use {{placeholders}})")
    body_template: Optional[str] = Field(None, description="Email body template (use {{placeholders}})")
    is_ai_crafted: bool = Field(False, description="Set true if AI should generate content for this step")

class CampaignStepResponse(CampaignStepInput):
    """Response model for a campaign step, includes DB ID."""
    id: int
    campaign_id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CampaignInput(BaseModel):
    """Input for creating or updating a campaign definition."""
    name: str = Field(..., min_length=1, examples=["Q3 Fintech Outreach"])
    description: Optional[str] = Field(None, examples=["Campaign targeting Fintech CTOs..."])
    is_active: bool = Field(True)
    # Optionally allow creating steps along with campaign
    steps: Optional[List[CampaignStepInput]] = Field(None, description="Optionally define steps during campaign creation")

class CampaignResponse(BaseModel):
    """Response model for a campaign definition."""
    id: int
    organization_id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    # Optionally include steps in the response
    steps: Optional[List[CampaignStepResponse]] = None # Loaded separately if needed

    class Config:
        from_attributes = True

# --- Lead Status Schema (Optional - for API responses if needed) ---
class LeadCampaignStatusResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: int
    organization_id: int
    current_step_number: int
    status: str
    last_email_sent_at: Optional[datetime] = None
    next_email_due_at: Optional[datetime] = None
    last_response_type: Optional[str] = None
    last_response_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- === END OF NEW CAMPAIGN/STEP SCHEMAS === ---
