# app/db/database.py

# --- Standard Library Imports ---
import os
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

# --- SQLAlchemy Core Imports ---
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy import create_engine, func, and_, or_, text, inspect # Added inspect
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.dialects.postgresql import insert as pg_insert

# --- Application Specific Imports ---

# 1. Import Base FIRST
try:
    from .base_class import Base
except ImportError as e_base:
    print(f"CRITICAL ERROR [database.py]: Could not import SQLAlchemy Base from .base_class: {e_base}")
    raise SystemExit("SQLAlchemy Base class not found, application cannot start.") from e_base

# 2. Import Models module NEXT
try:
    from . import models # Access models like: models.User, models.Organization
except ImportError as e_models:
    print(f"CRITICAL ERROR [database.py]: Could not import the '.models' module: {e_models}")
    print("Check for errors within app/db/models.py (e.g., import errors, syntax errors).")
    raise SystemExit("Failed to import ORM models module, application cannot start.") from e_models

# 3. Import Schemas
try:
    from app.schemas import LeadStatusEnum
    # from app.schemas import AIClassificationEnum # If used directly in this file
except ImportError as e_schemas:
    print(f"Warning [database.py]: Could not import Enums from app.schemas: {e_schemas}")
    LeadStatusEnum = None

# 4. Import Logger
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')
    logger.info("Initialized basic logger for database.py.")

# 5. Import Settings
try:
    from app.utils.config import settings
    logger.info("Successfully imported settings in database.py")
    if not hasattr(settings, 'DATABASE_URL') or not settings.DATABASE_URL or \
       settings.DATABASE_URL == "ENV_VAR_DATABASE_URL_NOT_SET" or \
       not settings.DATABASE_URL.startswith(("postgresql://", "postgres://")):
        logger.critical("DATABASE_URL from settings is invalid. Falling back to OS env var.")
        SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
        if not SQLALCHEMY_DATABASE_URL:
            raise ValueError("FATAL ERROR: DATABASE_URL cannot be determined.")
    else:
        SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL
except ImportError:
    logger.critical("Could not import settings. Using DATABASE_URL from OS env var.")
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URL:
        raise ValueError("FATAL ERROR: DATABASE_URL not in OS env & settings import failed.")
except Exception as e_settings:
    logger.critical(f"Error accessing settings: {e_settings}. Using DATABASE_URL from OS env var.")
    SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")
    if not SQLALCHEMY_DATABASE_URL:
        raise ValueError("FATAL ERROR: DATABASE_URL not in OS env after settings error.")

# --- Engine and Session Setup ---
if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("FATAL ERROR: SQLALCHEMY_DATABASE_URL not set before engine creation.")

try:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
except Exception as e_engine:
    logger.error(f"FATAL ERROR: Could not create DB engine: {SQLALCHEMY_DATABASE_URL}", exc_info=True)
    raise SystemExit("DB engine creation failed.") from e_engine

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Schema Creation Function ---
def create_db_and_tables():
    if not Base:
        logger.error("CRITICAL: SQLAlchemy Base is None. Cannot create tables.")
        return
    logger.info("Attempting to create database tables (Base.metadata.create_all)...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created successfully.")
    except Exception as e:
        logger.error(f"ERROR creating database tables: {e}", exc_info=True)

# ==========================================
# ENCRYPTION FUNCTIONS
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None: return None
    return plain_text
def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None: return None
    return encrypted_text

# ==========================================
# ORGANIZATION CRUD
# ==========================================
def create_organization(db: Session, name: str) -> Optional[models.Organization]:
    if not models.Organization: logger.error("DB: Organization model not loaded."); return None
    try:
        existing_org = db.query(models.Organization).filter(models.Organization.name == name).first()
        if existing_org:
            logger.warning(f"Org '{name}' already exists. Returning ID: {existing_org.id}")
            return existing_org
        new_org = models.Organization(name=name)
        db.add(new_org); db.commit(); db.refresh(new_org)
        logger.info(f"Created org '{new_org.name}' ID: {new_org.id}")
        return new_org
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError creating org '{name}'. Fetching.")
        return db.query(models.Organization).filter(models.Organization.name == name).first()
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error creating org '{name}': {e}", exc_info=True); return None

def get_organization_by_id(db: Session, organization_id: int) -> Optional[models.Organization]:
    if not models.Organization: logger.error("DB: Organization model not loaded."); return None
    try: return db.query(models.Organization).filter(models.Organization.id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get org ID {organization_id}: {e}", exc_info=True); return None

def get_organization_by_name(db: Session, name: str) -> Optional[models.Organization]:
    if not models.Organization: logger.error("DB: Organization model not loaded."); return None
    try: return db.query(models.Organization).filter(models.Organization.name == name).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get org name '{name}': {e}", exc_info=True); return None

def get_all_organizations(db: Session) -> List[models.Organization]:
    if not models.Organization: logger.error("DB: Organization model not loaded."); return []
    try: return db.query(models.Organization).order_by(models.Organization.name).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get all orgs: {e}", exc_info=True); return []

# ==========================================
# USER CRUD
# ==========================================
def create_user(db: Session, email: str, hashed_password: str, organization_id: int,
                full_name: Optional[str] = None, is_active: bool = True, is_superuser: bool = False
               ) -> Optional[models.User]:
    if not models.User or not models.Organization: logger.error("DB: User/Org model not loaded for create_user."); return None
    try:
        if not db.query(models.Organization).filter(models.Organization.id == organization_id).first():
            logger.error(f"Org ID {organization_id} not found for user '{email}'."); return None
        existing_user = db.query(models.User).filter(models.User.email == email).first()
        if existing_user: logger.warning(f"User '{email}' already exists."); return existing_user

        new_user_obj = models.User(email=email, hashed_password=hashed_password, organization_id=organization_id,
                                   full_name=full_name, is_active=is_active, is_superuser=is_superuser)
        db.add(new_user_obj); db.commit(); db.refresh(new_user_obj)
        logger.info(f"Created user '{email}' (ID: {new_user_obj.id}) for org {organization_id}")
        return new_user_obj
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError creating user '{email}'.", exc_info=True)
        return db.query(models.User).filter(models.User.email == email).first()
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"SQLAlchemyError creating user '{email}': {e}", exc_info=True); return None

