# app/db/models.py

from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, String, DateTime, Text,
    Enum as SQLAlchemyEnum, Float, func, UniqueConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB # Specific to PostgreSQL for JSON

# Import Base from your central base_class.py
from .base_class import Base

# Import Enums from schemas.py (Single Source of Truth for Enums)
from app.schemas import LeadStatusEnum, AIClassificationEnum # Ensure these are defined in schemas.py

# --- Main Models ---

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="organization", cascade="all, delete-orphan")
    icps = relationship("ICP", back_populates="organization", cascade="all, delete-orphan")
    offerings = relationship("Offering", back_populates="organization", cascade="all, delete-orphan")
    email_campaigns = relationship("EmailCampaign", back_populates="organization", cascade="all, delete-orphan")
    email_settings = relationship("OrganizationEmailSettings", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    # outgoing_email_logs = relationship("OutgoingEmailLog", back_populates="organization", cascade="all, delete-orphan") # If needed
    # email_replies = relationship("EmailReply", back_populates="organization", cascade="all, delete-orphan") # If needed


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="users")


class ICP(Base): # Ideal Customer Profile
    __tablename__ = "icps"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, default='Default ICP', nullable=False) # Ensure name is not nullable
    
    title_keywords = Column(JSONB, nullable=True, default=list) # Store as JSON list
    industry_keywords = Column(JSONB, nullable=True, default=list)
    company_size_rules = Column(JSONB, nullable=True, default=dict) # Store as JSON dict
    location_keywords = Column(JSONB, nullable=True, default=list)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="icps")
    # Relationships to leads and campaigns
    leads_matched = relationship("Lead", back_populates="matched_icp") # Link to leads this ICP matched
    campaigns = relationship("EmailCampaign", back_populates="icp")   # Campaigns using this ICP


class Offering(Base):
    __tablename__ = "offerings"
    __table_args__ = (UniqueConstraint('organization_id', 'name', name='_org_offering_name_uc'),)


    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    key_features = Column(JSONB, nullable=True, default=list)
    target_pain_points = Column(JSONB, nullable=True, default=list)
    call_to_action = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="offerings")
    campaigns = relationship("EmailCampaign", back_populates="offering")


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (UniqueConstraint('organization_id', 'email', name='_org_lead_email_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String, index=True, nullable=False)
    name = Column(String, index=True, nullable=True) # Combined name
    # first_name = Column(String, nullable=True) # If you store separately
    # last_name = Column(String, nullable=True)  # If you store separately
    company = Column(String, index=True, nullable=True) # Aligned with your DDL
    title = Column(String, nullable=True)
    source = Column(String, nullable=True)
    linkedin_profile = Column(String, nullable=True)
    company_size = Column(String, nullable=True) # DDL had TEXT
    industry = Column(String, nullable=True) # DDL had TEXT
    location = Column(String, nullable=True) # DDL had TEXT
    
    matched = Column(Boolean, default=False) # DDL name for is_icp_matched
    reason = Column(Text, nullable=True) # DDL name for icp_match_reason
    icp_match_id = Column(Integer, ForeignKey("icps.id", ondelete="SET NULL"), nullable=True, index=True) # DDL name

    crm_status = Column(String, default='pending')
    appointment_confirmed = Column(Boolean, default=False)
    # appointment_details = Column(Text, nullable=True) # If you want to store details
    # is_unsubscribed = Column(Boolean, default=False) # Might be better on LeadCampaignStatus per campaign

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="leads")
    matched_icp = relationship("ICP", back_populates="leads_matched") # Matched ICP for this lead
    campaign_statuses = relationship("LeadCampaignStatus", back_populates="lead", cascade="all, delete-orphan")
    email_replies = relationship("EmailReply", back_populates="lead", cascade="all, delete-orphan")
    # outgoing_email_logs = relationship("OutgoingEmailLog", back_populates="lead", cascade="all, delete-orphan") # if needed


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    icp_id = Column(Integer, ForeignKey("icps.id", ondelete="SET NULL"), nullable=True, index=True)
    offering_id = Column(Integer, ForeignKey("offerings.id", ondelete="SET NULL"), nullable=True, index=True)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    ai_status = Column(String, default='pending', nullable=False) # e.g., pending, generating, completed
    # ai_error_message = Column(Text, nullable=True) # If you want to store AI errors

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="email_campaigns")
    icp = relationship("ICP", back_populates="campaigns")
    offering = relationship("Offering", back_populates="campaigns")
    steps = relationship("CampaignStep", back_populates="campaign", cascade="all, delete-orphan")
    lead_statuses = relationship("LeadCampaignStatus", back_populates="campaign", cascade="all, delete-orphan")
    # outgoing_email_logs = relationship("OutgoingEmailLog", back_populates="campaign", cascade="all, delete-orphan") # if needed
    # email_replies = relationship("EmailReply", back_populates="campaign", cascade="all, delete-orphan") # if needed


