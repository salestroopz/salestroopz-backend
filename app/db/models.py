# app/db/models.py

from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, String, DateTime, Text,
    Float, func, UniqueConstraint, Enum as SQLAlchemyEnum # Keep SQLAlchemyEnum for potential future use
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

# Import Base from your central base_class.py
from .base_class import Base

# Import Enums from schemas.py (Single Source of Truth for Enums)
try:
    from app.schemas import LeadStatusEnum, AIClassificationEnum
except ImportError:
    # This allows the module to parse if schemas.py has an issue during early dev,
    # but operations using these enums will fail.
    # A more robust setup might raise an error here.
    print("Warning [models.py]: Could not import Enums from app.schemas. Model definitions using them might be incomplete.")
    LeadStatusEnum = None
    AIClassificationEnum = None


# --- Main Models ---

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    stripe_customer_id = Column(String, nullable=True, unique=True, index=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    
    # Relationships
    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    leads = relationship("Lead", back_populates="organization", cascade="all, delete-orphan")
    icps = relationship("ICP", back_populates="organization", cascade="all, delete-orphan")
    offerings = relationship("Offering", back_populates="organization", cascade="all, delete-orphan")
    email_campaigns = relationship("EmailCampaign", back_populates="organization", cascade="all, delete-orphan")
    email_settings = relationship("OrganizationEmailSettings", back_populates="organization", uselist=False, cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="organization", uselist=False, cascade="all, delete-orphan")

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


class ICP(Base):
    __tablename__ = "icps"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, default='Default ICP', nullable=False)
    
    title_keywords = Column(JSONB, nullable=True, default=lambda: []) # Use callable for mutable default
    industry_keywords = Column(JSONB, nullable=True, default=lambda: [])
    company_size_rules = Column(JSONB, nullable=True, default=lambda: {})
    location_keywords = Column(JSONB, nullable=True, default=lambda: [])

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="icps")
    leads_matched = relationship("Lead", back_populates="matched_icp")
    campaigns = relationship("EmailCampaign", back_populates="icp")


class Offering(Base):
    __tablename__ = "offerings"
    __table_args__ = (UniqueConstraint('organization_id', 'name', name='_org_offering_name_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    key_features = Column(JSONB, nullable=True, default=lambda: [])
    target_pain_points = Column(JSONB, nullable=True, default=lambda: [])
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
    name = Column(String, index=True, nullable=True)
    # first_name = Column(String, nullable=True) # Keep commented if 'name' is primary
    # last_name = Column(String, nullable=True)  # Keep commented if 'name' is primary
    company = Column(String, index=True, nullable=True)
    title = Column(String, nullable=True)
    source = Column(String, nullable=True)
    linkedin_profile = Column(String, nullable=True)
    company_size = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    location = Column(String, nullable=True)
    
    matched = Column(Boolean, default=False) # was is_icp_matched
    reason = Column(Text, nullable=True) # was icp_match_reason
    icp_match_id = Column(Integer, ForeignKey("icps.id", ondelete="SET NULL"), nullable=True, index=True)

    crm_status = Column(String, default='pending')
    appointment_confirmed = Column(Boolean, default=False)
    # appointment_details = Column(Text, nullable=True)
    # is_unsubscribed = Column(Boolean, default=False) # Usually per campaign or global email preference

    # custom_fields = Column(JSONB, nullable=True, default=lambda: {}) # If you had Text, consider JSONB

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="leads")
    matched_icp = relationship("ICP", back_populates="leads_matched")
    campaign_statuses = relationship("LeadCampaignStatus", back_populates="lead", cascade="all, delete-orphan")
    email_replies = relationship("EmailReply", back_populates="lead", cascade="all, delete-orphan")


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    icp_id = Column(Integer, ForeignKey("icps.id", ondelete="SET NULL"), nullable=True, index=True)
    offering_id = Column(Integer, ForeignKey("offerings.id", ondelete="SET NULL"), nullable=True, index=True)
    
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False, nullable=False)
    ai_status = Column(String, default='pending', nullable=False)
    # ai_error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="email_campaigns")
    icp = relationship("ICP", back_populates="campaigns")
    offering = relationship("Offering", back_populates="campaigns")
    steps = relationship("CampaignStep", back_populates="campaign", cascade="all, delete-orphan")
    lead_statuses = relationship("LeadCampaignStatus", back_populates="campaign", cascade="all, delete-orphan")


class CampaignStep(Base):
    __tablename__ = "campaign_steps"
    __table_args__ = (UniqueConstraint('campaign_id', 'step_number', name='_campaign_step_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    step_number = Column(Integer, nullable=False)
    delay_days = Column(Integer, default=1, nullable=False)
    subject_template = Column(Text, nullable=False)
    body_template = Column(Text, nullable=False)
    is_ai_crafted = Column(Boolean, default=False, nullable=False)
    follow_up_angle = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    campaign = relationship("EmailCampaign", back_populates="steps")


class LeadCampaignStatus(Base):
    __tablename__ = "lead_campaign_status"
    __table_args__ = (UniqueConstraint('lead_id', name='_lead_campaign_status_lead_uc'),)

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)

    current_step_number = Column(Integer, default=0, nullable=False)
    # Storing enum value as string, aligns with queries using .value
    status = Column(String(50), nullable=False, default=LeadStatusEnum.pending_enrollment.value if LeadStatusEnum else "pending_enrollment", index=True)

    last_email_sent_at = Column(DateTime(timezone=True), nullable=True)
    next_email_due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_response_type = Column(String(255), nullable=True) # Could be AIClassificationEnum.value
    last_response_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True) # Was status_reason in your model
    user_notes = Column(Text, nullable=True) # From your DDL
    # error_count = Column(Integer, default=0) # From your model, add if needed

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False) # Added this!
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    lead = relationship("Lead", back_populates="campaign_statuses")
    campaign = relationship("EmailCampaign", back_populates="lead_statuses")
    outgoing_email_logs = relationship("OutgoingEmailLog", back_populates="lead_campaign_status", cascade="all, delete-orphan")
    email_replies = relationship("EmailReply", back_populates="lead_campaign_status", cascade="all, delete-orphan")


