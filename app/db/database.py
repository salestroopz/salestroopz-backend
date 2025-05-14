# app/db/database.py

from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, func, and_, or_, text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert # For ON CONFLICT DO UPDATE

from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone

# --- Model Imports (CRUCIAL: These must be correctly defined in app.db.models) ---
try:
    from . import models # Assuming models.py is in the same directory
    from .models import (
        Base, Organization, User, ICP, Offering, Lead, EmailCampaign, CampaignStep,
        LeadCampaignStatus, OrganizationEmailSettings, OutgoingEmailLog, EmailReply
    )
except ImportError as e:
    print(f"CRITICAL ERROR: Could not import SQLAlchemy models from .models: {e}")
    print("Please ensure app.db.models.py exists and defines all necessary SQLAlchemy models.")
    # To prevent the app from completely breaking on import, define placeholders
    # but this means the DB functions will fail until models are correct.
    Base = None
    Organization = User = ICP = Offering = Lead = EmailCampaign = CampaignStep = None
    LeadCampaignStatus = OrganizationEmailSettings = OutgoingEmailLog = EmailReply = None

from app.schemas import LeadStatusEnum # Assuming this is for enum values
import os

# Import logger
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

# Import Settings
try:
    from app.utils.config import settings
    logger.info("Successfully imported settings in database.py")
    if not settings or not getattr(settings, 'DATABASE_URL', None) or \
       settings.DATABASE_URL == "ENV_VAR_DATABASE_URL_NOT_SET" or \
       not settings.DATABASE_URL.startswith(("postgresql://", "postgres://")):
        logger.critical("DATABASE_URL from settings is not configured or is invalid for SQLAlchemy.")
        # Fallback to os.getenv if settings are problematic for DATABASE_URL
        SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
        if not SQLALCHEMY_DATABASE_URL:
            raise ValueError("FATAL ERROR: DATABASE_URL cannot be determined.")
        logger.warning(f"Falling back to DATABASE_URL from environment: {SQLALCHEMY_DATABASE_URL[:30]}...")
    else:
        SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
except ImportError:
    logger.critical("Could not import settings from app.utils.config. Falling back for DATABASE_URL.")
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URL:
        raise ValueError("FATAL ERROR: DATABASE_URL environment variable is not set and settings import failed.")
except Exception as e:
    logger.critical(f"Error loading settings in database.py: {e}. Falling back for DATABASE_URL.")
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URL:
        raise ValueError("FATAL ERROR: DATABASE_URL cannot be determined after settings error.")


if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("FATAL ERROR: SQLALCHEMY_DATABASE_URL is not set.")

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
except Exception as e:
    logger.error(f"ERROR: Could not create database engine with URL: {SQLALCHEMY_DATABASE_URL}")
    logger.error(f"SQLAlchemy create_engine error: {e}", exc_info=True)
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_and_tables():
    """Creates all database tables defined in models.py inheriting from Base."""
    if not Base:
        logger.error("SQLAlchemy Base not imported/defined. Cannot create tables.")
        return
    logger.info("Attempting to create database tables via SQLAlchemy models (Base.metadata.create_all)...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables (SQLAlchemy models) checked/created successfully.")
    except Exception as e:
        logger.error(f"ERROR: Could not create database tables via SQLAlchemy: {e}", exc_info=True)

# ==========================================
# PLACEHOLDER ENCRYPTION FUNCTIONS - WARNING!
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None: return None
    return plain_text
def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None: return None
    return encrypted_text

# ==========================================
# ORGANIZATION CRUD OPERATIONS (SQLAlchemy)
# ==========================================
def create_organization(db: Session, name: str) -> Optional[models.Organization]:
    """Creates an organization or returns existing one by name."""
    if not Organization: return None # Model not available
    try:
        existing_org = db.query(Organization).filter(Organization.name == name).first()
        if existing_org:
            logger.warning(f"Org name '{name}' already exists. Returning existing ID: {existing_org.id}")
            return existing_org

        new_org = Organization(name=name)
        db.add(new_org)
        db.commit()
        db.refresh(new_org)
        logger.info(f"Created org '{new_org.name}' ID: {new_org.id}")
        return new_org
    except IntegrityError: # Should be caught by the check above, but as a safeguard
        db.rollback()
        logger.warning(f"IntegrityError for org name '{name}'. Fetching existing.")
        return db.query(Organization).filter(Organization.name == name).first()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error creating org '{name}': {e}", exc_info=True)
        return None

