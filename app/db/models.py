# app/db/models.py

from sqlalchemy import (
    Boolean, Column, ForeignKey, Integer, String, DateTime, Text, Enum as SQLAlchemyEnum, Float
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import enum # For Python enums used with SQLAlchemyEnum
from .database import Base # Or wherever your Base is defined (e.g., a shared base.py)

# Create a Base for declarative models
Base = declarative_base()

# --- Enums (if you use them for status fields etc.) ---
# Example: If you have specific statuses for LeadCampaignStatus
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
    # Add other statuses as needed

class AIClassificationEnum(str, enum.Enum):
    positive_interest = "positive_interest"
    question = "question"
    objection = "objection"
    unsubscribe_request = "unsubscribe_request"
    out_of_office = "out_of_office"
    negative_reply = "negative_reply"
    not_applicable = "not_applicable"
    # Add other classifications

# --- Main Models ---

class Organization(Base): # Assuming you have an Organization table
    __tablename__ = "organizations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    users = relationship("User", back_populates="organization")
    leads = relationship("Lead", back_populates="organization")
    icps = relationship("ICP", back_populates="organization")
    offerings = relationship("Offering", back_populates="organization")
    email_campaigns = relationship("EmailCampaign", back_populates="organization")
    email_settings = relationship("OrganizationEmailSettings", back_populates="organization", uselist=False) # <--- UPDATED CLASS NAME

class User(Base): # Assuming a User model
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="users")

class ICP(Base): # Ideal Customer Profile
    __tablename__ = "icps"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    title_keywords = Column(Text, nullable=True) # Could be JSON or comma-separated
    industry_keywords = Column(Text, nullable=True)
    location_keywords = Column(Text, nullable=True)
    # Example: company_size_min = Column(Integer, nullable=True)
    # Example: company_size_max = Column(Integer, nullable=True)
    company_size_rules = Column(Text, nullable=True) # Could store JSON like {"min": 10, "max": 50}
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="icps")
    campaigns = relationship("EmailCampaign", back_populates="icp")
    # leads_matched = relationship("Lead", back_populates="matched_icp") # If you want a direct link

class Offering(Base):
    __tablename__ = "offerings"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    key_features = Column(Text, nullable=True) # Could be JSON array
    target_pain_points = Column(Text, nullable=True) # Could be JSON array
    call_to_action = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    organization = relationship("Organization", back_populates="offerings")
    campaigns = relationship("EmailCampaign", back_populates="offering")


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True, nullable=False) # Consider unique=True per organization
    name = Column(String, index=True, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    company_name = Column(String, index=True, nullable=True) # Renamed from 'company' for clarity
    title = Column(String, nullable=True)
    linkedin_profile = Column(String, nullable=True)
    source = Column(String, nullable=True)
    # Custom fields can be added or handled via a JSON column
    custom_fields = Column(Text, nullable=True) # For storing JSON data

    # ICP Matching related fields
    matched_icp_id = Column(Integer, ForeignKey("icps.id"), nullable=True)
    icp_match_reason = Column(Text, nullable=True)
    is_icp_matched = Column(Boolean, default=False) # 'matched' from your Streamlit form

    # Appointment and status fields
    appointment_confirmed = Column(Boolean, default=False)
    appointment_details = Column(Text, nullable=True) # Store notes about the appointment
    is_unsubscribed = Column(Boolean, default=False) # Global unsubscribe flag

    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="leads")
    # matched_icp = relationship("ICP", back_populates="leads_matched") # If direct link defined above
    campaign_statuses = relationship("LeadCampaignStatus", back_populates="lead")
    email_replies = relationship("EmailReply", back_populates="lead") # All replies from this lead

    # To make email unique per organization, you might use a UniqueConstraint
    # from sqlalchemy import UniqueConstraint
    # __table_args__ = (UniqueConstraint('email', 'organization_id', name='_email_org_uc'),)


class EmailCampaign(Base):
    __tablename__ = "email_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False) # User activates/deactivates
    ai_status = Column(String, default="pending") # e.g., pending, generating, completed, failed, completed_partial
    ai_error_message = Column(Text, nullable=True)

    icp_id = Column(Integer, ForeignKey("icps.id"), nullable=True)
    offering_id = Column(Integer, ForeignKey("offerings.id"), nullable=True)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="email_campaigns")
    icp = relationship("ICP", back_populates="campaigns")
    offering = relationship("Offering", back_populates="campaigns")
    steps = relationship("CampaignStep", back_populates="campaign", cascade="all, delete-orphan")
    lead_statuses = relationship("LeadCampaignStatus", back_populates="campaign")
    # outgoing_emails = relationship("OutgoingEmailLog", back_populates="campaign")


class CampaignStep(Base):
    __tablename__ = "campaign_steps"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), nullable=False)
    step_number = Column(Integer, nullable=False) # e.g., 1, 2, 3
    delay_days = Column(Integer, default=0) # Days after previous step or enrollment
    subject_template = Column(String, nullable=False)
    body_template = Column(Text, nullable=False)
    follow_up_angle = Column(String, nullable=True) # AI's suggested angle
    is_ai_crafted = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campaign = relationship("EmailCampaign", back_populates="steps")


