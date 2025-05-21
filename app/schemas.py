# app/schemas.py

from pydantic import BaseModel, Field, EmailStr, constr
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
from datetime import datetime

# --- DEFINE LeadStatusEnum HERE ---
# This should be the single source of truth for these status strings.
class LeadStatusEnum(str, Enum):
    active = "active"  # For leads actively in a campaign sequence
    pending_enrollment = "pending_enrollment"
    paused_by_user = "paused_by_user"
    paused_due_to_reply = "paused_due_to_reply"
    completed_sequence = "completed_sequence"
    unsubscribed = "unsubscribed"
    unsubscribed_ai_flagged = "unsubscribed_ai_flagged"

    # Reply related statuses
    positive_reply_ai_flagged = "positive_reply_ai_flagged"
    positive_reply_received = "positive_reply_received"
    question_ai_flagged = "question_ai_flagged"
    negative_reply_ai_flagged = "negative_reply_ai_flagged"
    manual_follow_up_needed = "manual_follow_up_needed"

    # State/Action statuses
    appointment_manually_set = "appointment_manually_set"

    # Error statuses
    error_sending_email = "error_sending_email"
    error_lead_not_found = "error_lead_not_found"
    error_email_config = "error_email_config"
    error_template_missing = "error_template_missing"
    error_unknown = "error_unknown"

# --- Authentication & User Schemas ---
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    is_active: Optional[bool] = Field(default=True) # Default to active

class UserCreate(UserBase):
    password: constr(min_length=8)
    organization_name: str

class UserPublic(UserBase):
    id: int
    organization_id: int
    is_active: bool # From DB
    is_superuser: bool # From DB
    # organization_name: Optional[str] = None # Optional: Add if you join/resolve this in the API response

    model_config = {"from_attributes": True}

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    sub: Optional[EmailStr] = None # Subject (user's email)
    user_id: Optional[int] = None
    organization_id: Optional[int] = None

# --- Lead Schemas ---
class LeadBase(BaseModel):
    name: Optional[str] = Field(default=None, examples=["Jane Doe"])
    email: EmailStr = Field(..., examples=["jane.doe@example.com"]) # '...' means required
    company: Optional[str] = Field(default=None, examples=["Acme Corp"])
    title: Optional[str] = Field(default=None, examples=["Marketing Manager"])
    source: Optional[str] = Field(default="API Input", examples=["Manual Entry", "CSV Upload"])
    linkedin_profile: Optional[str] = Field(default=None, examples=["https://linkedin.com/in/janedoe"])
    company_size: Optional[str] = Field(default=None, examples=["51-200"])
    industry: Optional[str] = Field(default=None, examples=["SaaS"])
    location: Optional[str] = Field(default=None, examples=["New York, USA"])
    matched: bool = Field(default=False)
    reason: Optional[str] = Field(default=None, description="Reason for ICP match/no match")
    crm_status: Optional[str] = Field(default="pending", description="Status in CRM")
    appointment_confirmed: bool = Field(default=False)
    icp_match_id: Optional[int] = Field(default=None, description="ID of the ICP this lead matched, if any")

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
    icp_match_id: Optional[int] = Field(default=None, description="Update matched ICP ID, use null to unset")

class LeadResponse(LeadBase):
    id: int
    organization_id: int
    icp_match_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# --- ICP (Ideal Customer Profile) Schemas ---
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
    description: Optional[str] = Field(default=None)
    key_features: List[str] = Field(default_factory=list)
    target_pain_points: List[str] = Field(default_factory=list)
    call_to_action: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)

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
    # GOOGLE_OAUTH = "google_oauth"

class EmailSettingsBase(BaseModel):
    provider_type: Optional[EmailProviderType] = None
    verified_sender_email: Optional[EmailStr] = None
    sender_name: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None # Port for SMTP
    aws_region: Optional[str] = None
    is_configured: bool = Field(default=False)

    # IMAP settings for reply detection
    enable_reply_detection: bool = Field(default=False)
    imap_host: Optional[str] = None
    imap_port: Optional[int] = Field(default=993, description="IMAP port, defaults to 993 for SSL") # Corrected: Only one definition
    imap_username: Optional[str] = None
    imap_use_ssl: bool = Field(default=True)