def get_organization_by_id(db: Session, organization_id: int) -> Optional[models.Organization]:
    if not Organization: return None
    try:
        return db.query(Organization).filter(Organization.id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting org ID {organization_id}: {e}", exc_info=True)
        return None

def get_organization_by_name(db: Session, name: str) -> Optional[models.Organization]:
    if not Organization: return None
    try:
        return db.query(Organization).filter(Organization.name == name).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting org by name '{name}': {e}", exc_info=True)
        return None

def get_all_organizations(db: Session) -> List[models.Organization]:
    if not Organization: return []
    try:
        return db.query(Organization).order_by(Organization.name).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting all organizations: {e}", exc_info=True)
        return []

# ==========================================
# USER CRUD (SQLAlchemy)
# ==========================================
def create_user(db: Session, email: str, hashed_password: str, organization_id: int) -> Optional[models.User]:
    if not User: return None
    try:
        # Check if org exists
        if not db.query(Organization).filter(Organization.id == organization_id).first():
            logger.error(f"Organization ID {organization_id} not found when creating user '{email}'.")
            return None

        new_user = User(email=email, hashed_password=hashed_password, organization_id=organization_id)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"Created user '{email}' (ID: {new_user.id}) for org ID {organization_id}")
        return new_user
    except IntegrityError: # Email already exists
        db.rollback()
        logger.warning(f"User email '{email}' already exists. Fetching existing.")
        return db.query(User).filter(User.email == email).first()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error creating user '{email}': {e}", exc_info=True)
        return None

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    if not User: return None
    try:
        # Use joinedload for eager loading of organization if relationship is defined in User model
        # from sqlalchemy.orm import joinedload
        # return db.query(User).options(joinedload(User.organization)).filter(User.id == user_id).first()
        return db.query(User).filter(User.id == user_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting user ID {user_id}: {e}", exc_info=True)
        return None

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    if not User: return None
    try:
        # return db.query(User).options(joinedload(User.organization)).filter(User.email == email).first()
        return db.query(User).filter(User.email == email).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting user by email {email}: {e}", exc_info=True)
        return None

def get_users_by_organization(db: Session, organization_id: int) -> List[models.User]:
    if not User: return []
    try:
        return db.query(User).filter(User.organization_id == organization_id).order_by(User.email).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting users for Org {organization_id}: {e}", exc_info=True)
        return []

# ==========================================
# LEAD CRUD OPERATIONS (SQLAlchemy)
# ==========================================
def save_lead(db: Session, lead_data: Dict, organization_id: int) -> Optional[models.Lead]:
    if not Lead: return None
    if not lead_data.get('email'):
        logger.warning(f"Skipping lead save for org {organization_id}: missing email")
        return None

    # Prepare data for insert/update, ensuring boolean and icp_match_id handling
    values_to_set = lead_data.copy()
    values_to_set['organization_id'] = organization_id
    values_to_set['matched'] = bool(values_to_set.get('matched', False))
    values_to_set['appointment_confirmed'] = bool(values_to_set.get('appointment_confirmed', False))
    # Ensure 'icp_match_id' is present if provided, or defaults to None if not (model should handle this)
    if 'icp_match_id' not in values_to_set:
        values_to_set['icp_match_id'] = None


    # Remove 'id' and 'created_at' as they are auto-managed or not part of conflict target for update
    # For the update part of ON CONFLICT, we list fields that should be updated
    update_dict = {
        key: values_to_set[key] for key in values_to_set
        if key not in ['id', 'email', 'organization_id', 'created_at'] # These are part of index or not to be updated on conflict
    }
    update_dict['updated_at'] = datetime.now(timezone.utc)


    # Prepare insert statement with ON CONFLICT DO UPDATE
    # Assumes a unique constraint on (organization_id, email)
    stmt = pg_insert(Lead).values(**values_to_set)
    stmt = stmt.on_conflict_do_update(
        index_elements=[Lead.organization_id, Lead.email],  # Columns in your UNIQUE constraint
        set_=update_dict
    ).returning(Lead) # Get the full row back

    try:
        result_proxy = db.execute(stmt)
        saved_lead_orm = result_proxy.scalar_one_or_none() #scalar_one if you expect one row
        db.commit()
        if saved_lead_orm:
            # db.refresh(saved_lead_orm) # Not strictly needed as returning(Lead) gives the state
            logger.debug(f"Successfully saved/updated lead ID {saved_lead_orm.id} for org {organization_id}")
            return saved_lead_orm
        else: # Should not happen with returning if conflict or insert occurred
            logger.error("Lead save/update did not return the lead object as expected.")
            return None
    except IntegrityError as e: # Fallback for other integrity errors not caught by on_conflict
        db.rollback()
        logger.error(f"DB IntegrityError saving lead for org {organization_id}, email {lead_data.get('email')}: {e}", exc_info=True)
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB SQLAlchemyError saving lead for org {organization_id}, email {lead_data.get('email')}: {e}", exc_info=True)
        return None


def get_lead_by_id(db: Session, lead_id: int, organization_id: int) -> Optional[models.Lead]:
    if not Lead: return None
    try:
        return db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting lead ID {lead_id} for Org {organization_id}: {e}", exc_info=True)
        return None

def get_lead_by_email(db: Session, email: str, organization_id: int) -> Optional[models.Lead]:
    if not Lead: return None
    try:
        return db.query(Lead).filter(Lead.email == email, Lead.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting lead by email '{email}' for Org {organization_id}: {e}", exc_info=True)
        return None

def get_leads_by_organization(db: Session, organization_id: int, offset: int = 0, limit: int = 100) -> List[models.Lead]:
    if not Lead: return []
    try:
        return db.query(Lead).filter(Lead.organization_id == organization_id)\
            .order_by(Lead.created_at.desc())\
            .offset(offset).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting leads for Org {organization_id}: {e}", exc_info=True)
        return []

def update_lead_partial(db: Session, lead_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.Lead]:
    if not Lead: return None
    try:
        lead_to_update = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == organization_id).first()
        if not lead_to_update:
            logger.warning(f"Lead ID {lead_id} not found for Org {organization_id} during partial update.")
            return None

        allowed_fields = {"name", "company", "title", "source", "linkedin_profile", "company_size",
                          "industry", "location", "matched", "reason", "crm_status",
                          "appointment_confirmed", "icp_match_id"}
        has_updates = False
        for key, value in updates.items():
            if key in allowed_fields:
                if key == "matched" or key == "appointment_confirmed":
                    setattr(lead_to_update, key, bool(value))
                elif key == "icp_match_id" and value is None: # Allow setting FK to None
                    setattr(lead_to_update, key, None)
                elif value is not None: # For other fields, only update if value is not None
                    setattr(lead_to_update, key, value)
                has_updates = True

        if not has_updates:
            logger.info(f"No valid fields provided for updating lead ID {lead_id}")
            return lead_to_update # Return current state

        lead_to_update.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(lead_to_update)
        logger.info(f"Partially updated lead ID {lead_id} for Org {organization_id}")
        return lead_to_update
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error partially updating lead ID {lead_id}: {e}", exc_info=True)
        return None

def delete_lead(db: Session, lead_id: int, organization_id: int) -> bool:
    if not Lead: return False
    try:
        lead_to_delete = db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == organization_id).first()
        if lead_to_delete:
            db.delete(lead_to_delete)
            db.commit()
            logger.info(f"Deleted lead ID {lead_id} for Org {organization_id}")
            return True
        else:
            logger.warning(f"Lead ID {lead_id} not found for Org {organization_id} during delete.")
            return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error deleting lead ID {lead_id}: {e}", exc_info=True)
        return False


# ==========================================
# ICP CRUD OPERATIONS (SQLAlchemy)
# ==========================================
def create_icp(db: Session, organization_id: int, icp_definition: Dict[str, Any]) -> Optional[models.ICP]:
    if not ICP or not Organization: return None
    try:
        if not db.query(Organization).filter(Organization.id == organization_id).first():
            logger.error(f"Organization ID {organization_id} not found for ICP creation.")
            return None
        if not icp_definition.get("name"):
            logger.error("ICP name is required.")
            return None

        # JSON fields should be passed as Python dicts/lists
        new_icp_data = {
            "organization_id": organization_id,
            "name": icp_definition.get("name", "Default ICP"),
            "title_keywords": icp_definition.get("title_keywords") or [],
            "industry_keywords": icp_definition.get("industry_keywords") or [],
            "company_size_rules": icp_definition.get("company_size_rules") or {},
            "location_keywords": icp_definition.get("location_keywords") or [],
            # updated_at and created_at should be handled by model defaults or db triggers if configured
        }
        new_icp = ICP(**new_icp_data)
        db.add(new_icp)
        db.commit()
        db.refresh(new_icp)
        logger.info(f"Created ICP '{new_icp.name}' (ID: {new_icp.id}) for Org ID: {organization_id}")
        return new_icp
    except IntegrityError as e: # e.g. if (org_id, name) is unique and violated
        db.rollback()
        logger.warning(f"DB IntegrityError creating ICP: {e}", exc_info=True)
        # Optionally, try to fetch if it's a duplicate name issue
        return db.query(ICP).filter(ICP.organization_id == organization_id, ICP.name == icp_definition.get("name")).first()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error creating ICP for Org ID {organization_id}: {e}", exc_info=True)
        return None

