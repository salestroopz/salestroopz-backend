# app/schemas.py

from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from datetime import datetime
from app.db.models import LeadStatusEnum
import enum 

# --- Authentication & User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    # Consider adding is_active, is_superuser if you have roles/status directly on user model

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8)
    organization_name: str
    full_name: Optional[str] = None # Add full_name, make it optional for now

class UserPublic(UserBase): # For API responses representing a user
    id: int
    organization_id: int
    organization_name: str # Good to include for context
    # is_active: bool # If you have this on your User DB model

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[EmailStr] = None # Changed to EmailStr from str
    # sub: Optional[str] = None # Often 'sub' (subject) is used for user ID/email in JWT

# --- Lead Schemas ---
class LeadBase(BaseModel):
    name: Optional[str] = Field(None, examples=["Jane Doe"])
    email: EmailStr = Field(..., examples=["jane.doe@example.com"])
    company: Optional[str] = Field(None, examples=["Acme Corp"])
    title: Optional[str] = Field(None, examples=["Marketing Manager"])
    source: Optional[str] = Field("API Input", examples=["Manual Entry", "CSV Upload"])
    linkedin_profile: Optional[str] = Field(None, examples=["https://linkedin.com/in/janedoe"])
    company_size: Optional[str] = Field(None, examples=["51-200"])
    industry: Optional[str] = Field(None, examples=["SaaS"])
    location: Optional[str] = Field(None, examples=["New York, USA"])
    matched: bool = Field(False) # Default to False, ensure boolean
    reason: Optional[str] = Field(None, description="Reason for ICP match/no match")
    crm_status: Optional[str] = Field("pending", description="Status in CRM")
    appointment_confirmed: bool = Field(False) # Default to False
    icp_match_id: Optional[int] = Field(None, description="ID of the ICP this lead matched, if any") # NEW

class LeadInput(LeadBase):
    """Schema for creating a new lead."""
    pass

class LeadUpdatePartial(BaseModel): # For PATCH requests - explicitly list updatable fields
    """Schema for partially updating a lead. All fields are optional."""
    name: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    linkedin_profile: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None
    matched: Optional[bool] = None
    reason: Optional[str] = None
    crm_status: Optional[str] = None
    appointment_confirmed: Optional[bool] = None
    icp_match_id: Optional[int] = Field(None, description="Update matched ICP ID, use null to unset")

class LeadResponse(LeadBase):
    """Schema for returning lead data from the API."""
    id: int
    organization_id: int
    icp_match_name: Optional[str] = None # Name of the matched ICP (from JOIN)
    created_at: datetime
    updated_at: datetime # Should always be present after DB schema change

    class Config:
        from_attributes = True

# --- ICP (Ideal Customer Profile) Schemas ---
class ICPBase(BaseModel):
    name: str = Field(..., min_length=1, description="A name for this ICP definition", examples=["Tech Startup ICP"])
    title_keywords: List[str] = Field(default_factory=list, description="List of target job titles/keywords", examples=[["VP Engineering", "CTO"]])
    industry_keywords: List[str] = Field(default_factory=list, description="List of target industries/keywords", examples=[["SaaS", "Cloud Computing"]])
    company_size_rules: Optional[Dict[str, Any]] = Field(default_factory=dict, description='Rules for company size (e.g., {"min": 50, "max": 500})', examples=[{"min": 51, "max": 200}]) # Made optional, can be empty dict
    location_keywords: List[str] = Field(default_factory=list, description="List of target locations/keywords", examples=[["London", "Remote"]])

class ICPInput(ICPBase):
    """Schema for creating/updating an ICP via the API."""
    pass

class ICPResponse(ICPBase):
    """Schema for returning an ICP definition from the API."""
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Offering Schemas ---
class OfferingBase(BaseModel):
    name: str = Field(..., min_length=1, examples=["Cloud Migration Assessment"])
    description: Optional[str] = Field(None, examples=["Detailed analysis..."])
    key_features: List[str] = Field(default_factory=list, examples=[["Cost Projection"]])
    target_pain_points: List[str] = Field(default_factory=list, examples=[["High AWS Bills"]])
    call_to_action: Optional[str] = Field(None, examples=["Schedule a 15-min call"])
    is_active: bool = Field(True)

class OfferingInput(OfferingBase):
    """Schema for creating/updating an Offering via API."""
    pass

class OfferingResponse(OfferingBase):
    """Schema for returning an Offering definition from the API."""
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Email Settings Schemas ---
class EmailProviderType(str, Enum):
    SMTP = "smtp"
    AWS_SES = "aws_ses"

