# app/schemas.py

from pydantic import BaseModel, Field, EmailStr, constr
from typing import Optional, List, Dict, Any, Literal # Literal was used
from enum import Enum
from datetime import datetime

# --- DEFINE LeadStatusEnum HERE ---
# This should be the single source of truth for these status strings.
class LeadStatusEnum(str, Enum):
    active = "active"  # For leads actively in a campaign sequence
    pending_enrollment = "pending_enrollment"
    # enrolled_active = "enrolled_active" # 'active' should cover this
    paused_by_user = "paused_by_user"
    paused_due_to_reply = "paused_due_to_reply"
    completed_sequence = "completed_sequence" # Renamed from sequence_completed for consistency
    unsubscribed = "unsubscribed"
    unsubscribed_ai_flagged = "unsubscribed_ai_flagged"

    # Reply related statuses
    positive_reply_ai_flagged = "positive_reply_ai_flagged"
    positive_reply_received = "positive_reply_received"
    question_ai_flagged = "question_ai_flagged"
    negative_reply_ai_flagged = "negative_reply_ai_flagged"
    manual_follow_up_needed = "manual_follow_up_needed" # Renamed from needs_manual_followup

    # State/Action statuses
    appointment_manually_set = "appointment_manually_set"

    # Error statuses
    error_sending_email = "error_sending_email" # Renamed from error_sending
    error_lead_not_found = "error_lead_not_found"
    error_email_config = "error_email_config"
    error_template_missing = "error_template_missing"
    error_unknown = "error_unknown" # General error

    # Example sequence steps (if you use them, otherwise 'active' is enough during sequence)
    # sequence_step_1_sent = "sequence_step_1_sent" # Generally, just update current_step_number

# --- Authentication & User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None # Added based on your model changes
    is_active: Optional[bool] = True # If you track this

class UserCreate(UserBase): # Inherits email, full_name, is_active from UserBase
    password: constr(min_length=8)
    organization_name: str

class UserPublic(UserBase):
    id: int
    organization_id: int
    # organization_name: str # This would require a JOIN or hybrid property on User model if using from_orm directly
    # For simplicity, let's assume User ORM object doesn't directly have organization_name when fetched by get_user_by_email
    # If you need it, your /register route can construct it or User model can have a property.
    is_active: bool # Assuming this comes from DB
    is_superuser: bool # Assuming this comes from DB

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    # 'sub' (subject) is typically used for the user identifier (e.g., email or ID)
    sub: Optional[EmailStr] = None # Standard claim for subject
    user_id: Optional[int] = None
    organization_id: Optional[int] = None


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
    matched: bool = Field(False)
    reason: Optional[str] = Field(None, description="Reason for ICP match/no match")
    crm_status: Optional[str] = Field("pending", description="Status in CRM")
    appointment_confirmed: bool = Field(False)
    icp_match_id: Optional[int] = Field(None, description="ID of the ICP this lead matched, if any")

class LeadInput(LeadBase):
    pass

class LeadUpdatePartial(BaseModel):
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
    id: int
    organization_id: int
    icp_match_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# --- ICP Schemas ---
class ICPBase(BaseModel):
    name: str = Field(..., min_length=1, description="A name for this ICP definition", examples=["Tech Startup ICP"])
    title_keywords: List[str] = Field(default_factory=list)
    industry_keywords: List[str] = Field(default_factory=list)
    company_size_rules: Optional[Dict[str, Any]] = Field(default_factory=dict)
    location_keywords: List[str] = Field(default_factory=list)

class ICPInput(ICPBase):
    pass