def update_icp(db: Session, icp_id: int, organization_id: int, icp_definition: Dict[str, Any]) -> Optional[models.ICP]:
    if not ICP: return None
    try:
        icp_to_update = db.query(ICP).filter(ICP.id == icp_id, ICP.organization_id == organization_id).first()
        if not icp_to_update:
            logger.warning(f"ICP ID {icp_id} not found for Org ID {organization_id} for update.")
            return None

        has_updates = False
        if "name" in icp_definition and icp_definition["name"] is not None:
            icp_to_update.name = icp_definition["name"]
            has_updates = True
        # For JSON fields, update if key is present in definition, allowing empty lists/dicts
        json_fields = ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
        for field in json_fields:
            if field in icp_definition:
                setattr(icp_to_update, field, icp_definition[field]) # Pass Python dict/list directly
                has_updates = True
        
        if not has_updates:
            logger.info(f"No fields to update for ICP ID {icp_id}.")
            return icp_to_update

        # icp_to_update.updated_at = datetime.now(timezone.utc) # if model doesn't auto-update
        db.commit()
        db.refresh(icp_to_update)
        logger.info(f"Updated ICP ID {icp_id} for Org ID {organization_id}")
        return icp_to_update
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error updating ICP ID {icp_id}: {e}", exc_info=True)
        return None