def get_user_by_id(db: Session, user_id: int) -> Optional[models.User]:
    if not models.User: logger.error("DB: User model not loaded."); return None
    try: return db.query(models.User).filter(models.User.id == user_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get user ID {user_id}: {e}", exc_info=True); return None

def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    if not models.User: logger.error("DB: User model not loaded."); return None
    try: return db.query(models.User).filter(models.User.email == email).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get user email {email}: {e}", exc_info=True); return None

def get_users_by_organization(db: Session, organization_id: int) -> List[models.User]:
    if not models.User: logger.error("DB: User model not loaded."); return []
    try: return db.query(models.User).filter(models.User.organization_id == organization_id).order_by(models.User.email).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get users for Org {organization_id}: {e}", exc_info=True); return []

# ==========================================
# LEAD CRUD
# ==========================================
def save_lead(db: Session, lead_data: Dict[str, Any], organization_id: int) -> Optional[models.Lead]:
    if not models.Lead: logger.error("DB: Lead model not loaded."); return None
    email = lead_data.get('email')
    if not email: logger.warning(f"Lead save skip: org {organization_id}, no email"); return None

    values_to_set = {
        "organization_id": organization_id, "email": email,
        "name": lead_data.get("name"), "company": lead_data.get("company"),
        "title": lead_data.get("title"), "source": lead_data.get("source"),
        "linkedin_profile": lead_data.get("linkedin_profile"), "company_size": lead_data.get("company_size"),
        "industry": lead_data.get("industry"), "location": lead_data.get("location"),
        "matched": bool(lead_data.get('matched', False)), "reason": lead_data.get("reason"),
        "crm_status": lead_data.get("crm_status", "pending"),
        "appointment_confirmed": bool(lead_data.get('appointment_confirmed', False)),
        "icp_match_id": lead_data.get("icp_match_id")
    }

    stmt = pg_insert(models.Lead).values(**values_to_set)
    update_on_conflict_dict = {
        col.key: getattr(stmt.excluded, col.key)
        for col in models.Lead.__table__.columns
        if col.key in values_to_set and col.key not in ['id', 'email', 'organization_id', 'created_at']
    }
    if update_on_conflict_dict: # Only add updated_at if there are fields to update
        update_on_conflict_dict['updated_at'] = func.now() # Use database function

    stmt = stmt.on_conflict_do_update(
        index_elements=[models.Lead.organization_id, models.Lead.email],
        set_=update_on_conflict_dict
    ).returning(models.Lead)

    try:
        result_proxy = db.execute(stmt)
        saved_lead_orm = result_proxy.scalar_one_or_none()
        db.commit()
        if saved_lead_orm: logger.debug(f"Saved/Updated lead ID {saved_lead_orm.id} for org {organization_id}")
        else: logger.error(f"Lead upsert failed to return object for org {organization_id}, email {email}")
        return saved_lead_orm
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error saving lead for org {organization_id}, email {email}: {e}", exc_info=True); return None

def _update_entity_fields(entity: Any, updates: Dict[str, Any], allowed_fields: set) -> bool:
    has_updates = False
    for key, value in updates.items():
        if key in allowed_fields:
            setattr(entity, key, value)
            has_updates = True
    return has_updates

def update_lead_partial(db: Session, lead_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.Lead]:
    if not models.Lead: logger.error("DB: Lead model not loaded."); return None
    try:
        lead = db.query(models.Lead).filter(models.Lead.id == lead_id, models.Lead.organization_id == organization_id).first()
        if not lead: logger.warning(f"Lead ID {lead_id} not found for org {organization_id} to update."); return None
        
        allowed = {"name", "company", "title", "source", "linkedin_profile", "company_size",
                   "industry", "location", "matched", "reason", "crm_status",
                   "appointment_confirmed", "icp_match_id"}
        if not _update_entity_fields(lead, updates, allowed):
            logger.info(f"No valid fields to update for lead {lead_id}."); return lead
        
        db.commit(); db.refresh(lead)
        logger.info(f"Partially updated lead ID {lead_id}")
        return lead
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error partial update lead {lead_id}: {e}", exc_info=True); return None

def get_lead_by_id(db: Session, lead_id: int, organization_id: int) -> Optional[models.Lead]:
    if not models.Lead: logger.error("DB: Lead model not loaded."); return None
    try: return db.query(models.Lead).filter(models.Lead.id == lead_id, models.Lead.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get lead ID {lead_id}: {e}", exc_info=True); return None

def get_lead_by_email(db: Session, email: str, organization_id: int) -> Optional[models.Lead]:
    if not models.Lead: logger.error("DB: Lead model not loaded."); return None
    try: return db.query(models.Lead).filter(models.Lead.email == email, models.Lead.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get lead email '{email}': {e}", exc_info=True); return None

def get_leads_by_organization(db: Session, organization_id: int, offset: int = 0, limit: int = 100) -> List[models.Lead]:
    if not models.Lead: logger.error("DB: Lead model not loaded."); return []
    try:
        return db.query(models.Lead).filter(models.Lead.organization_id == organization_id)\
            .order_by(models.Lead.created_at.desc()).offset(offset).limit(limit).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get leads for org {organization_id}: {e}", exc_info=True); return []

def delete_lead(db: Session, lead_id: int, organization_id: int) -> bool:
    if not models.Lead: logger.error("DB: Lead model not loaded."); return False
    try:
        lead = db.query(models.Lead).filter(models.Lead.id == lead_id, models.Lead.organization_id == organization_id).first()
        if lead: db.delete(lead); db.commit(); logger.info(f"Deleted lead ID {lead_id}"); return True
        logger.warning(f"Lead ID {lead_id} not found for delete."); return False
    except SQLAlchemyError as e: db.rollback(); logger.error(f"DB Error delete lead {lead_id}: {e}", exc_info=True); return False

# ==========================================
# ICP CRUD
# ==========================================
def create_icp(db: Session, organization_id: int, icp_definition: Dict[str, Any]) -> Optional[models.ICP]:
    if not models.ICP or not models.Organization: logger.error("DB: ICP/Org model not loaded for create_icp."); return None
    try:
        if not db.query(models.Organization).filter(models.Organization.id == organization_id).first():
            logger.error(f"Org ID {organization_id} not found for ICP creation."); return None
        if not icp_definition.get("name"): logger.error("ICP name required."); return None

        new_icp = models.ICP(
            organization_id=organization_id, name=icp_definition.get("name", "Default ICP"),
            title_keywords=icp_definition.get("title_keywords") or [],
            industry_keywords=icp_definition.get("industry_keywords") or [],
            company_size_rules=icp_definition.get("company_size_rules") or {},
            location_keywords=icp_definition.get("location_keywords") or []
        )
        db.add(new_icp); db.commit(); db.refresh(new_icp)
        logger.info(f"Created ICP '{new_icp.name}' (ID: {new_icp.id}) for Org {organization_id}")
        return new_icp
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError creating ICP '{icp_definition.get('name')}'.", exc_info=True)
        return db.query(models.ICP).filter(models.ICP.organization_id == organization_id, models.ICP.name == icp_definition.get("name")).first()
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error creating ICP: {e}", exc_info=True); return None

def get_icp_by_id(db: Session, icp_id: int, organization_id: int) -> Optional[models.ICP]:
    if not models.ICP: logger.error("DB: ICP model not loaded."); return None
    try: return db.query(models.ICP).filter(models.ICP.id == icp_id, models.ICP.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get ICP ID {icp_id}: {e}", exc_info=True); return None

def get_icps_by_organization_id(db: Session, organization_id: int) -> List[models.ICP]:
    if not models.ICP: logger.error("DB: ICP model not loaded."); return []
    try: return db.query(models.ICP).filter(models.ICP.organization_id == organization_id).order_by(models.ICP.name).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get ICPs for Org {organization_id}: {e}", exc_info=True); return []

def update_icp(db: Session, icp_id: int, organization_id: int, icp_definition: Dict[str, Any]) -> Optional[models.ICP]:
    if not models.ICP: logger.error("DB: ICP model not loaded."); return None
    try:
        icp = db.query(models.ICP).filter(models.ICP.id == icp_id, models.ICP.organization_id == organization_id).first()
        if not icp: logger.warning(f"ICP ID {icp_id} not found for update."); return None

        allowed_json = {"title_keywords", "industry_keywords", "company_size_rules", "location_keywords"}
        update_data = {}
        if "name" in icp_definition and icp_definition["name"] is not None:
            update_data["name"] = icp_definition["name"]
        for field in allowed_json:
            if field in icp_definition: # Update if key exists, allowing empty list/dict
                update_data[field] = icp_definition[field]

        if not update_data: logger.info(f"No valid fields to update for ICP {icp_id}."); return icp
        
        for key, value in update_data.items():
            setattr(icp, key, value)
            
        db.commit(); db.refresh(icp)
        logger.info(f"Updated ICP ID {icp_id}")
        return icp
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error updating ICP {icp_id}: {e}", exc_info=True); return None

def delete_icp(db: Session, icp_id: int, organization_id: int) -> bool:
    if not models.ICP: logger.error("DB: ICP model not loaded."); return False
    try:
        icp = db.query(models.ICP).filter(models.ICP.id == icp_id, models.ICP.organization_id == organization_id).first()
        if icp: db.delete(icp); db.commit(); logger.info(f"Deleted ICP ID {icp_id}"); return True
        logger.warning(f"ICP ID {icp_id} not found for delete."); return False
    except SQLAlchemyError as e: db.rollback(); logger.error(f"DB Error deleting ICP {icp_id}: {e}", exc_info=True); return False

# ==========================================
# OFFERING CRUD
# ==========================================
def create_offering(db: Session, organization_id: int, offering_data: Dict[str, Any]) -> Optional[models.Offering]:
    if not models.Offering or not models.Organization: logger.error("DB: Offering/Org model not loaded."); return None
    try:
        if not db.query(models.Organization).filter(models.Organization.id == organization_id).first():
            logger.error(f"Org ID {organization_id} not found for Offering creation."); return None
        if not offering_data.get("name"): logger.error("Offering name required."); return None

        new_offering = models.Offering(
            organization_id=organization_id, name=offering_data.get("name"),
            description=offering_data.get("description"),
            key_features=offering_data.get("key_features") or [],
            target_pain_points=offering_data.get("target_pain_points") or [],
            call_to_action=offering_data.get("call_to_action"),
            is_active=bool(offering_data.get("is_active", True))
        )
        db.add(new_offering); db.commit(); db.refresh(new_offering)
        logger.info(f"Created Offering '{new_offering.name}' (ID: {new_offering.id})")
        return new_offering
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError creating Offering '{offering_data.get('name')}'.", exc_info=True)
        return db.query(models.Offering).filter(models.Offering.name == offering_data.get("name"), models.Offering.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error creating Offering: {e}", exc_info=True); return None

def get_offering_by_id(db: Session, offering_id: int, organization_id: int) -> Optional[models.Offering]:
    if not models.Offering: logger.error("DB: Offering model not loaded."); return None
    try: return db.query(models.Offering).filter(models.Offering.id == offering_id, models.Offering.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get offering ID {offering_id}: {e}", exc_info=True); return None

def get_offerings_by_organization(db: Session, organization_id: int, active_only: bool = True) -> List[models.Offering]:
    if not models.Offering: logger.error("DB: Offering model not loaded."); return []
    try:
        query = db.query(models.Offering).filter(models.Offering.organization_id == organization_id)
        if active_only: query = query.filter(models.Offering.is_active == True)
        return query.order_by(models.Offering.name).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get offerings for Org {organization_id}: {e}", exc_info=True); return []

def update_offering(db: Session, offering_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.Offering]:
    if not models.Offering: logger.error("DB: Offering model not loaded."); return None
    try:
        offering = db.query(models.Offering).filter(models.Offering.id == offering_id, models.Offering.organization_id == organization_id).first()
        if not offering: logger.warning(f"Offering ID {offering_id} not found for update."); return None
        
        allowed = {"name", "description", "key_features", "target_pain_points", "call_to_action", "is_active"}
        if not _update_entity_fields(offering, updates, allowed):
            logger.info(f"No valid fields to update for Offering {offering_id}."); return offering
            
        db.commit(); db.refresh(offering)
        logger.info(f"Updated Offering ID {offering_id}")
        return offering
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError updating Offering {offering_id}.", exc_info=True); return None
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error updating Offering {offering_id}: {e}", exc_info=True); return None

def delete_offering(db: Session, offering_id: int, organization_id: int) -> bool:
    if not models.Offering: logger.error("DB: Offering model not loaded."); return False
    try:
        offering = db.query(models.Offering).filter(models.Offering.id == offering_id, models.Offering.organization_id == organization_id).first()
        if offering: db.delete(offering); db.commit(); logger.info(f"Deleted Offering ID {offering_id}"); return True
        logger.warning(f"Offering ID {offering_id} not found for delete."); return False
    except SQLAlchemyError as e: db.rollback(); logger.error(f"DB Error deleting Offering {offering_id}: {e}", exc_info=True); return False

# ===========================================================
# CAMPAIGN CRUD
# ===========================================================
def create_campaign(db: Session, organization_id: int, name: str, description: Optional[str] = None,
                    is_active: bool = False, icp_id: Optional[int] = None,
                    offering_id: Optional[int] = None, ai_status: str = "pending") -> Optional[models.EmailCampaign]:
    if not models.EmailCampaign or not models.Organization or not models.ICP or not models.Offering:
        logger.error("DB: Models missing for create_campaign."); return None
    try:
        if not db.query(models.Organization).filter(models.Organization.id == organization_id).first():
            logger.error(f"Org ID {organization_id} not found for campaign."); return None
        if icp_id and not db.query(models.ICP).filter(models.ICP.id == icp_id, models.ICP.organization_id == organization_id).first():
            logger.warning(f"ICP ID {icp_id} not found for campaign (Org {organization_id})."); return None
        if offering_id and not db.query(models.Offering).filter(models.Offering.id == offering_id, models.Offering.organization_id == organization_id).first():
            logger.warning(f"Offering ID {offering_id} not found for campaign (Org {organization_id})."); return None

        new_campaign = models.EmailCampaign(
            organization_id=organization_id, name=name, description=description, is_active=is_active,
            icp_id=icp_id, offering_id=offering_id, ai_status=ai_status
        )
        db.add(new_campaign); db.commit(); db.refresh(new_campaign)
        logger.info(f"Created campaign '{name}' (ID: {new_campaign.id}) for Org {organization_id}")
        return new_campaign
    except IntegrityError as e:
        db.rollback(); logger.error(f"DB IntegrityError creating campaign '{name}': {e}", exc_info=True); return None
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error creating campaign '{name}': {e}", exc_info=True); return None

def get_campaign_by_id(db: Session, campaign_id: int, organization_id: int) -> Optional[models.EmailCampaign]:
    if not models.EmailCampaign: logger.error("DB: EmailCampaign model not loaded."); return None
    try:
        return db.query(models.EmailCampaign).filter(models.EmailCampaign.id == campaign_id, models.EmailCampaign.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get campaign ID {campaign_id}: {e}", exc_info=True); return None

def get_campaign_with_details_by_id(db: Session, campaign_id: int, organization_id: int) -> Optional[Dict]:
    if not models.EmailCampaign or not models.ICP or not models.Offering: logger.error("DB: Models missing for campaign details."); return None
    try:
        result = db.query(
                models.EmailCampaign, models.ICP.name.label("icp_name"), models.Offering.name.label("offering_name")
            ).outerjoin(models.ICP, models.EmailCampaign.icp_id == models.ICP.id)\
             .outerjoin(models.Offering, models.EmailCampaign.offering_id == models.Offering.id)\
             .filter(models.EmailCampaign.id == campaign_id, models.EmailCampaign.organization_id == organization_id).first()
        if result:
            campaign_obj, icp_name, offering_name = result
            campaign_dict = {c.key: getattr(campaign_obj, c.key) for c in inspect(campaign_obj).mapper.column_attrs}
            campaign_dict["icp_name"] = icp_name
            campaign_dict["offering_name"] = offering_name
            return campaign_dict
        return None
    except SQLAlchemyError as e: logger.error(f"DB Error get campaign details ID {campaign_id}: {e}", exc_info=True); return None

def get_campaigns_by_organization(db: Session, organization_id: int, active_only: Optional[bool] = None) -> List[models.EmailCampaign]:
    if not models.EmailCampaign: logger.error("DB: EmailCampaign model not loaded."); return []
    try:
        query = db.query(models.EmailCampaign).filter(models.EmailCampaign.organization_id == organization_id)
        if active_only is not None: query = query.filter(models.EmailCampaign.is_active == active_only)
        return query.order_by(models.EmailCampaign.name).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get campaigns for Org {organization_id}: {e}", exc_info=True); return []

def update_campaign(db: Session, campaign_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.EmailCampaign]:
    if not models.EmailCampaign: logger.error("DB: EmailCampaign model not loaded."); return None
    try:
        campaign = db.query(models.EmailCampaign).filter(models.EmailCampaign.id == campaign_id, models.EmailCampaign.organization_id == organization_id).first()
        if not campaign: logger.warning(f"Campaign ID {campaign_id} not found for update."); return None
        allowed = {"name", "description", "is_active", "icp_id", "offering_id", "ai_status"}
        if not _update_entity_fields(campaign, updates, allowed): logger.info(f"No valid fields for campaign {campaign_id}."); return campaign
        db.commit(); db.refresh(campaign); logger.info(f"Updated campaign ID {campaign_id}"); return campaign
    except SQLAlchemyError as e: db.rollback(); logger.error(f"DB Error update campaign {campaign_id}: {e}", exc_info=True); return None

def update_campaign_ai_status(db: Session, campaign_id: int, organization_id: int, ai_status: str) -> Optional[models.EmailCampaign]:
    return update_campaign(db, campaign_id, organization_id, {"ai_status": ai_status})

def delete_campaign(db: Session, campaign_id: int, organization_id: int) -> bool:
    if not models.EmailCampaign: logger.error("DB: EmailCampaign model not loaded."); return False
    try:
        campaign = db.query(models.EmailCampaign).filter(models.EmailCampaign.id == campaign_id, models.EmailCampaign.organization_id == organization_id).first()
        if campaign: db.delete(campaign); db.commit(); logger.info(f"Deleted campaign ID {campaign_id}"); return True
        logger.warning(f"Campaign ID {campaign_id} not found for delete."); return False
    except SQLAlchemyError as e: db.rollback(); logger.error(f"DB Error delete campaign {campaign_id}: {e}", exc_info=True); return False

# ===========================================================
# CAMPAIGN STEP CRUD
# ===========================================================
def create_campaign_step(db: Session, campaign_id: int, organization_id: int, step_number: int, delay_days: int,
                         subject_template: str, body_template: str,
                         is_ai_crafted: bool = False, follow_up_angle: Optional[str] = None) -> Optional[models.CampaignStep]:
    if not models.CampaignStep or not models.EmailCampaign: logger.error("DB: Models missing for create_campaign_step."); return None
    try:
        parent_campaign = db.query(models.EmailCampaign).filter(models.EmailCampaign.id == campaign_id, models.EmailCampaign.organization_id == organization_id).first()
        if not parent_campaign: logger.error(f"Campaign {campaign_id} (Org {organization_id}) not found for step."); return None

        new_step = models.CampaignStep(
            campaign_id=campaign_id, organization_id=organization_id, step_number=step_number,
            delay_days=delay_days, subject_template=subject_template, body_template=body_template,
            is_ai_crafted=is_ai_crafted, follow_up_angle=follow_up_angle
        )
        db.add(new_step); db.commit(); db.refresh(new_step)
        logger.info(f"Created step {step_number} (ID: {new_step.id}) for Campaign {campaign_id}")
        return new_step
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError: Step {step_number} likely exists for Camp {campaign_id}.")
        return db.query(models.CampaignStep).filter(models.CampaignStep.campaign_id == campaign_id, models.CampaignStep.step_number == step_number).first()
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error create step {step_number} for Camp {campaign_id}: {e}", exc_info=True); return None

def get_campaign_step_by_id(db: Session, step_id: int, organization_id: int) -> Optional[models.CampaignStep]:
    if not models.CampaignStep: logger.error("DB: CampaignStep model not loaded."); return None
    try: return db.query(models.CampaignStep).filter(models.CampaignStep.id == step_id, models.CampaignStep.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get step ID {step_id}: {e}", exc_info=True); return None

def get_steps_for_campaign(db: Session, campaign_id: int, organization_id: int) -> List[models.CampaignStep]:
    if not models.CampaignStep: logger.error("DB: CampaignStep model not loaded."); return []
    try:
        return db.query(models.CampaignStep).filter(models.CampaignStep.campaign_id == campaign_id, models.CampaignStep.organization_id == organization_id)\
            .order_by(models.CampaignStep.step_number).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get steps for Camp {campaign_id}, Org {organization_id}: {e}", exc_info=True); return []

def get_next_campaign_step(db: Session, campaign_id: int, organization_id: int, current_step_number: int) -> Optional[models.CampaignStep]:
    if not models.CampaignStep: logger.error("DB: CampaignStep model not loaded."); return None
    next_step_no = current_step_number + 1
    try:
        return db.query(models.CampaignStep).filter(
            models.CampaignStep.campaign_id == campaign_id,
            models.CampaignStep.organization_id == organization_id,
            models.CampaignStep.step_number == next_step_no
        ).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get next campaign step: {e}", exc_info=True); return None

def update_campaign_step(db: Session, step_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.CampaignStep]:
    if not models.CampaignStep: logger.error("DB: CampaignStep model not loaded."); return None
    try:
        step = db.query(models.CampaignStep).filter(models.CampaignStep.id == step_id, models.CampaignStep.organization_id == organization_id).first()
        if not step: logger.warning(f"CampaignStep ID {step_id} not found for update."); return None
        allowed = {"step_number", "delay_days", "subject_template", "body_template", "is_ai_crafted", "follow_up_angle"}
        if not _update_entity_fields(step, updates, allowed): logger.info(f"No valid fields for step {step_id}."); return step
        db.commit(); db.refresh(step); logger.info(f"Updated step ID {step_id}"); return step
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError updating step {step_id}.", exc_info=True); return None
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error update step {step_id}: {e}", exc_info=True); return None

def delete_campaign_step(db: Session, step_id: int, organization_id: int) -> bool:
    if not models.CampaignStep: logger.error("DB: CampaignStep model not loaded."); return False
    try:
        step = db.query(models.CampaignStep).filter(models.CampaignStep.id == step_id, models.CampaignStep.organization_id == organization_id).first()
        if step: db.delete(step); db.commit(); logger.info(f"Deleted step ID {step_id}"); return True
        logger.warning(f"Step ID {step_id} not found for delete."); return False
    except SQLAlchemyError as e: db.rollback(); logger.error(f"DB Error delete step {step_id}: {e}", exc_info=True); return False

# ===========================================================
# LEAD CAMPAIGN STATUS CRUD
# ===========================================================
def enroll_lead_in_campaign(db: Session, lead_id: int, campaign_id: int, organization_id: int) -> Optional[models.LeadCampaignStatus]:
    if not models.LeadCampaignStatus or not models.Lead or not models.EmailCampaign: logger.error("DB: Models missing for enroll_lead."); return None
    try:
        if not db.query(models.Lead).filter(models.Lead.id == lead_id, models.Lead.organization_id == organization_id).first():
            logger.warning(f"Lead {lead_id} not found for enrollment in Org {organization_id}."); return None
        if not db.query(models.EmailCampaign).filter(models.EmailCampaign.id == campaign_id, models.EmailCampaign.organization_id == organization_id).first():
            logger.warning(f"Campaign {campaign_id} not found for enrollment in Org {organization_id}."); return None

        # Check if LeadStatusEnum was imported successfully
        if LeadStatusEnum is None: logger.error("DB: LeadStatusEnum not available for enroll_lead."); return None

        new_status = models.LeadCampaignStatus(
            lead_id=lead_id, campaign_id=campaign_id, organization_id=organization_id,
            status=LeadStatusEnum.active.value, # Use .value if status column stores string
            current_step_number=0,
            next_email_due_at=datetime.now(timezone.utc)
        )
        db.add(new_status); db.commit(); db.refresh(new_status)
        logger.info(f"Enrolled Lead {lead_id} in Campaign {campaign_id} (Status ID: {new_status.id})")
        return new_status
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError: Lead {lead_id} already enrolled or bad FK.", exc_info=True)
        return db.query(models.LeadCampaignStatus).filter(models.LeadCampaignStatus.lead_id == lead_id, models.LeadCampaignStatus.organization_id == organization_id).first()
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error enroll lead {lead_id} in camp {campaign_id}: {e}", exc_info=True); return None

def update_lead_campaign_status(db: Session, status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[models.LeadCampaignStatus]:
    if not models.LeadCampaignStatus: logger.error("DB: LeadCampaignStatus model not loaded."); return None
    try:
        status_obj = db.query(models.LeadCampaignStatus).filter(models.LeadCampaignStatus.id == status_id, models.LeadCampaignStatus.organization_id == organization_id).first()
        if not status_obj: logger.warning(f"LCS ID {status_id} not found for update."); return None
        
        allowed = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", 
                   "last_response_type", "last_response_at", "error_message", "user_notes"}
        # Ensure 'status' update uses enum's value if model stores string
        if "status" in updates and isinstance(updates["status"], LeadStatusEnum):
            updates["status"] = updates["status"].value

        if not _update_entity_fields(status_obj, updates, allowed):
            logger.info(f"No valid fields to update for LCS {status_id}."); return status_obj
            
        db.commit(); db.refresh(status_obj); logger.info(f"Updated LCS ID {status_id}")
        return status_obj
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error update LCS {status_id}: {e}", exc_info=True); return None

def get_active_leads_due_for_step(db: Session, organization_id: Optional[int] = None, query_limit: int = 100) -> List[models.LeadCampaignStatus]:
    if not models.LeadCampaignStatus or not models.Lead or not models.EmailCampaign or not LeadStatusEnum:
        logger.error("DB: Models/Enums missing for get_active_leads_due_for_step.")
        return []
    try:
        query = db.query(models.LeadCampaignStatus).\
            join(models.Lead, models.LeadCampaignStatus.lead_id == models.Lead.id).\
            join(models.EmailCampaign, models.LeadCampaignStatus.campaign_id == models.EmailCampaign.id).\
            filter(models.LeadCampaignStatus.status == LeadStatusEnum.active.value).\
            filter(or_(
                models.LeadCampaignStatus.next_email_due_at <= datetime.now(timezone.utc),
                and_(models.LeadCampaignStatus.next_email_due_at.is_(None), models.LeadCampaignStatus.current_step_number == 0)
            ))

        if organization_id is not None:
            query = query.filter(models.LeadCampaignStatus.organization_id == organization_id)

        leads_due = query.order_by(
                models.LeadCampaignStatus.organization_id,
                models.LeadCampaignStatus.next_email_due_at.asc().nulls_first(),
                models.LeadCampaignStatus.created_at.asc()
            ).limit(query_limit).all()
        logger.debug(f"DB: Found {len(leads_due)} active leads due for step.")
        return leads_due
    except AttributeError as ae: # If created_at or other attribute is missing from model
        logger.error(f"DB Model AttributeError in get_active_leads_due_for_step: {ae}", exc_info=True)
        return []
    except SQLAlchemyError as e:
        logger.error(f"DB SQLAlchemyError in get_active_leads_due_for_step: {e}", exc_info=True)
        return []

def get_lead_campaign_status_by_id(db: Session, status_id: int, organization_id: int) -> Optional[models.LeadCampaignStatus]:
    if not models.LeadCampaignStatus: logger.error("DB: LeadCampaignStatus model not loaded."); return None
    try: return db.query(models.LeadCampaignStatus).filter(models.LeadCampaignStatus.id == status_id, models.LeadCampaignStatus.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get LCS ID {status_id}: {e}", exc_info=True); return None

def get_lead_campaign_status(db: Session, lead_id: int, organization_id: int) -> Optional[models.LeadCampaignStatus]:
    if not models.LeadCampaignStatus: logger.error("DB: LeadCampaignStatus model not loaded."); return None
    try: return db.query(models.LeadCampaignStatus).filter(models.LeadCampaignStatus.lead_id == lead_id, models.LeadCampaignStatus.organization_id == organization_id).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get LCS for lead {lead_id}: {e}", exc_info=True); return None

# ==========================================
# ORGANIZATION EMAIL SETTINGS CRUD
# ==========================================
def save_org_email_settings(db: Session, organization_id: int, settings_data: Dict[str, Any]) -> Optional[models.OrganizationEmailSettings]:
    if not models.OrganizationEmailSettings or not models.Organization: logger.error("DB: Models missing for save_org_email_settings."); return None
    try:
        if not db.query(models.Organization).filter(models.Organization.id == organization_id).first():
            logger.error(f"Org ID {organization_id} not found for email settings."); return None
        if not settings_data.get("verified_sender_email") or not settings_data.get("provider_type"):
            logger.error("verified_sender_email and provider_type required for email settings."); return None

        # Prepare values for model, encrypting sensitive data
        # Ensure all fields match the OrganizationEmailSettings model
        values = {
            "organization_id": organization_id,
            "provider_type": settings_data.get("provider_type"),
            "smtp_host": settings_data.get("smtp_host"),
            "smtp_port": int(settings_data["smtp_port"]) if settings_data.get("smtp_port") is not None else None,
            "smtp_username": settings_data.get("smtp_username"),
            "encrypted_smtp_password": _encrypt_data(settings_data.get("smtp_password")),
            "encrypted_api_key": _encrypt_data(settings_data.get("encrypted_api_key")), # Match model field name
            "encrypted_secret_key": _encrypt_data(settings_data.get("encrypted_secret_key")), # Match model field name
            "encrypted_access_token": _encrypt_data(settings_data.get("encrypted_access_token")),
            "encrypted_refresh_token": _encrypt_data(settings_data.get("encrypted_refresh_token")),
            "token_expiry": settings_data.get("token_expiry"),
            "aws_region": settings_data.get("aws_region"), # Match model field name
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
        }

        stmt = pg_insert(models.OrganizationEmailSettings).values(**values)
        update_values = {col.key: getattr(stmt.excluded, col.key)
                         for col in models.OrganizationEmailSettings.__table__.columns
                         if col.key in values and col.key != 'organization_id' and col.key != 'id' and col.key != 'created_at'}
        if update_values: # Only set updated_at if there's something to update
            update_values['updated_at'] = func.now()

        stmt = stmt.on_conflict_do_update(
            index_elements=[models.OrganizationEmailSettings.organization_id],
            set_=update_values
        ).returning(models.OrganizationEmailSettings)

        result_proxy = db.execute(stmt)
        saved_settings_orm = result_proxy.scalar_one_or_none()
        db.commit()

        if saved_settings_orm: logger.info(f"Saved/Updated Email Settings for Org ID: {organization_id}")
        else: logger.error(f"Email settings upsert failed for Org {organization_id}")
        return saved_settings_orm
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error saving email settings for Org {organization_id}: {e}", exc_info=True); return None

def get_org_email_settings_from_db(db: Session, organization_id: int, decrypt: bool = True) -> Optional[models.OrganizationEmailSettings]:
    if not models.OrganizationEmailSettings: logger.error("DB: OrgEmailSettings model not loaded."); return None
    try:
        settings_obj = db.query(models.OrganizationEmailSettings).filter(models.OrganizationEmailSettings.organization_id == organization_id).first()
        if settings_obj and decrypt:
            # Add transient decrypted attributes
            setattr(settings_obj, 'smtp_password', _decrypt_data(getattr(settings_obj, 'encrypted_smtp_password', None)))
            setattr(settings_obj, 'api_key', _decrypt_data(getattr(settings_obj, 'encrypted_api_key', None))) # Assuming 'api_key' maps to encrypted_api_key
            setattr(settings_obj, 'secret_key', _decrypt_data(getattr(settings_obj, 'encrypted_secret_key', None)))
            setattr(settings_obj, 'access_token', _decrypt_data(getattr(settings_obj, 'encrypted_access_token', None)))
            setattr(settings_obj, 'refresh_token', _decrypt_data(getattr(settings_obj, 'encrypted_refresh_token', None)))
            setattr(settings_obj, 'imap_password', _decrypt_data(getattr(settings_obj, 'encrypted_imap_password', None)))
        return settings_obj
    except SQLAlchemyError as e: logger.error(f"DB Error get email settings for Org {organization_id}: {e}", exc_info=True); return None

# ==========================================
# LEAD & IMAP RELATED QUERIES
# ==========================================
def get_leads_by_icp_match(db: Session, organization_id: int, icp_id: int, limit: int = 1000) -> List[models.Lead]:
    if not models.Lead or not models.ICP: logger.error("DB: Lead/ICP model not loaded."); return []
    try:
        return db.query(models.Lead).filter(
            models.Lead.organization_id == organization_id,
            models.Lead.icp_match_id == icp_id, # Ensure Lead model has icp_match_id
            models.Lead.matched == True
        ).order_by(models.Lead.created_at.desc()).limit(limit).all()
    except SQLAlchemyError as e: logger.error(f"DB Error get leads by ICP for Org {organization_id}, ICP {icp_id}: {e}", exc_info=True); return []

def get_organizations_with_imap_enabled(db: Session, limit: int = 1000) -> List[models.OrganizationEmailSettings]:
    if not models.OrganizationEmailSettings: logger.error("DB: OrgEmailSettings model not loaded."); return []
    try:
        query = db.query(models.OrganizationEmailSettings).filter(
            models.OrganizationEmailSettings.is_configured == True,
            models.OrganizationEmailSettings.enable_reply_detection == True,
            models.OrganizationEmailSettings.imap_host.isnot(None), 
            models.OrganizationEmailSettings.imap_host != '',
            models.OrganizationEmailSettings.imap_username.isnot(None),
            models.OrganizationEmailSettings.imap_username != '',
            models.OrganizationEmailSettings.encrypted_imap_password.isnot(None),
            models.OrganizationEmailSettings.encrypted_imap_password != ''
        )
        settings_list = query.limit(limit).all()

        for settings_obj in settings_list:
            if hasattr(settings_obj, 'encrypted_imap_password'):
                setattr(settings_obj, 'imap_password', _decrypt_data(settings_obj.encrypted_imap_password))
            else: setattr(settings_obj, 'imap_password', None)
        
        if not settings_list: logger.info("DB: No orgs found with IMAP enabled criteria.")
        else: logger.info(f"DB: Found {len(settings_list)} orgs for IMAP.")
        return settings_list
    except SQLAlchemyError as e:
        logger.error(f"DB Error fetching orgs with IMAP: {e}", exc_info=True)
        return []

def update_organization_email_settings_field(db: Session, organization_id: int, updates: Dict[str, Any]) -> bool:
    if not models.OrganizationEmailSettings: logger.error("DB: OrgEmailSettings model not loaded."); return False
    try:
        settings = db.query(models.OrganizationEmailSettings).filter(models.OrganizationEmailSettings.organization_id == organization_id).first()
        if not settings: logger.warning(f"No org email settings for org {organization_id} to update."); return False

        allowed = {"last_imap_poll_uid", "last_imap_poll_timestamp", "enable_reply_detection", "is_configured"}
        if not _update_entity_fields(settings, updates, allowed):
            logger.info(f"No valid fields for org email settings update (Org {organization_id})."); return False
            
        db.commit(); logger.info(f"Updated org email settings fields for Org {organization_id}")
        return True
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error update org email settings fields for Org {organization_id}: {e}", exc_info=True); return False

# ==========================================
# REPLY HANDLING CRUD
# ==========================================
def log_sent_email(db: Session, lead_campaign_status_id: Optional[int], organization_id: int, lead_id: int, # LCS ID can be optional
                   campaign_id: int, campaign_step_id: Optional[int], message_id_header: str, # Step ID can be optional
                   to_email: str, subject: str) -> Optional[models.OutgoingEmailLog]:
    if not models.OutgoingEmailLog: logger.error("DB: OutgoingEmailLog model not loaded."); return None
    try:
        new_log = models.OutgoingEmailLog(
            lead_campaign_status_id=lead_campaign_status_id, organization_id=organization_id,
            lead_id=lead_id, campaign_id=campaign_id, campaign_step_id=campaign_step_id,
            message_id_header=message_id_header, to_email=to_email, subject=subject
        )
        db.add(new_log); db.commit(); db.refresh(new_log)
        logger.info(f"Logged sent email: LCS_ID {lead_campaign_status_id}, MsgID: {message_id_header}")
        return new_log
    except IntegrityError:
        db.rollback(); logger.warning(f"IntegrityError: MsgID '{message_id_header}' for org {organization_id} likely exists.")
        return db.query(models.OutgoingEmailLog).filter(
            models.OutgoingEmailLog.organization_id == organization_id,
            models.OutgoingEmailLog.message_id_header == message_id_header
        ).first()
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error logging sent email: {e}", exc_info=True); return None

def store_email_reply(db: Session, reply_data: Dict[str, Any]) -> Optional[models.EmailReply]:
    if not models.EmailReply: logger.error("DB: EmailReply model not loaded."); return None
    
    required_fields = ["organization_id", "lead_id", "received_at", "from_email"] # LCS_id, campaign_id can be optional
    if not all(reply_data.get(f) is not None for f in required_fields):
        logger.error(f"Missing required fields for storing email reply: {reply_data}. Required: {required_fields}")
        return None

    try:
        # Ensure ai_extracted_entities is a dict/list or None for JSONB
        ai_entities = reply_data.get("ai_extracted_entities")
        if ai_entities is not None and not isinstance(ai_entities, (dict, list)):
            logger.warning(f"Attempting to store non-dict/list ai_extracted_entities of type {type(ai_entities)}. Setting to None.")
            ai_entities = None

        new_reply_params = {
            "outgoing_email_log_id": reply_data.get("outgoing_email_log_id"),
            "lead_campaign_status_id": reply_data.get("lead_campaign_status_id"), # Allow None
            "organization_id": reply_data["organization_id"],
            "lead_id": reply_data["lead_id"],
            "campaign_id": reply_data.get("campaign_id"), # Allow None
            "received_at": reply_data["received_at"],
            "from_email": reply_data["from_email"],
            "reply_subject": reply_data.get("reply_subject"),
            "raw_body_text": reply_data.get("raw_body_text"),
            "cleaned_reply_text": reply_data.get("cleaned_reply_text"),
            "ai_classification": reply_data.get("ai_classification"), # Assumes string value of enum
            "ai_summary": reply_data.get("ai_summary"),
            "ai_extracted_entities": ai_entities,
            "is_actioned_by_user": bool(reply_data.get("is_actioned_by_user", False)),
            "user_action_notes": reply_data.get("user_action_notes"),
        }
        new_reply = models.EmailReply(**new_reply_params)
        db.add(new_reply); db.commit(); db.refresh(new_reply)
        logger.info(f"Stored email reply ID {new_reply.id} from {new_reply.from_email}")
        return new_reply
    except SQLAlchemyError as e:
        db.rollback(); logger.error(f"DB Error storing email reply: {e}", exc_info=True); return None

def get_outgoing_email_log_by_message_id(db: Session, organization_id: int, message_id_header: str) -> Optional[models.OutgoingEmailLog]:
    if not models.OutgoingEmailLog: logger.error("DB: OutgoingEmailLog model not loaded."); return None
    try:
        return db.query(models.OutgoingEmailLog).filter(
            models.OutgoingEmailLog.organization_id == organization_id,
            models.OutgoingEmailLog.message_id_header == message_id_header
        ).first()
    except SQLAlchemyError as e: logger.error(f"DB Error get outgoing log by MsgID: {e}", exc_info=True); return None

# ==========================================
# DASHBOARD & ANALYTICS QUERIES
# ==========================================
def get_leads_with_positive_status_for_dashboard(db: Session, organization_id: int, limit: int = 100) -> List[Dict]:
    if not models.LeadCampaignStatus or not models.Lead or not models.EmailCampaign or not models.EmailReply or not LeadStatusEnum:
        logger.error("DB: Models/Enums missing for dashboard query."); return []

    actionable_statuses = [
        LeadStatusEnum.positive_reply_ai_flagged.value, LeadStatusEnum.question_ai_flagged.value,
        LeadStatusEnum.appointment_manually_set.value, LeadStatusEnum.positive_reply_received.value,
        LeadStatusEnum.manual_follow_up_needed.value
    ]
    # This query is complex and requires careful construction for ORM or might be better as a view/raw SQL for performance.
    # The N+1 query pattern for latest_reply is inefficient for large datasets.
    # Consider using a window function with a subquery if performance becomes an issue.
    try:
        base_query = db.query(
                models.LeadCampaignStatus.id.label("lead_campaign_status_id"),
                models.Lead.id.label("lead_id"), models.EmailCampaign.id.label("campaign_id"),
                models.LeadCampaignStatus.organization_id, models.LeadCampaignStatus.status.label("lead_campaign_status"),
                models.LeadCampaignStatus.last_response_type, models.LeadCampaignStatus.last_response_at,
                models.LeadCampaignStatus.user_notes, models.LeadCampaignStatus.updated_at.label("status_updated_at"),
                models.Lead.name.label("lead_name"), models.Lead.email.label("lead_email"),
                models.Lead.company.label("lead_company"), models.EmailCampaign.name.label("campaign_name")
            ).join(models.Lead, models.Lead.id == models.LeadCampaignStatus.lead_id)\
             .join(models.EmailCampaign, models.EmailCampaign.id == models.LeadCampaignStatus.campaign_id)\
             .filter(models.LeadCampaignStatus.organization_id == organization_id)\
             .filter(models.LeadCampaignStatus.status.in_(actionable_statuses))\
             .order_by(models.LeadCampaignStatus.updated_at.desc()).limit(limit)

        results = base_query.all()
        dashboard_items = []
        for row_proxy in results:
            item = dict(row_proxy._asdict()) # Convert RowProxy to dict
            latest_reply = db.query(models.EmailReply)\
                .filter(models.EmailReply.lead_campaign_status_id == item['lead_campaign_status_id'])\
                .order_by(models.EmailReply.received_at.desc()).first()
            if latest_reply:
                item['latest_reply_id'] = latest_reply.id
                item['latest_reply_snippet'] = (latest_reply.cleaned_reply_text or "")[:250]
                item['latest_reply_ai_summary'] = latest_reply.ai_summary
                item['latest_reply_ai_classification'] = latest_reply.ai_classification
                item['latest_reply_received_at'] = latest_reply.received_at
            else: # Initialize keys if no reply
                item.update({k: None for k in ['latest_reply_id', 'latest_reply_snippet', 'latest_reply_ai_summary',
                                               'latest_reply_ai_classification', 'latest_reply_received_at']})
            dashboard_items.append(item)
        return dashboard_items
    except SQLAlchemyError as e: logger.error(f"DB Error get positive status for dashboard (Org {organization_id}): {e}", exc_info=True); return []
def get_actionable_email_replies(db: Session, organization_id: int, limit: int = 50) -> List[Dict]:
    """
    Fetches email replies that are marked as unactioned by the user and have
    an AI classification indicating they need review or action.
    Returns a list of dictionaries with relevant information for the dashboard.
    """
    if not models.EmailReply or not models.Lead or not models.EmailCampaign or not models.LeadCampaignStatus or not LeadStatusEnum:
        logger.error("DB: One or more models/enums missing for get_actionable_email_replies.")
        return []

    # Define AI classifications that are considered "actionable" for the dashboard
    # This list might need adjustment based on your AIClassificationEnum and business logic
    actionable_ai_classifications = [
        # AIClassificationEnum.positive_interest.value, # Assuming you have this enum
        # AIClassificationEnum.question.value,
        # AIClassificationEnum.objection.value,
        # Add any other AI classifications that require user attention
        "positive_interest", # Using strings if your model stores strings
        "question",
        "objection",
        "positive_reply_ai_flagged", # This might come from LeadCampaignStatus
        "question_ai_flagged"        # This might come from LeadCampaignStatus
    ]
    
    # Define LeadCampaignStatus statuses that are also relevant for showing actionable items
    # (e.g., if an AI classification directly sets the LCS status)
    actionable_lcs_statuses = [
        LeadStatusEnum.positive_reply_ai_flagged.value,
        LeadStatusEnum.question_ai_flagged.value,
        LeadStatusEnum.manual_follow_up_needed.value
    ]

    try:
        # We want to join EmailReply with Lead, EmailCampaign, and potentially LeadCampaignStatus
        # to get all necessary context for the dashboard.
        query = db.query(
            models.EmailReply.id.label("reply_id"),
            models.EmailReply.received_at.label("reply_received_at"),
            models.EmailReply.cleaned_reply_text.label("reply_snippet"), # You might want full text or better snippet logic
            models.EmailReply.ai_classification.label("reply_ai_classification"),
            models.EmailReply.ai_summary.label("reply_ai_summary"),
            models.Lead.id.label("lead_id"),
            models.Lead.name.label("lead_name"),
            models.Lead.email.label("lead_email"),
            models.Lead.company.label("lead_company"),
            models.EmailCampaign.id.label("campaign_id"),
            models.EmailCampaign.name.label("campaign_name"),
            models.LeadCampaignStatus.status.label("lead_campaign_status") # Current status of the lead in the campaign
        ).select_from(models.EmailReply)\
         .join(models.Lead, models.EmailReply.lead_id == models.Lead.id)\
         .outerjoin(models.EmailCampaign, models.EmailReply.campaign_id == models.EmailCampaign.id) \
         .outerjoin(models.LeadCampaignStatus, models.EmailReply.lead_campaign_status_id == models.LeadCampaignStatus.id) \
         .filter(models.EmailReply.organization_id == organization_id)\
         .filter(models.EmailReply.is_actioned_by_user == False) \
         .filter(
             or_(
                 models.EmailReply.ai_classification.in_(actionable_ai_classifications),
                 models.LeadCampaignStatus.status.in_(actionable_lcs_statuses) # Also consider LCS status
             )
         )

        # Order by most recent replies first
        results = query.order_by(models.EmailReply.received_at.desc()).limit(limit).all()

        actionable_items = []
        for row in results:
            item = dict(row._asdict()) # Convert RowProxy to dict
            # Further process snippet if needed
            if item.get("reply_snippet"):
                item["reply_snippet"] = item["reply_snippet"][:250] + "..." if len(item["reply_snippet"]) > 250 else item["reply_snippet"]
            actionable_items.append(item)
        
        logger.info(f"DB: Found {len(actionable_items)} actionable replies for Org ID {organization_id}.")
        return actionable_items

    except AttributeError as ae: # Catch if a model is missing an expected attribute
        logger.error(f"DB Model AttributeError in get_actionable_email_replies: {ae}", exc_info=True)
        return []
    except SQLAlchemyError as e:
        logger.error(f"DB SQLAlchemyError in get_actionable_email_replies for Org ID {organization_id}: {e}", exc_info=True)
        return []


def count_appointments_set(db: Session, organization_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
    if not models.Lead: logger.error("DB: Lead model not loaded."); return 0
    try:
        query = db.query(func.count(models.Lead.id)).filter(
            models.Lead.organization_id == organization_id, models.Lead.appointment_confirmed == True
        )
        if start_date: query = query.filter(models.Lead.updated_at >= start_date)
        if end_date: query = query.filter(models.Lead.updated_at <= end_date)
        return query.scalar() or 0
    except SQLAlchemyError as e: logger.error(f"DB Error count appointments: {e}", exc_info=True); return 0

def count_positive_replies_status(db: Session, organization_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
    if not models.LeadCampaignStatus or not models.Lead or not LeadStatusEnum: logger.error("DB: Models/Enums missing for count_pos_replies."); return 0
    positive_statuses = [
        LeadStatusEnum.positive_reply_ai_flagged.value, LeadStatusEnum.positive_reply_received.value,
        # Add other statuses that count as "positive reply" for this metric
    ]
    try:
        query = db.query(func.count(models.LeadCampaignStatus.id))\
            .join(models.Lead, models.Lead.id == models.LeadCampaignStatus.lead_id)\
            .filter(models.Lead.organization_id == organization_id, models.LeadCampaignStatus.status.in_(positive_statuses))
        if start_date: query = query.filter(models.LeadCampaignStatus.last_response_at >= start_date)
        if end_date: query = query.filter(models.LeadCampaignStatus.last_response_at <= end_date)
        return query.scalar() or 0
    except SQLAlchemyError as e: logger.error(f"DB Error count positive replies: {e}", exc_info=True); return 0

def get_recent_appointments_list(db: Session, organization_id: int, limit: int = 5) -> List[Dict]:
    if not models.Lead or not models.EmailCampaign or not models.LeadCampaignStatus: logger.error("DB: Models missing for recent_appointments."); return []
    try:
        results = db.query(
                models.Lead.name.label("lead_name"), models.Lead.company.label("company_name"),
                models.EmailCampaign.name.label("campaign_name"),
                models.LeadCampaignStatus.last_response_at.label("action_date") # Or appointment set date if available
            ).join(models.LeadCampaignStatus, models.Lead.id == models.LeadCampaignStatus.lead_id)\
             .join(models.EmailCampaign, models.EmailCampaign.id == models.LeadCampaignStatus.campaign_id)\
             .filter(models.Lead.organization_id == organization_id, models.Lead.appointment_confirmed == True)\
             .order_by(models.LeadCampaignStatus.last_response_at.desc().nullslast()).limit(limit).all()
        return [
            {"lead_name": r.lead_name or "N/A", "company_name": r.company_name or "N/A",
             "campaign_name": r.campaign_name or "N/A",
             "date_marked": r.action_date.strftime('%Y-%m-%d %H:%M') if r.action_date else 'N/A'}
            for r in results
        ]
    except SQLAlchemyError as e: logger.error(f"DB Error get recent appointments: {e}", exc_info=True); return []

# ==========================================
# Main execution for schema creation
# ==========================================
if __name__ == "__main__":
    logger.info("Running database.py directly, attempting SQLAlchemy table creation...")
    if 'engine' in globals() and Base:
        create_db_and_tables()
        logger.info("SQLAlchemy table creation process from __main__ finished.")
    else:
        logger.error("Cannot create tables from __main__: SQLAlchemy Base or engine not available.")