class ICPResponse(ICPBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# --- Offering Schemas ---
class OfferingBase(BaseModel):
    name: str = Field(..., min_length=1, examples=["Cloud Migration Assessment"])
    description: Optional[str] = Field(None)
    key_features: List[str] = Field(default_factory=list)
    target_pain_points: List[str] = Field(default_factory=list)
    call_to_action: Optional[str] = Field(None)
    is_active: bool = Field(True)

class OfferingInput(OfferingBase):
    pass

class OfferingResponse(OfferingBase):
    id: int
    organization_id: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# --- Email Settings Schemas ---
class EmailProviderType(str, Enum):
    SMTP = "smtp"
    AWS_SES = "aws_ses"
    # GOOGLE_OAUTH = "google_oauth" # Example for future

class EmailSettingsBase(BaseModel):
    provider_type: Optional[EmailProviderType] = None
    verified_sender_email: Optional[EmailStr] = None
    sender_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_username: Optional[str] = None
    aws_region: Optional[str] = None # Specific to AWS SES
    is_configured: bool = Field(False)
    
    # IMAP settings for reply detection
    imap_port: Optional[int] = Field(993, description="IMAP port, defaults to 993 for SSL")
    enable_reply_detection: bool = Field(False)
    imap_host: Optional[str] = None
    imap_port: Optional[int] = Field(None, default=993) # Default common SSL port
    imap_username: Optional[str] = None
    imap_use_ssl: bool = Field(True)


class EmailSettingsInput(EmailSettingsBase): # Fields for creating/updating settings
    smtp_password: Optional[str] = Field(None, description="Write-only, will be encrypted")
    # For AWS SES using API keys
    aws_access_key_id: Optional[str] = Field(None, description="Write-only")
    aws_secret_access_key: Optional[str] = Field(None, description="Write-only")
    # For Google OAuth
    # access_token: Optional[str] = Field(None, description="Write-only, from OAuth flow")
    # refresh_token: Optional[str] = Field(None, description="Write-only, from OAuth flow")
    # token_expiry: Optional[datetime] = Field(None, description="Write-only, from OAuth flow")
    # IMAP
    imap_password: Optional[str] = Field(None, description="Write-only, will be encrypted")


class EmailSettingsResponse(EmailSettingsBase): # Fields returned from API (no raw passwords)
    id: int
    organization_id: int
    # credentials_set: bool = Field(False, description="Indicates if essential credentials seem to be set") # You can derive this
    # last_imap_poll_uid: Optional[str] = None # If you want to expose this
    # last_imap_poll_timestamp: Optional[datetime] = None # If you want to expose this
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Campaign Step Schemas ---
class CampaignStepBase(BaseModel):
    step_number: int = Field(..., gt=0)
    delay_days: int = Field(..., ge=0)
    subject_template: str = Field(...)
    body_template: str = Field(...)
    follow_up_angle: Optional[str] = Field(None)

class CampaignStepInput(CampaignStepBase):
    pass

class CampaignStepUpdate(BaseModel):
    step_number: Optional[int] = Field(None, gt=0)
    delay_days: Optional[int] = Field(None, ge=0)
    subject_template: Optional[str] = None
    body_template: Optional[str] = None
    follow_up_angle: Optional[str] = None

class CampaignStepResponse(CampaignStepBase):
    id: int
    campaign_id: int
    organization_id: int
    is_ai_crafted: bool
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# --- Campaign Schemas ---
class CampaignBase(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = Field(None)
    is_active: bool = Field(False) # Default to False, activate explicitly
    icp_id: Optional[int] = None
    offering_id: Optional[int] = None

class CampaignInput(CampaignBase):
    pass

class CampaignUpdate(BaseModel): # Explicitly make all fields optional for PATCH-like behavior
    name: Optional[str] = Field(None, min_length=1)
    description: Optional[str] = Field(None)
    is_active: Optional[bool] = None
    icp_id: Optional[int] = None # Allow null to unset
    offering_id: Optional[int] = None # Allow null to unset
    # ai_status: Optional[str] = None # If updating AI status is allowed here

class CampaignResponse(CampaignBase):
    id: int
    organization_id: int
    icp_name: Optional[str] = None
    offering_name: Optional[str] = None
    ai_status: Optional[str] = Field(None)
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class CampaignDetailResponse(CampaignResponse):
    steps: List[CampaignStepResponse] = Field(default_factory=list)
    model_config = {"from_attributes": True}

# --- Lead Enrollment Schemas ---
class CampaignEnrollLeadsRequest(BaseModel):
    lead_ids: List[int] = Field(..., min_items=1)

# --- Lead Campaign Status Schema (Consolidated and Enhanced) ---
class LeadCampaignStatusResponse(BaseModel): # REMOVED the first duplicate
    id: int
    lead_id: int
    campaign_id: int
    organization_id: int
    current_step_number: int
    status: LeadStatusEnum # Use the Enum for type safety and clarity
    last_email_sent_at: Optional[datetime] = None
    next_email_due_at: Optional[datetime] = None
    last_response_type: Optional[str] = None
    last_response_at: Optional[datetime] = None
    error_message: Optional[str] = None
    user_notes: Optional[str] = None # Added from your DDL

    # Joined fields for richer responses (e.g., for dashboards)
    lead_name: Optional[str] = None
    lead_email: Optional[EmailStr] = None
    lead_company: Optional[str] = None
    campaign_name: Optional[str] = None
    latest_reply_id: Optional[int] = None
    latest_reply_snippet: Optional[str] = None
    latest_reply_ai_summary: Optional[str] = None
    latest_reply_ai_classification: Optional[str] = None
    latest_reply_received_at: Optional[datetime] = None

    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# --- Misc Schemas ---
class ManualLeadData(BaseModel):
    name: Optional[str] = None
    email: EmailStr
    company: Optional[str] = None
    title: Optional[str] = None

class LeadEnrichmentRequest(BaseModel):
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[EmailStr] = None

class LeadEnrichmentResponse(BaseModel):
    name: str
    company: str
    title: Optional[str] = None
    email: Optional[EmailStr] = None
    linkedin_profile: Optional[str] = None
    company_size: Optional[str] = None
    industry: Optional[str] = None
    location: Optional[str] = None

class WorkflowInitiateRequest(BaseModel):
    icp: ICPInput
    source_type: Literal["file_upload", "apollo", "crm", "manual_entry"]
    source_details: Optional[Dict[str, Any]] = None

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

# --- DASHBOARD RESPONSE MODELS ---
class AppointmentStatsResponse(BaseModel):
    total_appointments_set: int
    total_positive_replies: int # Or a more specific name like "leads_with_positive_engagement"
    conversion_rate_percent: Optional[float] = None
    model_config = {"from_attributes": True}

class RecentAppointment(BaseModel):
    lead_name: str
    company_name: Optional[str] = None
    campaign_name: str
    date_marked: str # Or datetime
    model_config = {"from_attributes": True}

class ActionableReply(BaseModel):
    reply_id: int
    lead_id: int
    lead_name: str
    lead_email: EmailStr
    lead_company: Optional[str] = None
    campaign_id: int # Assuming campaign_id is available for the reply context
    campaign_name: str
    latest_reply_received_at: Optional[datetime] = None # Use this for consistency if it's the reply's received time
    latest_reply_ai_classification: Optional[str] = None
    latest_reply_ai_summary: Optional[str] = None
    latest_reply_snippet: Optional[str] = None
    model_config = {"from_attributes": True}

class CampaignPerformanceSummaryItem(BaseModel):
    campaign_id: int
    campaign_name: str
    leads_enrolled: int
    emails_sent: Optional[int] = None
    positive_replies: int
    appointments_set: int
    # model_config should be inside the class, not outside
    model_config = {"from_attributes": True}

# Removed the stray Config class that was outside CampaignPerformanceSummaryItem
