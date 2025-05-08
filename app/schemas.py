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
class LeadBase(BaseModel): # Common fields
    name: Optional[str] = Field(None, examples=["Jane Doe"])
    email: EmailStr = Field(..., examples=["jane.doe@example.com"]) # Email is mandatory for new leads
    company: Optional[str] = Field(None, examples=["Acme Corp"])
    title: Optional[str] = Field(None, examples=["Marketing Manager"])
    source: Optional[str] = Field("API Input", examples=["Manual Entry", "CSV Upload"])
    linkedin_profile: Optional[str] = Field(None, examples=["https://linkedin.com/in/janedoe"])
    company_size: Optional[str] = Field(None, examples=["51-200"])
    industry: Optional[str] = Field(None, examples=["SaaS"])
    location: Optional[str] = Field(None, examples=["New York, USA"])
    # Workflow fields
    matched: Optional[bool] = Field(False) # Using bool
    reason: Optional[str] = Field(None, description="Reason for match/no match")
    crm_status: Optional[str] = Field("pending", description="Status in CRM")
    appointment_confirmed: Optional[bool] = Field(False) # Using bool

class LeadInput(LeadBase): # For creating new leads or full updates (via save_lead)
    """Schema for creating or fully updating a lead."""
    pass # Inherits all fields from LeadBase

class LeadUpdatePartialInput(BaseModel): # For PATCH requests
    """Schema for partially updating a lead. All fields are optional."""
    name: Optional[str] = Field(None, examples=["Jane Doe"])
    # Email usually not updatable as it's often a key identifier with organization_id
    # email: Optional[EmailStr] = Field(None, examples=["jane.doe@example.com"])
    company: Optional[str] = Field(None, examples=["Acme Corp"])
    title: Optional[str] = Field(None, examples=["Marketing Manager"])
    source: Optional[str] = Field(None, examples=["Manual Entry", "CSV Upload"])
    linkedin_profile: Optional[str] = Field(None, examples=["https://linkedin.com/in/janedoe"])
    company_size: Optional[str] = Field(None, examples=["51-200"])
    industry: Optional[str] = Field(None, examples=["SaaS"])
    location: Optional[str] = Field(None, examples=["New York, USA"])
    matched: Optional[bool] = Field(None) # Allow updating to True/False/None
    reason: Optional[str] = Field(None)
    crm_status: Optional[str] = Field(None)
    appointment_confirmed: Optional[bool] = Field(None) # Allow updating to True/False/None

class LeadResponse(LeadBase): # For returning leads from DB
    """Schema for returning lead data from the API."""
    id: int
    organization_id: int # Usually good to include the org_id in responses
    created_at: datetime
    updated_at: Optional[datetime] = None # Add if you have this column in DB

    class Config:
        from_attributes = True

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



# --- === Email Settings Schemas === ---

class EmailProviderType(str, Enum):
    # Enum for allowed provider types
    SMTP = "smtp"
    AWS_SES = "aws_ses"
    # Add others later like GOOGLE_OAUTH, SENDGRID_API etc.

class EmailSettingsBase(BaseModel):
    provider_type: Optional[EmailProviderType] = Field(None, description="The email sending provider type")
    verified_sender_email: Optional[EmailStr] = Field(None, description="The verified email address to send from")
    sender_name: Optional[str] = Field(None, description="The 'From' name displayed in emails", examples=["Sales Team @ Company"])

    # SMTP Specific - optional overall, but required if provider_type is 'smtp'
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None # Typically 587 (TLS) or 465 (SSL)
    smtp_username: Optional[str] = None

    # AWS SES Specific - optional overall, but required if provider_type is 'aws_ses'
    # Store API keys securely, these are just for input validation structure
    aws_region: Optional[str] = Field(None, examples=["us-east-1"])

    # Flag indicating if setup is considered complete by user/system
    is_configured: Optional[bool] = Field(False)

class EmailSettingsInput(EmailSettingsBase):
    """Schema for inputting email settings. Secrets included here."""
    # Secrets are optional on input (user might not want to update them every time)
    smtp_password: Optional[str] = Field(None, description="SMTP Password (write-only)")
    aws_access_key_id: Optional[str] = Field(None, description="AWS Access Key ID (write-only)")
    aws_secret_access_key: Optional[str] = Field(None, description="AWS Secret Access Key (write-only)")

    # Add fields for other providers (API Key, OAuth tokens) here when needed

class EmailSettingsResponse(EmailSettingsBase):
    """Schema for returning email settings. Excludes sensitive data."""
    organization_id: int
    id: int
    # Indicate if essential credentials seem to be set for the chosen provider
    # Note: This is a basic check, doesn't guarantee validity
    credentials_set: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Pydantic v2