class LeadCampaignStatus(Base):
    __tablename__ = "lead_campaign_status"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), nullable=False)

    status = Column(SQLAlchemyEnum(LeadStatusEnum), default=LeadStatusEnum.pending_enrollment, nullable=False)
    status_reason = Column(Text, nullable=True) # e.g., AI classification details, error messages
    current_step_number = Column(Integer, default=0) # Last step processed or next step to process
    next_email_due_at = Column(DateTime, nullable=True, index=True) # When the next email in sequence is due
    last_contacted_at = Column(DateTime, nullable=True) # When last email was sent in this campaign
    last_response_at = Column(DateTime, nullable=True) # When last reply was received for this campaign
    engagement_score = Column(Float, default=0.0) # Opens, clicks, replies
    is_active = Column(Boolean, default=True) # If false, lead is paused/finished in this campaign
    error_count = Column(Integer, default=0)

    # Timestamps for this specific enrollment
    enrolled_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    lead = relationship("Lead", back_populates="campaign_statuses")
    campaign = relationship("EmailCampaign", back_populates="lead_statuses")
    # associated_replies relationship might be redundant if EmailReply links to lead_id and campaign_id

# Table for Email Replies (IMAP Polling)
class EmailReply(Base):
    __tablename__ = "email_replies"
    id = Column(Integer, primary_key=True, index=True)
    message_id_header = Column(String, unique=True, index=True, nullable=False) # From email header
    in_reply_to_header = Column(String, index=True, nullable=True) # Links to outgoing email
    thread_id = Column(String, index=True, nullable=True) # If available from IMAP/email
    subject = Column(Text, nullable=True)
    sender_email = Column(String, index=True, nullable=False)
    recipient_email = Column(String, index=True, nullable=False) # Your campaign email address
    received_at = Column(DateTime, nullable=False, index=True)
    body_text = Column(Text, nullable=True) # Full text body
    body_html = Column(Text, nullable=True) # Full HTML body
    body_preview = Column(Text, nullable=True) # Short snippet

    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=True) # Linked lead
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), nullable=True) # Linked campaign
    original_outgoing_email_id = Column(Integer, ForeignKey("outgoing_email_log.id"), nullable=True) # If linked to a specific sent email

    # AI Classification Fields
    ai_classification = Column(SQLAlchemyEnum(AIClassificationEnum), nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_confidence_score = Column(Float, nullable=True)
    ai_processed_at = Column(DateTime, nullable=True)

    # User Action Fields
    is_actioned_by_user = Column(Boolean, default=False)
    action_taken = Column(String, nullable=True) # e.g., "appointment_set", "manual_followup"
    action_notes = Column(Text, nullable=True)
    action_timestamp = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    lead = relationship("Lead", back_populates="email_replies")
    # campaign = relationship("EmailCampaign") # If you want direct link
    # original_outgoing_email = relationship("OutgoingEmailLog", back_populates="replies")


# Table for Outgoing Email Logs
class OutgoingEmailLog(Base):
    __tablename__ = "outgoing_email_log"
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    campaign_id = Column(Integer, ForeignKey("email_campaigns.id"), nullable=False)
    campaign_step_id = Column(Integer, ForeignKey("campaign_steps.id"), nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, index=True)
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body_html = Column(Text, nullable=True) # Store the actual sent body
    status = Column(String, default="sent") # e.g., sent, failed, bounced
    error_message = Column(Text, nullable=True)
    message_id_returned = Column(String, nullable=True, index=True) # Message-ID from ESP

    # lead = relationship("Lead") # Optional: if needed for direct access
    # campaign = relationship("EmailCampaign", back_populates="outgoing_emails")
    # step = relationship("CampaignStep")
    # replies = relationship("EmailReply", back_populates="original_outgoing_email")


class OrganizationEmailSettings(Base): # <--- RENAMED CLASS
    __tablename__ = "organization_email_settings" # <--- RENAMED TABLE

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)

    provider_type = Column(String, nullable=True)
    verified_sender_email = Column(String, nullable=False)
    sender_name = Column(String, nullable=True)

    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, nullable=True)
    smtp_username = Column(String, nullable=True)
    encrypted_smtp_password = Column(String, nullable=True)

    encrypted_api_key = Column(String, nullable=True)
    encrypted_secret_key = Column(String, nullable=True) # If you store AWS secret key
    encrypted_access_token = Column(String, nullable=True)
    encrypted_refresh_token = Column(String, nullable=True)
    token_expiry = Column(DateTime(timezone=True), nullable=True)
    aws_region = Column(String, nullable=True)

    is_configured = Column(Boolean, default=False, nullable=False)

    enable_reply_detection = Column(Boolean, default=False, nullable=False) # <--- ADDED
    imap_host = Column(String, nullable=True)
    imap_port = Column(Integer, default=993, nullable=True)
    imap_username = Column(String, nullable=True)
    encrypted_imap_password = Column(String, nullable=True) # <--- Store encrypted
    imap_use_ssl = Column(Boolean, default=True, nullable=False)

    last_imap_poll_uid = Column(Text, nullable=True) # <--- ADDED
    last_imap_poll_timestamp = Column(DateTime(timezone=True), nullable=True) # <--- ADDED

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