class OrganizationEmailSettings(Base):
    __tablename__ = "organization_email_settings"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    provider_type = Column(String, nullable=True)
    verified_sender_email = Column(String, nullable=False)
    sender_name = Column(String, nullable=True)

    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_username = Column(String, nullable=True)
    encrypted_smtp_password = Column(Text, nullable=True)

    encrypted_api_key = Column(Text, nullable=True)
    encrypted_secret_key = Column(Text, nullable=True) # Ensure this column exists in DB
    encrypted_access_token = Column(Text, nullable=True)
    encrypted_refresh_token = Column(Text, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    aws_region = Column(String, nullable=True) # Ensure this column exists in DB

    is_configured = Column(Boolean, default=False, nullable=False)
    enable_reply_detection = Column(Boolean, default=False, nullable=False)
    imap_host = Column(String, nullable=True)
    imap_port = Column(Integer, default=993, nullable=True)
    imap_username = Column(String, nullable=True)
    encrypted_imap_password = Column(Text, nullable=True)
    imap_use_ssl = Column(Boolean, default=True, nullable=False)

    last_imap_poll_uid = Column(Text, nullable=True)
    last_imap_poll_timestamp = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="email_settings")


class OutgoingEmailLog(Base):
    __tablename__ = "outgoing_email_log"
    __table_args__ = (UniqueConstraint('organization_id', 'message_id_header', name='_org_oel_message_id_uc'),) # Renamed constraint

    id = Column(Integer, primary_key=True, index=True)
    lead_campaign_status_id = Column(Integer, ForeignKey("lead_campaign_status.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_step_id = Column(Integer, ForeignKey("campaign_steps.id", ondelete="SET NULL"), nullable=True, index=True)

    message_id_header = Column(String(512), nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False) # Use server_default
    to_email = Column(String(255), nullable=False)
    subject = Column(Text, nullable=True)
    # body_html = Column(Text, nullable=True) # Consider adding if you need to store sent content

    # created_at not needed if sent_at serves this purpose for logs
    # updated_at not typically needed for logs

    lead_campaign_status = relationship("LeadCampaignStatus", back_populates="outgoing_email_logs")
    email_replies = relationship("EmailReply", back_populates="outgoing_email_log", cascade="all, delete-orphan") # A sent email can have many replies


class EmailReply(Base):
    __tablename__ = "email_replies"

    id = Column(Integer, primary_key=True, index=True)
    # message_id_header from your old model might be the reply's own Message-ID. Let's assume it is.
    # If you need the Message-ID of the email being replied to, use in_reply_to_header.
    message_id_header_of_reply = Column(String(512), unique=True, index=True, nullable=True) # The Message-ID of this reply email

    outgoing_email_log_id = Column(Integer, ForeignKey("outgoing_email_log.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_campaign_status_id = Column(Integer, ForeignKey("lead_campaign_status.id", ondelete="CASCADE"), nullable=True, index=True)
    
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id", ondelete="CASCADE"), nullable=True, index=True)

    received_at = Column(DateTime(timezone=True), nullable=False, index=True)
    from_email = Column(String(255), nullable=False, index=True) # Added index
    reply_subject = Column(Text, nullable=True)
    raw_body_text = Column(Text, nullable=True)
    cleaned_reply_text = Column(Text, nullable=True)

    # Storing as string, ensure AIClassificationEnum is imported from schemas
    ai_classification = Column(String(100), nullable=True) # Store enum value
    ai_summary = Column(Text, nullable=True)
    ai_extracted_entities = Column(JSONB, nullable=True, default=lambda: {}) # Default to empty dict

    is_actioned_by_user = Column(Boolean, default=False, nullable=False)
    user_action_notes = Column(Text, nullable=True)
    # action_taken = Column(String, nullable=True) # From your model
    # action_timestamp = Column(DateTime(timezone=True), nullable=True) # From your model

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False) # If replies can be updated

    outgoing_email_log = relationship("OutgoingEmailLog", back_populates="email_replies")
    lead_campaign_status = relationship("LeadCampaignStatus", back_populates="email_replies")
    lead = relationship("Lead", back_populates="email_replies")

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    # Link subscription to an organization
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)

    stripe_subscription_id = Column(String, unique=True, index=True, nullable=False)
    stripe_customer_id = Column(String, index=True, nullable=False) # From the Organization's Stripe Customer
    stripe_price_id = Column(String, nullable=False) # The Stripe Price ID
    stripe_product_id = Column(String, nullable=True) # Optional: The Stripe Product ID

    status = Column(String(50), nullable=False) # e.g., "active", "trialing", "past_due", "canceled", "incomplete"
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    trial_end_at = Column(DateTime(timezone=True), nullable=True) # If you offer trials

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="subscription")