class CampaignStep(Base):
    __tablename__ = "campaign_steps"
    __table_args__ = (UniqueConstraint('campaign_id', 'step_number', name='_campaign_step_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    # Added organization_id to align with DDL and likely query needs
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    step_number = Column(Integer, nullable=False)
    delay_days = Column(Integer, default=1, nullable=False) # DDL had default 1
    subject_template = Column(Text, nullable=False) # DDL had TEXT
    body_template = Column(Text, nullable=False)    # DDL had TEXT
    is_ai_crafted = Column(Boolean, default=False, nullable=False) # DDL had default FALSE
    follow_up_angle = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    campaign = relationship("EmailCampaign", back_populates="steps")
    # outgoing_email_logs = relationship("OutgoingEmailLog", back_populates="campaign_step") # If specific step log is needed


class LeadCampaignStatus(Base):
    __tablename__ = "lead_campaign_status"
    __table_args__ = (UniqueConstraint('lead_id', name='_lead_campaign_status_lead_uc'),) # DDL had UNIQUE(lead_id)

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    current_step_number = Column(Integer, default=0, nullable=False)
    status = Column(String(50), nullable=False, default=LeadStatusEnum.pending_enrollment.value) # Storing enum value as string
    # If using native DB ENUM:
    # status = Column(SQLAlchemyEnum(LeadStatusEnum, name="lcs_status_enum", values_callable=lambda x: [e.value for e in x]),
    #                 default=LeadStatusEnum.pending_enrollment, nullable=False)

    last_email_sent_at = Column(DateTime(timezone=True), nullable=True)
    next_email_due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_response_type = Column(String(255), nullable=True) # Could be AIClassificationEnum.value
    last_response_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    user_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    lead = relationship("Lead", back_populates="campaign_statuses")
    campaign = relationship("EmailCampaign", back_populates="lead_statuses")
    outgoing_email_logs = relationship("OutgoingEmailLog", back_populates="lead_campaign_status")
    email_replies = relationship("EmailReply", back_populates="lead_campaign_status")


class OrganizationEmailSettings(Base):
    __tablename__ = "organization_email_settings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    provider_type = Column(String, nullable=True) # e.g., "SMTP", "AWS_SES"
    verified_sender_email = Column(String, nullable=False)
    sender_name = Column(String, nullable=True)

    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_username = Column(String, nullable=True)
    encrypted_smtp_password = Column(Text, nullable=True) # Text for potentially long encrypted strings

    encrypted_api_key = Column(Text, nullable=True)
    encrypted_secret_key = Column(Text, nullable=True) # Ensure this column exists in DB
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    aws_region = Column(String, nullable=True) # If provider_type is AWS_SES

    is_configured = Column(Boolean, default=False, nullable=False)
    enable_reply_detection = Column(Boolean, default=False, nullable=False)
    imap_host = Column(String, nullable=True)
    imap_port = Column(Integer, default=993, nullable=True)
    imap_username = Column(String, nullable=True)
    encrypted_imap_password = Column(Text, nullable=True)
    imap_use_ssl = Column(Boolean, default=True, nullable=False)

    last_imap_poll_uid = Column(Text, nullable=True) # Can be string or number, Text is safer
    last_imap_poll_timestamp = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="email_settings")


class OutgoingEmailLog(Base):
    __tablename__ = "outgoing_email_log"
    __table_args__ = (UniqueConstraint('organization_id', 'message_id_header', name='_org_message_id_uc'),)


    id = Column(Integer, primary_key=True, index=True)
    lead_campaign_status_id = Column(Integer, ForeignKey("lead_campaign_status.id", ondelete="SET NULL"), nullable=True, index=True) # Can be null if LCS deleted
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_step_id = Column(Integer, ForeignKey("campaign_steps.id", ondelete="SET NULL"), nullable=True, index=True) # Can be null if step deleted

    message_id_header = Column(String(512), nullable=False, index=True) # DDL had VARCHAR(512)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    to_email = Column(String(255), nullable=False) # DDL had VARCHAR(255)
    subject = Column(Text, nullable=True) # DDL had TEXT
    # body_html = Column(Text, nullable=True) # If you store the sent body here

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False) # Redundant with sent_at but good for record creation
    # No updated_at typically for logs unless you modify them post-creation

    # Relationships
    lead_campaign_status = relationship("LeadCampaignStatus", back_populates="outgoing_email_logs")
    # organization = relationship("Organization", back_populates="outgoing_email_logs") # Add to Organization if needed
    # lead = relationship("Lead", back_populates="outgoing_email_logs") # Add to Lead if needed
    # campaign = relationship("EmailCampaign", back_populates="outgoing_email_logs") # Add to EmailCampaign if needed
    # campaign_step = relationship("CampaignStep", back_populates="outgoing_email_logs") # Add to CampaignStep if needed
    email_replies = relationship("EmailReply", back_populates="outgoing_email_log") # Replies to this sent email


class EmailReply(Base):
    __tablename__ = "email_replies"

    id = Column(Integer, primary_key=True, index=True)
    outgoing_email_log_id = Column(Integer, ForeignKey("outgoing_email_log.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_campaign_status_id = Column(Integer, ForeignKey("lead_campaign_status.id", ondelete="CASCADE"), nullable=True, index=True) # Can be nullable if not directly tied to a campaign status
    
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True) # Reply must be from a known lead
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=True, index=True) # Optional: campaign context

    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    from_email = Column(String(255), nullable=False) # DDL had VARCHAR(255)
    reply_subject = Column(Text, nullable=True)
    raw_body_text = Column(Text, nullable=True)
    cleaned_reply_text = Column(Text, nullable=True)

    # ai_classification = Column(SQLAlchemyEnum(AIClassificationEnum, name="ai_class_enum", values_callable=lambda x: [e.value for e in x]), nullable=True)
    ai_classification = Column(String(100), nullable=True) # Storing as string for simplicity
    ai_summary = Column(Text, nullable=True)
    ai_extracted_entities = Column(JSONB, nullable=True) # Store as JSON

    is_actioned_by_user = Column(Boolean, default=False, nullable=False)
    user_action_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    # No updated_at typically for replies unless they are modified

    # Relationships
    outgoing_email_log = relationship("OutgoingEmailLog", back_populates="email_replies")
    lead_campaign_status = relationship("LeadCampaignStatus", back_populates="email_replies")
    lead = relationship("Lead", back_populates="email_replies")
    # organization = relationship("Organization", back_populates="email_replies") # Add to Organization if needed
    # campaign = relationship("EmailCampaign", back_populates="email_replies") # Add to EmailCampaign if needed