def get_icp_by_id(db: Session, icp_id: int, organization_id: int) -> Optional[models.ICP]:
    if not ICP: return None
    try:
        return db.query(ICP).filter(ICP.id == icp_id, ICP.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting ICP ID {icp_id} for Org ID {organization_id}: {e}", exc_info=True)
        return None

def get_icps_by_organization_id(db: Session, organization_id: int) -> List[models.ICP]:
    if not ICP: return []
    try:
        return db.query(ICP).filter(ICP.organization_id == organization_id).order_by(ICP.name).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting all ICPs for Org ID {organization_id}: {e}", exc_info=True)
        return []

def delete_icp(db: Session, icp_id: int, organization_id: int) -> bool:
    if not ICP: return False
    try:
        icp_to_delete = db.query(ICP).filter(ICP.id == icp_id, ICP.organization_id == organization_id).first()
        if icp_to_delete:
            db.delete(icp_to_delete)
            db.commit()
            logger.info(f"Deleted ICP ID {icp_id} for Org ID {organization_id}")
            return True
        logger.warning(f"ICP ID {icp_id} not found for Org ID {organization_id} during delete.")
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error deleting ICP ID {icp_id}: {e}", exc_info=True)
        return False

# ... Continue this pattern for ALL other CRUD sections:
# Offering, EmailCampaign, CampaignStep, LeadCampaignStatus,
# OrganizationEmailSettings, OutgoingEmailLog, EmailReply.

# --- Helper for partial updates (can be generalized if needed) ---
def _update_entity_fields(entity: Any, updates: Dict[str, Any], allowed_fields: set) -> bool:
    has_updates = False
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(entity, key, value)
            has_updates = True
    return has_updates

# ==========================================
# OFFERING CRUD OPERATIONS (SQLAlchemy)
# ==========================================
def create_offering(db: Session, organization_id: int, offering_data: Dict[str, Any]) -> Optional[models.Offering]:
    if not Offering or not Organization: return None
    try:
        if not db.query(Organization).filter(Organization.id == organization_id).first():
            logger.error(f"Organization ID {organization_id} not found for Offering creation.")
            return None
        if not offering_data.get("name"):
            logger.error("Offering name is required.")
            return None

        new_offering_data = {
            "organization_id": organization_id,
            "name": offering_data.get("name"),
            "description": offering_data.get("description"),
            "key_features": offering_data.get("key_features") or [],
            "target_pain_points": offering_data.get("target_pain_points") or [],
            "call_to_action": offering_data.get("call_to_action"),
            "is_active": bool(offering_data.get("is_active", True)),
        }
        new_offering = Offering(**new_offering_data)
        db.add(new_offering)
        db.commit()
        db.refresh(new_offering)
        logger.info(f"Created Offering '{new_offering.name}' (ID: {new_offering.id}) for Org {organization_id}")
        return new_offering
    except IntegrityError: # Unique (organization_id, name)
        db.rollback()
        logger.warning(f"Offering '{offering_data.get('name')}' likely already exists for Org {organization_id}.")
        return db.query(Offering).filter(Offering.name == offering_data.get("name"), Offering.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error creating Offering: {e}", exc_info=True)
        return None

def get_offering_by_id(db: Session, offering_id: int, organization_id: int) -> Optional[models.Offering]:
    if not Offering: return None
    try:
        return db.query(Offering).filter(Offering.id == offering_id, Offering.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting offering ID {offering_id}: {e}", exc_info=True)
        return None

def get_offerings_by_organization(db: Session, organization_id: int, active_only: bool = True) -> List[models.Offering]:
    if not Offering: return []
    try:
        query = db.query(Offering).filter(Offering.organization_id == organization_id)
        if active_only:
            query = query.filter(Offering.is_active == True)
        return query.order_by(Offering.name).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting offerings for Org {organization_id}: {e}", exc_info=True)
        return []

def update_offering(db: Session, offering_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.Offering]:
    if not Offering: return None
    try:
        offering = db.query(Offering).filter(Offering.id == offering_id, Offering.organization_id == organization_id).first()
        if not offering:
            logger.warning(f"Offering ID {offering_id} not found for Org {organization_id}.")
            return None

        allowed = {"name", "description", "key_features", "target_pain_points", "call_to_action", "is_active"}
        if not _update_entity_fields(offering, updates, allowed):
            logger.info(f"No valid fields to update for Offering ID {offering_id}.")
            return offering
        
        # offering.updated_at = datetime.now(timezone.utc) # If model doesn't auto-update
        db.commit()
        db.refresh(offering)
        logger.info(f"Updated Offering ID {offering_id}.")
        return offering
    except IntegrityError:
        db.rollback()
        logger.warning(f"Integrity error updating offering {offering_id} (e.g. duplicate name).")
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error updating offering ID {offering_id}: {e}", exc_info=True)
        return None

def delete_offering(db: Session, offering_id: int, organization_id: int) -> bool:
    if not Offering: return False
    # Similar to delete_icp
    try:
        offering_to_delete = db.query(Offering).filter(Offering.id == offering_id, Offering.organization_id == organization_id).first()
        if offering_to_delete:
            db.delete(offering_to_delete)
            db.commit()
            logger.info(f"Deleted Offering ID {offering_id} for Org ID {organization_id}")
            return True
        logger.warning(f"Offering ID {offering_id} not found for Org ID {organization_id} during delete.")
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error deleting Offering ID {offering_id}: {e}", exc_info=True)
        return False

# ===========================================================
# CAMPAIGN CRUD (SQLAlchemy)
# ===========================================================
def create_campaign(db: Session, organization_id: int, name: str, description: Optional[str] = None,
                    is_active: bool = False, icp_id: Optional[int] = None,
                    offering_id: Optional[int] = None, ai_status: str = "pending") -> Optional[models.EmailCampaign]:
    if not EmailCampaign or not Organization: return None
    try:
        if not db.query(Organization).filter(Organization.id == organization_id).first(): return None # Org check
        # Optional: Check if ICP and Offering exist if IDs are provided
        if icp_id and not db.query(ICP).filter(ICP.id == icp_id, ICP.organization_id == organization_id).first():
            logger.warning(f"ICP ID {icp_id} not found for campaign creation.")
            return None
        if offering_id and not db.query(Offering).filter(Offering.id == offering_id, Offering.organization_id == organization_id).first():
            logger.warning(f"Offering ID {offering_id} not found for campaign creation.")
            return None

        new_campaign = EmailCampaign(
            organization_id=organization_id, name=name, description=description,
            is_active=is_active, icp_id=icp_id, offering_id=offering_id, ai_status=ai_status
        )
        db.add(new_campaign)
        db.commit()
        db.refresh(new_campaign)
        logger.info(f"Created campaign '{name}' (ID: {new_campaign.id}) for Org {organization_id}")
        return new_campaign
    except IntegrityError as e: # E.g. FK constraint failed if ICP/Offering check was skipped
        db.rollback()
        logger.error(f"DB IntegrityError creating campaign '{name}': {e}", exc_info=True)
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error creating campaign '{name}': {e}", exc_info=True)
        return None

def get_campaign_by_id(db: Session, campaign_id: int, organization_id: int) -> Optional[models.EmailCampaign]:
    if not EmailCampaign: return None
    try:
        # For eager loading of related icp and offering names, use joinedload
        # from sqlalchemy.orm import joinedload
        # return db.query(EmailCampaign).options(
        #     joinedload(EmailCampaign.icp), joinedload(EmailCampaign.offering)
        # ).filter(EmailCampaign.id == campaign_id, EmailCampaign.organization_id == organization_id).first()
        # If you need names directly and relationships are simple `icp_name = Column(String)` on EmailCampaign model,
        # you might need a hybrid property or adjust model. For now, return the object.
        return db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id, EmailCampaign.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting campaign ID {campaign_id}: {e}", exc_info=True)
        return None

# To get campaign with icp_name and offering_name (if not directly on EmailCampaign model)
def get_campaign_with_details_by_id(db: Session, campaign_id: int, organization_id: int) -> Optional[Dict]:
    if not EmailCampaign or not ICP or not Offering: return None
    try:
        result = db.query(
                EmailCampaign,
                ICP.name.label("icp_name"),
                Offering.name.label("offering_name")
            ).\
            outerjoin(ICP, EmailCampaign.icp_id == ICP.id).\
            outerjoin(Offering, EmailCampaign.offering_id == Offering.id).\
            filter(EmailCampaign.id == campaign_id, EmailCampaign.organization_id == organization_id).\
            first()
        if result:
            campaign_obj, icp_name, offering_name = result
            campaign_dict = campaign_obj.__dict__ # Naive conversion
            campaign_dict.pop('_sa_instance_state', None) # Remove SA internal state
            campaign_dict["icp_name"] = icp_name
            campaign_dict["offering_name"] = offering_name
            return campaign_dict
        return None
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting campaign with details ID {campaign_id}: {e}", exc_info=True)
        return None


def get_campaigns_by_organization(db: Session, organization_id: int, active_only: Optional[bool] = None) -> List[models.EmailCampaign]:
    if not EmailCampaign: return []
    # Similar to get_offerings_by_organization
    try:
        query = db.query(EmailCampaign).filter(EmailCampaign.organization_id == organization_id)
        if active_only is not None:
            query = query.filter(EmailCampaign.is_active == active_only)
        return query.order_by(EmailCampaign.name).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting campaigns for Org {organization_id}: {e}", exc_info=True)
        return []

def update_campaign(db: Session, campaign_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.EmailCampaign]:
    if not EmailCampaign: return None
    try:
        campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id, EmailCampaign.organization_id == organization_id).first()
        if not campaign: return None
        allowed = {"name", "description", "is_active", "icp_id", "offering_id", "ai_status"}
        if not _update_entity_fields(campaign, updates, allowed): return campaign
        # campaign.updated_at = datetime.now(timezone.utc) # If model doesn't auto-update
        db.commit()
        db.refresh(campaign)
        return campaign
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error updating campaign ID {campaign_id}: {e}", exc_info=True)
        return None

def update_campaign_ai_status(db: Session, campaign_id: int, organization_id: int, ai_status: str) -> Optional[models.EmailCampaign]:
    if not EmailCampaign: return None
    return update_campaign(db, campaign_id, organization_id, {"ai_status": ai_status})


def delete_campaign(db: Session, campaign_id: int, organization_id: int) -> bool:
    if not EmailCampaign: return False
    # Similar to delete_icp/offering
    try:
        campaign_to_delete = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id, EmailCampaign.organization_id == organization_id).first()
        if campaign_to_delete:
            # SQLAlchemy handles related CampaignSteps deletion if cascade is set in model or DB
            db.delete(campaign_to_delete)
            db.commit()
            logger.info(f"Deleted Campaign ID {campaign_id} for Org ID {organization_id}")
            return True
        logger.warning(f"Campaign ID {campaign_id} not found for Org ID {organization_id} during delete.")
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error deleting Campaign ID {campaign_id}: {e}", exc_info=True)
        return False

# ===========================================================
# CAMPAIGN STEP CRUD (SQLAlchemy)
# ===========================================================
def create_campaign_step(db: Session, campaign_id: int, organization_id: int, step_number: int, delay_days: int,
                         subject_template: Optional[str], body_template: Optional[str],
                         is_ai_crafted: bool = False, follow_up_angle: Optional[str] = None) -> Optional[models.CampaignStep]:
    if not CampaignStep or not EmailCampaign: return None
    try:
        # Ensure parent campaign exists and belongs to the organization
        parent_campaign = db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id, EmailCampaign.organization_id == organization_id).first()
        if not parent_campaign:
            logger.error(f"Campaign ID {campaign_id} not found or doesn't belong to Org {organization_id} for step creation.")
            return None

        new_step = CampaignStep(
            campaign_id=campaign_id, organization_id=organization_id, step_number=step_number,
            delay_days=delay_days, subject_template=subject_template, body_template=body_template,
            is_ai_crafted=is_ai_crafted, follow_up_angle=follow_up_angle
        )
        db.add(new_step)
        db.commit()
        db.refresh(new_step)
        logger.info(f"Created step {step_number} (ID: {new_step.id}) for Campaign {campaign_id}")
        return new_step
    except IntegrityError: # E.g., unique (campaign_id, step_number)
        db.rollback()
        logger.warning(f"Step number {step_number} likely already exists for Campaign {campaign_id}.")
        return db.query(CampaignStep).filter(CampaignStep.campaign_id == campaign_id, CampaignStep.step_number == step_number).first()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error creating step {step_number} for Camp {campaign_id}: {e}", exc_info=True)
        return None