class EmailSettingsBase(BaseModel):
    provider_type: Optional[EmailProviderType] = None
    verified_sender_email: Optional[EmailStr] = None
    sender_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    aws_region: Optional[str] = None
    is_configured: bool = Field(False) # Changed Optional[bool] to bool with default

class EmailSettingsInput(EmailSettingsBase):
    smtp_password: Optional[str] = Field(None, description="Write-only")
    aws_access_key_id: Optional[str] = Field(None, description="Write-only")
    aws_secret_access_key: Optional[str] = Field(None, description="Write-only")

class EmailSettingsResponse(EmailSettingsBase):
    id: int
    organization_id: int
    credentials_set: bool = Field(False, description="Indicates if essential credentials seem to be set") # Keep this for UI hint
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Campaign Step Schemas ---
class CampaignStepBase(BaseModel):
    step_number: int = Field(..., gt=0, description="Order of the step (1, 2, ...)")
    delay_days: int = Field(..., ge=0, description="Days to wait after previous step/enrollment")
    subject_template: str = Field(..., description="Subject line template (use {{placeholders}})") # Made required
    body_template: str = Field(..., description="Email body template (use {{placeholders}})")   # Made required
    follow_up_angle: Optional[str] = Field(None, description="Angle of the step, e.g., 'Introduction', 'Value Prop'")

class CampaignStepInput(CampaignStepBase): # Used by AI agent when creating steps
    """Schema for the AI agent to provide step data to the database layer."""
    # is_ai_crafted will be set to True by the agent logic directly when calling db.create_campaign_step
    pass

class CampaignStepUpdate(BaseModel): # NEW - For updating existing steps via API
    """Schema for updating an existing campaign step. All fields optional."""
    step_number: Optional[int] = Field(None, gt=0)
    delay_days: Optional[int] = Field(None, ge=0)
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    follow_up_angle: Optional[str] = None
    # is_ai_crafted could be set to False by the API if a user edits it

class CampaignStepResponse(CampaignStepBase):
    """Response model for a campaign step, includes DB ID."""
    id: int
    campaign_id: int
    organization_id: int
    is_ai_crafted: bool # This comes from the DB
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# --- Campaign Schemas ---
class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1, examples=["Q3 Fintech Outreach"])
    description: Optional[str] = Field(None, examples=["Campaign targeting Fintech CTOs..."])
    is_active: bool = Field(False)
    icp_id: Optional[int] = None
    offering_id: Optional[int] = None

class CampaignInput(CampaignBase): # For POST /campaigns/ (AI generates steps)
    """Input for creating a campaign definition. Steps are AI-generated."""
    pass

class CampaignUpdate(CampaignBase): # For PUT /campaigns/{id}
    """Schema for updating an existing campaign's core details."""
    # All fields are optional because it inherits from CampaignBase where fields might be required for creation
    # Pydantic handles this by making inherited fields optional if not re-declared with ...
    name: Optional[str] = Field(None, min_length=1) # Explicitly make optional for update
    is_active: Optional[bool] = None # Explicitly make optional
    # trigger_ai_regeneration: bool = Field(False) # Future idea

class CampaignResponse(CampaignBase):
    """Standard response model for a campaign."""
    id: int
    organization_id: int
    icp_name: Optional[str] = None # Populated from DB JOIN
    offering_name: Optional[str] = None # Populated from DB JOIN
    ai_status: Optional[str] = Field(None, examples=["pending", "generating", "completed", "failed"])
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CampaignDetailResponse(CampaignResponse): # Inherits all fields from CampaignResponse
    """Detailed response for a campaign, including its steps."""
    steps: List[CampaignStepResponse] = Field(default_factory=list)

    class Config: # Redundant if inherited, but harmless
        from_attributes = True


# --- Lead Enrollment Schemas ---
class CampaignEnrollLeadsRequest(BaseModel):
    lead_ids: List[int] = Field(..., min_items=1, description="A list of lead IDs to enroll into the campaign.")

# --- Lead Campaign Status Schema ---
class LeadCampaignStatusResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: int
    organization_id: int
    current_step_number: int
    status: str # Consider an Enum for this: 'active', 'paused', 'completed_sequence', etc.
    last_email_sent_at: Optional[datetime] = None
    next_email_due_at: Optional[datetime] = None
    last_response_type: Optional[str] = None # E.g., 'positive', 'negative', 'neutral'
    last_response_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- Misc Schemas (Keep if used) ---
class ManualLeadData(BaseModel): # If still used for some manual entry flow
    name: Optional[str] = None
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None