# --- === END Email Settings Schemas === ---

# --- === NEW SCHEMAS FOR CAMPAIGN/STEP MANAGEMENT === ---

# --- Campaign Schemas ---
class CampaignStepInput(BaseModel):
    """Input for creating a single campaign step."""
    step_number: int = Field(..., gt=0, description="Order of the step (1, 2, ...)")
    delay_days: int = Field(..., ge=0, description="Days to wait after previous step/enrollment")
    subject_template: Optional[str] = Field(None, description="Subject line template (use {{placeholders}})")
    body_template: Optional[str] = Field(None, description="Email body template (use {{placeholders}})")
    is_ai_crafted: bool = Field(False, description="Set true if AI should generate content for this step")
    follow_up_angle: Optional[str] = Field(None, description="Hint for AI personalization") # Added field

class CampaignStepResponse(CampaignStepInput):
    """Response model for a campaign step, includes DB ID."""
    id: int
    campaign_id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CampaignStepBase(BaseModel): # Added a base for consistency
    step_number: int = Field(..., gt=0, description="Order of the step (1, 2, ...)")
    delay_days: int = Field(..., ge=0, description="Days to wait after previous step/enrollment")
    subject_template: Optional[str] = Field(None, description="Subject line template (use {{placeholders}})")
    body_template: Optional[str] = Field(None, description="Email body template (use {{placeholders}})")
    follow_up_angle: Optional[str] = Field(None, description="Hint for AI personalization / Angle of the step")

class CampaignStepInput(CampaignStepBase): # This will primarily be used by the AI agent
    # is_ai_crafted: bool = Field(True, description="Indicates if the step was crafted by AI") # Agent sets this to True
    pass

class CampaignStepResponse(CampaignStepBase):
    """Response model for a campaign step, includes DB ID."""
    id: int
    campaign_id: int
    organization_id: int # Good to have for context if ever needed directly
    is_ai_crafted: bool = Field(False, description="True if AI generated content for this step") # This comes from DB
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Replaces orm_mode in Pydantic v2

# --- Campaign Schemas ---
class CampaignInput(BaseModel): # For POST /campaigns/
    """Input for creating a campaign definition. Steps are AI-generated."""
    name: str = Field(..., min_length=1, examples=["Q3 Fintech Outreach"])
    description: Optional[str] = Field(None, examples=["Campaign targeting Fintech CTOs..."])
    is_active: bool = Field(False) # Default to False, activate after AI generates steps perhaps
    icp_id: Optional[int] = Field(None, description="Optional ID of the ICP to associate with this campaign")
    offering_id: Optional[int] = Field(None, description="Optional ID of the Offering to associate with this campaign") # <<< ADDED
    # steps: Optional[List[CampaignStepInput]] = Field(None, ...) # <<< REMOVED

class CampaignUpdate(BaseModel): # For PUT /campaigns/{id}
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = None
    is_active: Optional[bool] = None
    icp_id: Optional[int] = None
    offering_id: Optional[int] = None
    # trigger_ai_regeneration: bool = Field(False, description="Set to true to re-generate steps if ICP/Offering changes") # Future idea

class CampaignResponseBase(BaseModel): # Base for common campaign response fields
    id: int
    organization_id: int
    name: str
    description: Optional[str] = None
    is_active: bool
    icp_id: Optional[int] = None
    icp_name: Optional[str] = None
    offering_id: Optional[int] = None # <<< ADDED
    offering_name: Optional[str] = None # <<< ADDED
    ai_status: Optional[str] = Field(None, examples=["pending", "generating", "completed", "failed"]) # <<< ADDED
    created_at: datetime
    updated_at: datetime

class CampaignResponse(CampaignResponseBase): # For POST response and GET /campaigns/ list items
    """Response model for a campaign definition."""
    class Config:
        from_attributes = True

class CampaignDetailResponse(CampaignResponseBase): # For GET /campaigns/{id}
    """Detailed response for a campaign, including its steps."""
    steps: List[CampaignStepResponse] = [] # Steps are included here

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

class BulkImportErrorDetail(BaseModel):
    row_number: Optional[int] = None # CSV row number (if identifiable)
    email: Optional[EmailStr] = None # Email of the problematic lead
    error: str                     # Description of the error

class BulkImportSummary(BaseModel):
    total_rows_in_file: int
    rows_attempted: int # Number of rows we tried to process (e.g., after skipping header)
    successfully_imported_or_updated: int
    failed_imports: int
    errors: List[BulkImportErrorDetail] = Field(default_factory=list)