class EmailSettingsInput(EmailSettingsBase):
    smtp_password: Optional[str] = Field(default=None, description="Write-only, will be encrypted")
    aws_access_key_id: Optional[str] = Field(default=None, description="Write-only")
    aws_secret_access_key: Optional[str] = Field(default=None, description="Write-only")
    imap_password: Optional[str] = Field(default=None, description="Write-only, will be encrypted")

class EmailSettingsResponse(EmailSettingsBase):
    id: int
    organization_id: int
    # credentials_set: bool = Field(default=False) # Derived in API or model if needed
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

# --- Campaign Step Schemas ---
class CampaignStepBase(BaseModel):
    step_number: int = Field(..., gt=0)
    delay_days: int = Field(..., ge=0)
    subject_template: str = Field(...)
    body_template: str = Field(...)
    follow_up_angle: Optional[str] = Field(default=None)

class CampaignStepInput(CampaignStepBase):
    pass

class CampaignStepUpdate(BaseModel):
    step_number: Optional[int] = Field(default=None, gt=0)
    delay_days: Optional[int] = Field(default=None, ge=0)
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
    description: Optional[str] = Field(default=None)
    is_active: bool = Field(default=False)
    icp_id: Optional[int] = None
    offering_id: Optional[int] = None

class CampaignInput(CampaignBase):
    pass

class CampaignUpdate(BaseModel): # Explicitly optional for PATCH
    name: Optional[str] = Field(default=None, min_length=1)
    description: Optional[str] = Field(default=None)
    is_active: Optional[bool] = None
    icp_id: Optional[int] = None
    offering_id: Optional[int] = None

class CampaignResponse(CampaignBase):
    id: int
    organization_id: int
    icp_name: Optional[str] = None
    offering_name: Optional[str] = None
    ai_status: Optional[str] = Field(default=None)
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class CampaignDetailResponse(CampaignResponse):
    steps: List[CampaignStepResponse] = Field(default_factory=list)
    model_config = {"from_attributes": True}

# --- Lead Enrollment Schemas ---
class CampaignEnrollLeadsRequest(BaseModel):
    lead_ids: List[int] = Field(..., min_items=1)

# --- Lead Campaign Status Schema (Consolidated) ---
class LeadCampaignStatusResponse(BaseModel):
    id: int
    lead_id: int
    campaign_id: int
    organization_id: int
    current_step_number: int
    status: LeadStatusEnum
    last_email_sent_at: Optional[datetime] = None
    next_email_due_at: Optional[datetime] = None
    last_response_type: Optional[str] = None
    last_response_at: Optional[datetime] = None
    error_message: Optional[str] = None
    user_notes: Optional[str] = None

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
    total_positive_replies: int
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
    campaign_id: int
    campaign_name: str
    latest_reply_received_at: Optional[datetime] = None
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
    model_config = {"from_attributes": True}

class AIClassificationEnum(str, Enum): # <--- DEFINE IT HERE
    positive_interest = "positive_interest"
    question = "question"
    objection = "objection"
    unsubscribe_request = "unsubscribe_request"
    out_of_office = "out_of_office"
    negative_reply = "negative_reply"
    not_applicable = "not_applicable"
    empty_reply = "empty_reply" # If you use this
    classification_failed = "classification_failed" # If you use this

class CreateSubscriptionRequest(BaseModel):
    payment_method_id: str
    price_id: str # Stripe Price ID (e.g., price_xxxxxxxxxxxx)

class CreateSubscriptionResponse(BaseModel):
    subscription_id: str
    status: str
    client_secret: Optional[str] = None # For SCA
    # Add other relevant fields you want to return