class LeadEnrichmentRequest(BaseModel): # If lead enrichment agent uses it
    name: str
    company: str # Assuming company name is used for enrichment
    title: Optional[str] = None
    email: Optional[EmailStr] = None

class LeadEnrichmentResponse(BaseModel): # If lead enrichment agent uses it
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[EmailStr] = None
    linkedin_profile: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None

class WorkflowInitiateRequest(BaseModel): # If used by a workflow endpoint
    # Forward declaration for ICPDefinitionForWorkflow if defined below, or use ICPInput
    # icp: 'ICPDefinitionForWorkflow' # Assuming this refers to a specific structure for workflow
    icp: ICPInput # Or reuse the main ICPInput if suitable
    source_type: Literal["file_upload", "apollo", "crm", "manual_entry"]
    source_details: Optional[Dict[str, Any]] = None # Keep as is

# class ICPDefinition(BaseModel): # This was a duplicate of ICPInput or similar
# This can be removed if ICPInput serves the purpose for WorkflowInitiateRequest

class BulkImportErrorDetail(BaseModel):
    row_number: Optional[int] = None
    email: Optional[EmailStr] = None
    error: str

class BulkImportSummary(BaseModel):
    total_rows_in_file: int
    rows_attempted: int
    successfully_imported_or_updated: int
    failed_imports: int
    errors: List[BulkImportErrorDetail] = Field(default_factory=list)

class LeadCampaignStatusResponse(BaseModel):
    # ... (core lcs fields) ...
    lead_name: Optional[str] = None
    lead_email: Optional[EmailStr] = None
    lead_company: Optional[str] = None
    campaign_name: Optional[str] = None
    # Fields from the latest email_reply JOIN
    latest_reply_id: Optional[int] = None
    latest_reply_snippet: Optional[str] = None
    latest_reply_ai_summary: Optional[str] = None
    latest_reply_ai_classification: Optional[str] = None
    latest_reply_received_at: Optional[datetime] = None # Added from the email_replies table

# --- DEFINE LeadStatusEnum HERE ---
class LeadStatusEnum(str, enum.Enum):
    pending_enrollment = "pending_enrollment"
    enrolled_active = "enrolled_active"
    sequence_step_1_sent = "sequence_step_1_sent"
    # ... other steps
    positive_reply_ai_flagged = "positive_reply_ai_flagged"
    positive_reply_received = "positive_reply_received" # Manually confirmed
    appointment_manually_set = "appointment_manually_set"
    needs_manual_followup = "needs_manual_followup"
    unsubscribed = "unsubscribed"
    sequence_completed = "sequence_completed"
    error_sending = "error_sending"

# --- ADD/ENSURE THESE DASHBOARD RESPONSE MODELS ARE DEFINED ---

class AppointmentStatsResponse(BaseModel):
    """
    Pydantic model for the response of the /dashboard/appointment_stats endpoint.
    """
    total_appointments_set: int
    total_positive_replies: int
    conversion_rate_percent: Optional[float] = None # Can be None if positive_replies is 0

    class Config:
        from_attributes = True # For Pydantic v2+ (replaces orm_mode)


class RecentAppointment(BaseModel):
    """
    Pydantic model for a single item in the recent appointments list.
    """
    lead_name: str
    company_name: Optional[str] = None
    campaign_name: str
    date_marked: str # Or datetime if you prefer to format on frontend

    class Config:
        from_attributes = True


class ActionableReply(BaseModel): # Assuming you have a schema for actionable replies
    reply_id: int
    lead_id: int
    lead_name: str
    lead_email: EmailStr
    lead_company: Optional[str] = None
    campaign_id: int
    campaign_name: str
    latest_reply_received_at: Optional[datetime] = None # Or received_at
    latest_reply_ai_classification: Optional[str] = None # Or use your AIClassificationEnum
    latest_reply_ai_summary: Optional[str] = None
    latest_reply_snippet: Optional[str] = None
    # Add full_reply_body if you pass it from backend
    # full_reply_body: Optional[str] = None

    class Config:
        from_attributes = True


class CampaignPerformanceSummaryItem(BaseModel): # For campaign performance snippets
    campaign_id: int
    campaign_name: str
    leads_enrolled: int
    emails_sent: Optional[int] = None # This might be tricky to get accurately without specific logging
    positive_replies: int
    appointments_set: int
    # conversion_rate: Optional[float] = None # (appointments / positive_replies)

    
class Config:
    from_attributes = True
    successfully_imported_or_updated: int
    failed_imports: int
    errors: List[BulkImportErrorDetail] = Field(default_factory=list)