def get_campaign_step_by_id(db: Session, step_id: int, organization_id: int) -> Optional[models.CampaignStep]:
    if not CampaignStep: return None
    try:
        return db.query(CampaignStep).filter(CampaignStep.id == step_id, CampaignStep.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting step ID {step_id}: {e}", exc_info=True)
        return None

def get_steps_for_campaign(db: Session, campaign_id: int, organization_id: int) -> List[models.CampaignStep]:
    if not CampaignStep: return []
    try:
        return db.query(CampaignStep).filter(CampaignStep.campaign_id == campaign_id, CampaignStep.organization_id == organization_id)\
            .order_by(CampaignStep.step_number).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting steps for Camp {campaign_id}: {e}", exc_info=True)
        return []

def get_next_campaign_step(db: Session, campaign_id: int, organization_id: int, current_step_number: int) -> Optional[models.CampaignStep]:
    if not CampaignStep: return None
    next_step_no = current_step_number + 1
    return db.query(CampaignStep)\
        .filter(CampaignStep.campaign_id == campaign_id,
                CampaignStep.organization_id == organization_id,
                CampaignStep.step_number == next_step_no)\
        .first()


def update_campaign_step(db: Session, step_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.CampaignStep]:
    if not CampaignStep: return None
    try:
        step = db.query(CampaignStep).filter(CampaignStep.id == step_id, CampaignStep.organization_id == organization_id).first()
        if not step: return None
        allowed = {"step_number", "delay_days", "subject_template", "body_template", "is_ai_crafted", "follow_up_angle"}
        if not _update_entity_fields(step, updates, allowed): return step
        # step.updated_at = datetime.now(timezone.utc) # If model doesn't auto-update
        db.commit()
        db.refresh(step)
        return step
    except IntegrityError: # E.g. duplicate step_number for campaign
        db.rollback()
        logger.warning(f"Integrity error updating step {step_id} (e.g. duplicate step_number).")
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error updating step ID {step_id}: {e}", exc_info=True)
        return None

def delete_campaign_step(db: Session, step_id: int, organization_id: int) -> bool:
    if not CampaignStep: return False
    # Similar to delete_icp
    try:
        step_to_delete = db.query(CampaignStep).filter(CampaignStep.id == step_id, CampaignStep.organization_id == organization_id).first()
        if step_to_delete:
            db.delete(step_to_delete)
            db.commit()
            logger.info(f"Deleted Campaign Step ID {step_id} for Org ID {organization_id}")
            return True
        logger.warning(f"Campaign Step ID {step_id} not found for Org ID {organization_id} during delete.")
        return False
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error deleting Campaign Step ID {step_id}: {e}", exc_info=True)
        return False

# ===========================================================
# LEAD CAMPAIGN STATUS CRUD (SQLAlchemy)
# ===========================================================
def enroll_lead_in_campaign(db: Session, lead_id: int, campaign_id: int, organization_id: int) -> Optional[models.LeadCampaignStatus]:
    if not LeadCampaignStatus or not Lead or not EmailCampaign: return None
    try:
        # Ensure lead and campaign exist and belong to the organization
        if not db.query(Lead).filter(Lead.id == lead_id, Lead.organization_id == organization_id).first():
            logger.warning(f"Lead {lead_id} not found for enrollment in Org {organization_id}.")
            return None
        if not db.query(EmailCampaign).filter(EmailCampaign.id == campaign_id, EmailCampaign.organization_id == organization_id).first():
            logger.warning(f"Campaign {campaign_id} not found for enrollment in Org {organization_id}.")
            return None

        new_status = LeadCampaignStatus(
            lead_id=lead_id, campaign_id=campaign_id, organization_id=organization_id,
            status=LeadStatusEnum.active.value, # Or 'active' string
            current_step_number=0,
            # Set next_email_due_at to now for immediate processing, or based on first step delay
            next_email_due_at=datetime.now(timezone.utc)
        )
        db.add(new_status)
        db.commit()
        db.refresh(new_status)
        logger.info(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {new_status.id})")
        return new_status
    except IntegrityError: # Unique (lead_id)
        db.rollback()
        logger.warning(f"Lead ID {lead_id} already enrolled in a campaign. Fetching existing.")
        return db.query(LeadCampaignStatus).filter(LeadCampaignStatus.lead_id == lead_id, LeadCampaignStatus.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}", exc_info=True)
        return None

def update_lead_campaign_status(db: Session, status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.LeadCampaignStatus]:
    if not LeadCampaignStatus: return None
    try:
        status_obj = db.query(LeadCampaignStatus).filter(LeadCampaignStatus.id == status_id, LeadCampaignStatus.organization_id == organization_id).first()
        if not status_obj: return None
        allowed = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message", "user_notes"}
        if not _update_entity_fields(status_obj, updates, allowed): return status_obj
        # status_obj.updated_at = datetime.now(timezone.utc) # If model doesn't auto-update
        db.commit()
        db.refresh(status_obj)
        return status_obj
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error updating lead status ID {status_id}: {e}", exc_info=True)
        return None

def get_active_leads_due_for_step(db: Session, organization_id: Optional[int] = None, query_limit: int = 100) -> List[models.LeadCampaignStatus]:
    if not LeadCampaignStatus or not Lead or not EmailCampaign : return []
    try:
        query = db.query(LeadCampaignStatus).\
            join(Lead, LeadCampaignStatus.lead_id == Lead.id).\
            join(EmailCampaign, LeadCampaignStatus.campaign_id == EmailCampaign.id).\
            filter(LeadCampaignStatus.status == LeadStatusEnum.active.value).\
            filter(or_(
                LeadCampaignStatus.next_email_due_at <= datetime.now(timezone.utc),
                and_(LeadCampaignStatus.next_email_due_at == None, LeadCampaignStatus.current_step_number == 0)
            ))

        if organization_id is not None:
            query = query.filter(LeadCampaignStatus.organization_id == organization_id)

        leads_due = query.order_by(
                LeadCampaignStatus.organization_id,
                LeadCampaignStatus.next_email_due_at.asc().nulls_first(),
                LeadCampaignStatus.created_at.asc()
            ).limit(query_limit).all()
        logger.debug(f"DB: Found {len(leads_due)} active leads due for step (SQLAlchemy).")
        return leads_due
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting active leads due (SQLAlchemy): {e}", exc_info=True)
        return []


def get_lead_campaign_status_by_id(db: Session, status_id: int, organization_id: int) -> Optional[models.LeadCampaignStatus]:
    if not LeadCampaignStatus: return None
    try:
        return db.query(LeadCampaignStatus).filter(LeadCampaignStatus.id == status_id, LeadCampaignStatus.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting lead_campaign_status by id {status_id}: {e}", exc_info=True)
        return None

def get_lead_campaign_status(db: Session, lead_id: int, organization_id: int) -> Optional[models.LeadCampaignStatus]:
    if not LeadCampaignStatus: return None
    try: # Assumes unique (lead_id) on LeadCampaignStatus table
        return db.query(LeadCampaignStatus).filter(LeadCampaignStatus.lead_id == lead_id, LeadCampaignStatus.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting lead_campaign_status for lead {lead_id}: {e}", exc_info=True)
        return None

# ==========================================
# ORGANIZATION EMAIL SETTINGS CRUD (SQLAlchemy)
# ==========================================
def save_org_email_settings(db: Session, organization_id: int, settings_data: Dict[str, Any]) -> Optional[models.OrganizationEmailSettings]:
    if not OrganizationEmailSettings or not Organization: return None
    try:
        if not db.query(Organization).filter(Organization.id == organization_id).first():
            logger.error(f"Org ID {organization_id} not found for saving email settings.")
            return None
        if not settings_data.get("verified_sender_email") or not settings_data.get("provider_type"):
            logger.error("verified_sender_email and provider_type are required.")
            return None

        # Prepare values, encrypting sensitive data
        values = {
            "organization_id": organization_id,
            "provider_type": settings_data.get("provider_type"),
            "smtp_host": settings_data.get("smtp_host"),
            "smtp_port": int(settings_data["smtp_port"]) if settings_data.get("smtp_port") is not None else None,
            "smtp_username": settings_data.get("smtp_username"),
            "encrypted_smtp_password": _encrypt_data(settings_data.get("smtp_password")),
            "encrypted_api_key": _encrypt_data(settings_data.get("api_key")),
            "encrypted_access_token": _encrypt_data(settings_data.get("access_token")),
            "encrypted_refresh_token": _encrypt_data(settings_data.get("refresh_token")),
            "token_expiry": settings_data.get("token_expiry"),
            "verified_sender_email": settings_data.get("verified_sender_email"),
            "sender_name": settings_data.get("sender_name"),
            "is_configured": bool(settings_data.get("is_configured", False)),
            "enable_reply_detection": bool(settings_data.get("enable_reply_detection", False)),
            "imap_host": settings_data.get("imap_host"),
            "imap_port": int(settings_data["imap_port"]) if settings_data.get("imap_port") is not None else None,
            "imap_username": settings_data.get("imap_username"),
            "encrypted_imap_password": _encrypt_data(settings_data.get("imap_password")),
            "imap_use_ssl": bool(settings_data.get("imap_use_ssl", True)),
            "last_imap_poll_uid": settings_data.get("last_imap_poll_uid"),
            "last_imap_poll_timestamp": settings_data.get("last_imap_poll_timestamp"),
            # updated_at handled by model/db
        }

        # Upsert logic using PostgreSQL ON CONFLICT
        stmt = pg_insert(OrganizationEmailSettings).values(**values)
        # Exclude organization_id from the SET part as it's the conflict target
        update_values = {k: v for k, v in values.items() if k != 'organization_id'}
        update_values['updated_at'] = datetime.now(timezone.utc) # Explicitly set updated_at on update

        stmt = stmt.on_conflict_do_update(
            index_elements=[OrganizationEmailSettings.organization_id], # conflict target
            set_=update_values
        ).returning(OrganizationEmailSettings)

        result_proxy = db.execute(stmt)
        saved_settings_orm = result_proxy.scalar_one_or_none()
        db.commit()

        if saved_settings_orm:
            logger.info(f"Saved/Updated Email Settings for Org ID: {organization_id}")
            # Decrypt for returning to caller (optional, depends on use case)
            # saved_settings_orm.smtp_password = _decrypt_data(saved_settings_orm.encrypted_smtp_password)
            # ... and other encrypted fields ...
            return saved_settings_orm
        return None
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error saving email settings for Org {organization_id}: {e}", exc_info=True)
        return None


def get_org_email_settings_from_db(db: Session, organization_id: int, decrypt: bool = True) -> Optional[models.OrganizationEmailSettings]:
    if not OrganizationEmailSettings: return None
    try:
        settings_obj = db.query(OrganizationEmailSettings).filter(OrganizationEmailSettings.organization_id == organization_id).first()
        if settings_obj and decrypt:
            # Create a detached copy or add transient properties if you don't want to modify the persistent object
            # For simplicity, just adding attributes to the loaded object for now:
            settings_obj.smtp_password = _decrypt_data(settings_obj.encrypted_smtp_password)
            settings_obj.api_key = _decrypt_data(settings_obj.encrypted_api_key)
            settings_obj.access_token = _decrypt_data(settings_obj.encrypted_access_token)
            settings_obj.refresh_token = _decrypt_data(settings_obj.encrypted_refresh_token)
            settings_obj.imap_password = _decrypt_data(settings_obj.encrypted_imap_password)
        return settings_obj
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting email settings for Org {organization_id}: {e}", exc_info=True)
        return None

# ==========================================
# LEAD & IMAP RELATED QUERIES (SQLAlchemy)
# ==========================================
def get_leads_by_icp_match(db: Session, organization_id: int, icp_id: int, limit: int = 1000) -> List[models.Lead]:
    if not Lead: return []
    try:
        return db.query(Lead).filter(
            Lead.organization_id == organization_id,
            Lead.icp_match_id == icp_id,
            Lead.matched == True
        ).order_by(Lead.created_at.desc()).limit(limit).all()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting leads by ICP match (Org {organization_id}, ICP {icp_id}): {e}", exc_info=True)
        return []

def get_organizations_with_imap_enabled(db: Session, limit: int = 1000) -> List[models.OrganizationEmailSettings]:
    """Fetches organization email settings where IMAP reply detection is enabled and configured."""
    if not OrganizationEmailSettings: return []
    try:
        settings_list = db.query(OrganizationEmailSettings).filter(
            OrganizationEmailSettings.is_configured == True,
            OrganizationEmailSettings.enable_reply_detection == True,
            OrganizationEmailSettings.imap_host != None, OrganizationEmailSettings.imap_host != '',
            OrganizationEmailSettings.imap_username != None, OrganizationEmailSettings.imap_username != '',
            OrganizationEmailSettings.encrypted_imap_password != None, OrganizationEmailSettings.encrypted_imap_password != ''
        ).limit(limit).all()

        # Decrypt IMAP passwords for use
        for settings_obj in settings_list:
            settings_obj.imap_password = _decrypt_data(settings_obj.encrypted_imap_password)
        return settings_list
    except SQLAlchemyError as e:
        logger.error(f"DB Error fetching organizations with IMAP enabled: {e}", exc_info=True)
        return []

def update_organization_email_settings_field(db: Session, organization_id: int, updates: Dict[str, Any]) -> bool:
    if not OrganizationEmailSettings: return False
    try:
        settings = db.query(OrganizationEmailSettings).filter(OrganizationEmailSettings.organization_id == organization_id).first()
        if not settings:
            logger.warning(f"No org email settings found for org {organization_id} to update fields.")
            return False

        allowed = {"last_imap_poll_uid", "last_imap_poll_timestamp", "enable_reply_detection", "is_configured"}
        if not _update_entity_fields(settings, updates, allowed):
            logger.info(f"No valid fields to update in org email settings for org {organization_id}.")
            return False # Or True if no change is not an error

        # settings.updated_at = datetime.now(timezone.utc) # If model doesn't auto-update
        db.commit()
        logger.info(f"Updated organization_email_settings fields for org {organization_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error updating org email settings fields for org {organization_id}: {e}", exc_info=True)
        return False


# ==========================================
# REPLY HANDLING CRUD (SQLAlchemy)
# ==========================================
def log_sent_email(db: Session, lead_campaign_status_id: int, organization_id: int, lead_id: int,
                   campaign_id: int, campaign_step_id: int, message_id_header: str,
                   to_email: str, subject: str) -> Optional[models.OutgoingEmailLog]:
    if not OutgoingEmailLog: return None
    try:
        new_log = OutgoingEmailLog(
            lead_campaign_status_id=lead_campaign_status_id, organization_id=organization_id,
            lead_id=lead_id, campaign_id=campaign_id, campaign_step_id=campaign_step_id,
            message_id_header=message_id_header, to_email=to_email, subject=subject
            # sent_at handled by model default
        )
        db.add(new_log)
        db.commit()
        db.refresh(new_log)
        logger.info(f"Logged sent email: LCS_ID {lead_campaign_status_id}, Message-ID: {message_id_header}")
        return new_log
    except IntegrityError: # Unique (organization_id, message_id_header)
        db.rollback()
        logger.warning(f"Message-ID '{message_id_header}' for org {organization_id} likely already logged.")
        return db.query(OutgoingEmailLog).filter(
            OutgoingEmailLog.organization_id == organization_id,
            OutgoingEmailLog.message_id_header == message_id_header
        ).first()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error logging sent email: {e}", exc_info=True)
        return None

def store_email_reply(db: Session, reply_data: Dict[str, Any]) -> Optional[models.EmailReply]:
    if not EmailReply: return None
    # Basic validation
    required = ["lead_campaign_status_id", "organization_id", "lead_id", "campaign_id", "received_at", "from_email"]
    if not all(reply_data.get(f) is not None for f in required):
        logger.error(f"Missing required fields for storing email reply: {reply_data}")
        return None

    try:
        # Prepare data, ensuring JSON fields are Python dicts/lists
        new_reply_params = {
            "outgoing_email_log_id": reply_data.get("outgoing_email_log_id"),
            "lead_campaign_status_id": reply_data["lead_campaign_status_id"],
            "organization_id": reply_data["organization_id"],
            "lead_id": reply_data["lead_id"],
            "campaign_id": reply_data["campaign_id"],
            "received_at": reply_data["received_at"], # Should be datetime object
            "from_email": reply_data["from_email"],
            "reply_subject": reply_data.get("reply_subject"),
            "raw_body_text": reply_data.get("raw_body_text"),
            "cleaned_reply_text": reply_data.get("cleaned_reply_text"),
            "ai_classification": reply_data.get("ai_classification"),
            "ai_summary": reply_data.get("ai_summary"),
            "ai_extracted_entities": reply_data.get("ai_extracted_entities"), # Pass as Python dict/list
            "is_actioned_by_user": bool(reply_data.get("is_actioned_by_user", False)),
            "user_action_notes": reply_data.get("user_action_notes"),
        }
        new_reply = EmailReply(**new_reply_params)
        db.add(new_reply)
        db.commit()
        db.refresh(new_reply)
        logger.info(f"Stored email reply ID {new_reply.id} from {new_reply.from_email}")
        return new_reply
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"DB Error storing email reply: {e}", exc_info=True)
        return None

def get_outgoing_email_log_by_message_id(db: Session, organization_id: int, message_id_header: str) -> Optional[models.OutgoingEmailLog]:
    if not OutgoingEmailLog: return None
    try:
        return db.query(OutgoingEmailLog).filter(
            OutgoingEmailLog.organization_id == organization_id,
            OutgoingEmailLog.message_id_header == message_id_header
        ).first()
    except SQLAlchemyError as e:
        logger.error(f"DB Error getting outgoing log by Message-ID: {e}", exc_info=True)
        return None

# ==========================================
# DASHBOARD & ANALYTICS QUERIES (SQLAlchemy)
# ==========================================
def get_leads_with_positive_status_for_dashboard(db: Session, organization_id: int, limit: int = 100) -> List[Dict]:
    if not LeadCampaignStatus or not Lead or not EmailCampaign or not EmailReply: return []

    actionable_statuses = [
        LeadStatusEnum.positive_reply_ai_flagged.value,
        LeadStatusEnum.question_ai_flagged.value,
        LeadStatusEnum.appointment_manually_set.value,
        LeadStatusEnum.positive_reply_received.value,
        LeadStatusEnum.manual_follow_up_needed.value
    ]

    # Subquery to get the latest reply for each lead_campaign_status_id
    # This is a bit complex in ORM, sometimes a raw SQL or window function is easier,
    # but let's try with a correlated subquery or a lateral join if the DB supports it.
    # For simplicity, a common ORM approach is to fetch LCS and then iterate or use a separate query for latest reply.
    # A more optimized ORM way uses a subquery for latest reply ID/timestamp.

    # Simpler approach: Get LCS, then fetch latest reply separately if needed or use a view.
    # For direct translation of your SQL, a LATERAL JOIN or DISTINCT ON is best, but might need raw SQL or specific dialect features.

    # Let's try a version that fetches the main data and you can augment with reply details after.
    # Or, if models have relationships, it could be easier.
    # For this example, I'll adapt your original query structure.

    from sqlalchemy.sql.expression import select, alias
    from sqlalchemy.orm import aliased

    # Alias for the subquery on email_replies
    er_sub = aliased(EmailReply, name="er_sub")
    # Subquery to get the latest reply_id for each lead_campaign_status_id
    # This is tricky with ORM without window functions.
    # A common pattern for "latest-N-per-group" is hard in pure ORM.
    # For now, I'll show a structure that gets LCS and you'd have to fetch latest reply separately,
    # or you might use a hybrid_property on LeadCampaignStatus model for latest_reply.

    # A more direct, though potentially less performant without specific DB optimizations:
    # This gets all LCS matching criteria, then you might iterate and get latest reply.
    # This is NOT a direct translation of your SQL's efficiency for latest reply.
    try:
        query = db.query(
                LeadCampaignStatus.id.label("lead_campaign_status_id"),
                Lead.id.label("lead_id"),
                EmailCampaign.id.label("campaign_id"),
                LeadCampaignStatus.organization_id,
                LeadCampaignStatus.status.label("lead_campaign_status"),
                LeadCampaignStatus.last_response_type,
                LeadCampaignStatus.last_response_at,
                LeadCampaignStatus.user_notes,
                LeadCampaignStatus.updated_at.label("status_updated_at"),
                Lead.name.label("lead_name"),
                Lead.email.label("lead_email"),
                Lead.company.label("lead_company"),
                EmailCampaign.name.label("campaign_name")
                # Cannot easily get latest_reply_* fields here without more complex ORM/SQL
            ).\
            join(Lead, Lead.id == LeadCampaignStatus.lead_id).\
            join(EmailCampaign, EmailCampaign.id == LeadCampaignStatus.campaign_id).\
            filter(LeadCampaignStatus.organization_id == organization_id).\
            filter(LeadCampaignStatus.status.in_(actionable_statuses)).\
            order_by(LeadCampaignStatus.updated_at.desc()).\
            limit(limit)

        results = query.all() # List of RowProxy objects

        # Convert to list of dicts and then potentially fetch latest reply for each
        dashboard_items = []
        for row in results:
            item = dict(row) # Convert RowProxy to dict
            # Now, fetch the latest reply for item['lead_campaign_status_id']
            latest_reply = db.query(EmailReply).\
                filter(EmailReply.lead_campaign_status_id == item['lead_campaign_status_id']).\
                order_by(EmailReply.received_at.desc()).\
                first()
            if latest_reply:
                item['latest_reply_id'] = latest_reply.id
                item['latest_reply_snippet'] = (latest_reply.cleaned_reply_text or "")[:250]
                item['latest_reply_ai_summary'] = latest_reply.ai_summary
                item['latest_reply_ai_classification'] = latest_reply.ai_classification
                item['latest_reply_received_at'] = latest_reply.received_at
            else:
                item['latest_reply_id'] = None
                item['latest_reply_snippet'] = None
                item['latest_reply_ai_summary'] = None
                item['latest_reply_ai_classification'] = None
                item['latest_reply_received_at'] = None
            dashboard_items.append(item)
        return dashboard_items

    except SQLAlchemyError as e:
        logger.error(f"DB error fetching positive engagement for dashboard (Org {organization_id}): {e}", exc_info=True)
        return []


# Functions from the end of your original file, refactored if they use SQLAlchemy Session
def count_appointments_set(db: Session, organization_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
    if not Lead: return 0
    try:
        query = db.query(func.count(Lead.id)).filter(
            Lead.organization_id == organization_id,
            Lead.appointment_confirmed == True
        )
        if start_date: query = query.filter(Lead.updated_at >= start_date) # Assuming updated_at tracks this
        if end_date: query = query.filter(Lead.updated_at <= end_date)
        count = query.scalar()
        return count if count else 0
    except SQLAlchemyError as e:
        logger.error(f"Error counting appointments (SA): {e}", exc_info=True)
        return 0


def count_positive_replies_status(db: Session, organization_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
    if not LeadCampaignStatus or not Lead: return 0
    positive_statuses = [
        LeadStatusEnum.positive_reply_ai_flagged.value,
        LeadStatusEnum.positive_reply_received.value,
    ]
    try:
        query = db.query(func.count(LeadCampaignStatus.id)).join(Lead, Lead.id == LeadCampaignStatus.lead_id).filter(
            Lead.organization_id == organization_id,
            LeadCampaignStatus.status.in_(positive_statuses)
        )
        if start_date: query = query.filter(LeadCampaignStatus.last_response_at >= start_date)
        if end_date: query = query.filter(LeadCampaignStatus.last_response_at <= end_date)
        count = query.scalar()
        return count if count else 0
    except SQLAlchemyError as e:
        logger.error(f"Error counting positive replies (SA): {e}", exc_info=True)
        return 0

def get_recent_appointments_list(db: Session, organization_id: int, limit: int = 5) -> List[Dict]:
    if not Lead or not EmailCampaign or not LeadCampaignStatus: return []
    try:
        results = (
            db.query(
                Lead.name.label("lead_name"), # Assuming Lead model has 'name'
                Lead.company.label("company_name"), # Assuming Lead model has 'company'
                EmailCampaign.name.label("campaign_name"),
                LeadCampaignStatus.last_response_at.label("action_date")
            )
            .join(LeadCampaignStatus, Lead.id == LeadCampaignStatus.lead_id)
            .join(EmailCampaign, LeadCampaignStatus.campaign_id == EmailCampaign.id)
            .filter(
                Lead.organization_id == organization_id,
                Lead.appointment_confirmed == True
            )
            .order_by(LeadCampaignStatus.last_response_at.desc().nullslast())
            .limit(limit)
            .all()
        )
        return [
            {
                "lead_name": r.lead_name or "N/A",
                "company_name": r.company_name or "N/A",
                "campaign_name": r.campaign_name or "N/A",
                "date_marked": r.action_date.strftime('%Y-%m-%d %H:%M') if r.action_date else 'N/A'
            } for r in results
        ]
    except SQLAlchemyError as e:
        logger.error(f"Error fetching recent appointments list (SA): {e}", exc_info=True)
        return []

# ==========================================
# Main execution for schema creation
# ==========================================
if __name__ == "__main__":
    logger.info("Running database.py directly, attempting SQLAlchemy table creation...")
    if Base and engine: # Ensure Base is defined and engine is created
        create_db_and_tables()
        logger.info("SQLAlchemy table creation process finished.")
    else:
        logger.error("Cannot create tables: SQLAlchemy Base or engine not available.")

    # The old initialize_db() with raw SQL is now superseded by create_db_and_tables()
    # If you need to run raw SQL for specific setup (e.g. extensions, roles), do it separately or carefully.
