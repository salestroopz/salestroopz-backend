# app/db/database.py

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime # Import datetime

# Import logger unconditionally if used in functions like placeholders
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# --- Import Settings ---
try:
    from app.utils.config import settings
    logger.info("Successfully imported settings in database.py")
except ImportError:
    logger.warning("Could not import settings from app.utils.config. Using default DB path.")
    settings = None

# --- Determine Database Path ---
if settings and settings.DATABASE_URL.startswith("sqlite"):
    db_url_path_part = settings.DATABASE_URL.split("///")[-1]
    DB_PATH = Path(db_url_path_part).resolve()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.info(f"Using SQLite database path from settings: {DB_PATH}")
elif settings:
    logger.warning(f"Non-SQLite DATABASE_URL ({settings.DATABASE_URL}). Connection logic assumes SQLite.")
    DB_PATH = None
else:
    DB_PATH = Path(__file__).parent / "salestroopz_fallback.db"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger.warning(f"Using fallback SQLite database path: {DB_PATH}")


# --- Database Connection Function ---
def get_connection():
    """Establishes and returns a connection to the SQLite database."""
    if not DB_PATH:
         raise ValueError("Database path is not configured correctly for SQLite.")
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON;") # Enable foreign key enforcement
    return conn


# --- Database Initialization (ALL Tables) ---
def initialize_db():
    """Creates/updates tables: organizations, users, leads, icps, offerings, email_campaigns, campaign_steps, lead_campaign_status, organization_email_settings."""
    logger.info("Initializing database schema...")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Define all CREATE TABLE statements here
        tables = {
            "organizations": """
                CREATE TABLE IF NOT EXISTS organizations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP )""",
            "users": """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    hashed_password TEXT NOT NULL, organization_id INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )""",
            "leads": """
                CREATE TABLE IF NOT EXISTS leads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL, name TEXT,
                    email TEXT NOT NULL COLLATE NOCASE, company TEXT, title TEXT, source TEXT, linkedin_profile TEXT,
                    company_size TEXT, industry TEXT, location TEXT, matched INTEGER DEFAULT 0, reason TEXT,
                    crm_status TEXT DEFAULT 'pending', appointment_confirmed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, UNIQUE (organization_id, email),
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )""",
            "icps": """
                CREATE TABLE IF NOT EXISTS icps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL UNIQUE,
                    name TEXT DEFAULT 'Default ICP', title_keywords TEXT, industry_keywords TEXT,
                    company_size_rules TEXT, location_keywords TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )""",
            "offerings": """
                CREATE TABLE IF NOT EXISTS offerings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL, name TEXT NOT NULL,
                    description TEXT, key_features TEXT, target_pain_points TEXT, call_to_action TEXT,
                    is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )""",
            "email_campaigns": """
                CREATE TABLE IF NOT EXISTS email_campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL, name TEXT NOT NULL,
                    description TEXT, is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )""",
            "campaign_steps": """
                CREATE TABLE IF NOT EXISTS campaign_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, campaign_id INTEGER NOT NULL, organization_id INTEGER NOT NULL,
                    step_number INTEGER NOT NULL, delay_days INTEGER DEFAULT 1, subject_template TEXT, body_template TEXT,
                    is_ai_crafted INTEGER DEFAULT 0, follow_up_angle TEXT, -- Added follow_up_angle
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (campaign_id, step_number),
                    FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )""",
            "lead_campaign_status": """
                CREATE TABLE IF NOT EXISTS lead_campaign_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, lead_id INTEGER NOT NULL, campaign_id INTEGER NOT NULL,
                    organization_id INTEGER NOT NULL, current_step_number INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending',
                    last_email_sent_at TIMESTAMP, next_email_due_at TIMESTAMP, last_response_type TEXT, last_response_at TIMESTAMP,
                    error_message TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (lead_id),
                    FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE,
                    FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id) ON DELETE CASCADE,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )""",
            "organization_email_settings": """
                CREATE TABLE IF NOT EXISTS organization_email_settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL UNIQUE, provider_type TEXT,
                    smtp_host TEXT, smtp_port INTEGER, smtp_username TEXT, encrypted_smtp_password TEXT,
                    encrypted_api_key TEXT, encrypted_access_token TEXT, encrypted_refresh_token TEXT, token_expiry TIMESTAMP,
                    verified_sender_email TEXT NOT NULL, sender_name TEXT, is_configured INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE )"""
        }

        # Define indexes separately for clarity
        indexes = {
            "users": ["CREATE INDEX IF NOT EXISTS idx_user_email ON users (email)",
                      "CREATE INDEX IF NOT EXISTS idx_user_organization ON users (organization_id)"],
            "leads": ["CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id)",
                      "CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email)"],
            "icps": ["CREATE INDEX IF NOT EXISTS idx_icp_organization ON icps (organization_id)"],
            "offerings": ["CREATE INDEX IF NOT EXISTS idx_offering_organization ON offerings (organization_id)"],
            "email_campaigns": ["CREATE INDEX IF NOT EXISTS idx_campaign_organization ON email_campaigns (organization_id)"],
            "campaign_steps": ["CREATE INDEX IF NOT EXISTS idx_step_campaign ON campaign_steps (campaign_id)",
                               "CREATE INDEX IF NOT EXISTS idx_step_organization ON campaign_steps (organization_id)"],
            "lead_campaign_status": ["CREATE INDEX IF NOT EXISTS idx_status_lead ON lead_campaign_status (lead_id)",
                                     "CREATE INDEX IF NOT EXISTS idx_status_campaign ON lead_campaign_status (campaign_id)",
                                     "CREATE INDEX IF NOT EXISTS idx_status_organization ON lead_campaign_status (organization_id)",
                                     "CREATE INDEX IF NOT EXISTS idx_status_status ON lead_campaign_status (status)",
                                     "CREATE INDEX IF NOT EXISTS idx_status_due ON lead_campaign_status (next_email_due_at)"],
            "organization_email_settings": ["CREATE INDEX IF NOT EXISTS idx_email_settings_organization ON organization_email_settings (organization_id)"]
        }

        # Execute CREATE TABLE statements
        for table_name, sql_create in tables.items():
            cursor.execute(sql_create)
            logger.debug(f" -> {table_name.capitalize()} table checked/created.")

        # Execute CREATE INDEX statements
        for table_name, index_sqls in indexes.items():
             for sql_index in index_sqls:
                 cursor.execute(sql_index)
             logger.debug(f" -> {table_name.capitalize()} indexes checked/created.")

        conn.commit()
        logger.info("Database initialization sequence complete.")
    except sqlite3.Error as e:
        logger.error(f"DATABASE ERROR during initialization: {e}", exc_info=True)
        # Consider re-raising depending on how critical initialization is
    finally:
        if conn: conn.close()


# ==========================================
# ORGANIZATION CRUD OPERATIONS
# ==========================================
def create_organization(name: str) -> Optional[Dict]:
    sql = "INSERT INTO organizations (name) VALUES (?)"
    conn = None; org_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, (name,)); org_id = cursor.lastrowid
        conn.commit(); logger.info(f"Created organization '{name}' with ID: {org_id}")
        org_data = get_organization_by_id(org_id)
    except sqlite3.IntegrityError:
        logger.warning(f"Organization name '{name}' already exists.")
        org_data = get_organization_by_name(name)
    except sqlite3.Error as e: logger.error(f"DB Error creating org '{name}': {e}")
    finally:
        if conn: conn.close()
    return org_data

def get_organization_by_id(organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM organizations WHERE id = ?"
    conn = None; org_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (organization_id,)); result = cursor.fetchone()
        if result: org_data = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return org_data

def get_organization_by_name(name: str) -> Optional[Dict]:
    sql = "SELECT * FROM organizations WHERE name = ?"
    conn = None; org_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (name,)); result = cursor.fetchone()
        if result: org_data = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting org name '{name}': {e}")
    finally:
        if conn: conn.close()
    return org_data

def get_all_organizations() -> List[Dict]:
    sql = "SELECT * FROM organizations ORDER BY name"
    conn = None; orgs = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql); results = cursor.fetchall()
        for row in results: orgs.append(dict(row))
    except sqlite3.Error as e: logger.error(f"DB Error getting all organizations: {e}")
    finally:
        if conn: conn.close()
    return orgs

# ==========================================
# USER CRUD OPERATIONS
# ==========================================
def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (?, ?, ?)"
    conn = None; user_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, (email, hashed_password, organization_id)); user_id = cursor.lastrowid
        conn.commit(); logger.info(f"Created user '{email}' (ID: {user_id}) for org ID {organization_id}")
        user_data = get_user_by_id(user_id)
    except sqlite3.IntegrityError as e:
        if "users.email" in str(e): logger.warning(f"User email '{email}' already exists.")
        elif "FOREIGN KEY" in str(e): logger.error(f"Cannot create user: Org ID {organization_id} does not exist.")
        else: logger.error(f"DB Integrity error creating user '{email}': {e}")
    except sqlite3.Error as e: logger.error(f"DB Error creating user '{email}': {e}")
    finally:
        if conn: conn.close()
    return user_data

def get_user_by_id(user_id: int) -> Optional[Dict]:
    sql = "SELECT u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name FROM users u JOIN organizations o ON u.organization_id = o.id WHERE u.id = ?"
    conn = None; user = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (user_id,)); result = cursor.fetchone()
        if result: user = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting user ID {user_id}: {e}")
    finally:
        if conn: conn.close()
    return user

def get_user_by_email(email: str) -> Optional[Dict]:
    sql = "SELECT u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name FROM users u JOIN organizations o ON u.organization_id = o.id WHERE u.email = ?"
    conn = None; user = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (email,)); result = cursor.fetchone()
        if result: user = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting user by email '{email}': {e}")
    finally:
        if conn: conn.close()
    return user

def get_users_by_organization(organization_id: int) -> List[Dict]:
    sql = "SELECT u.id, u.email, u.organization_id, o.name as organization_name FROM users u JOIN organizations o ON u.organization_id = o.id WHERE u.organization_id = ? ORDER BY u.email"
    conn = None; users = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (organization_id,)); results = cursor.fetchall()
        for row in results: users.append(dict(row))
    except sqlite3.Error as e: logger.error(f"DB Error getting users for org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return users


# ==========================================
# LEAD CRUD OPERATIONS (Tenant-Aware)
# ==========================================
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
    conn = None; saved_lead = None; required_fields = ["email"]
    if not lead_data.get("email"):
        logger.warning(f"Skipping lead save for org {organization_id} due to missing email: {lead_data.get('name')}")
        return None
    columns = ["organization_id", "name", "email", "company", "title", "source", "linkedin_profile", "company_size", "industry", "location", "matched", "reason", "crm_status", "appointment_confirmed"]
    sql_upsert = f"""INSERT INTO leads ({", ".join(columns)}) VALUES ({", ".join(["?"] * len(columns))})
                     ON CONFLICT(organization_id, email) DO UPDATE SET
                         name=excluded.name, company=excluded.company, title=excluded.title, source=excluded.source,
                         linkedin_profile=excluded.linkedin_profile, company_size=excluded.company_size, industry=excluded.industry,
                         location=excluded.location, matched=excluded.matched, reason=excluded.reason,
                         crm_status=excluded.crm_status, appointment_confirmed=excluded.appointment_confirmed, created_at=excluded.created_at;""" # Keep created_at on update? Maybe updated_at?
    try:
        conn = get_connection(); cursor = conn.cursor()
        match_result_dict = lead_data.get("match_result", {})
        params = (
            organization_id, lead_data.get("name", ""), lead_data.get("email"), lead_data.get("company", ""), lead_data.get("title", ""),
            lead_data.get("source", "unknown"), lead_data.get("linkedin_profile"), lead_data.get("company_size"), lead_data.get("industry"),
            lead_data.get("location"), int(match_result_dict.get("matched", lead_data.get("matched", 0))),
            match_result_dict.get("reason", lead_data.get("reason", "")), lead_data.get("crm_status", "pending"),
            int(lead_data.get("appointment_confirmed", 0)) )
        cursor.execute(sql_upsert, params); conn.commit()
        saved_lead = get_lead_by_email(lead_data['email'], organization_id)
        if saved_lead: logger.debug(f"Saved/Updated lead ID {saved_lead['id']} for org {organization_id}")
    except sqlite3.Error as e: logger.error(f"DB Error saving lead for org {organization_id}, email {lead_data.get('email')}: {e}", exc_info=True)
    except Exception as e: logger.error(f"Unexpected error saving lead for org {organization_id}, email {lead_data.get('email')}: {e}", exc_info=True)
    finally:
        if conn: conn.close()
    return saved_lead

def get_lead_by_id(lead_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM leads WHERE id = ? AND organization_id = ?"
    conn = None; lead_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (lead_id, organization_id)); result = cursor.fetchone()
        if result: lead_data = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting lead ID {lead_id} for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return lead_data

def get_lead_by_email(email: str, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM leads WHERE email = ? AND organization_id = ?"
    conn = None; lead_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (email, organization_id)); result = cursor.fetchone()
        if result: lead_data = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting lead by email '{email}' for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return lead_data

def get_leads_by_organization(organization_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
    leads = []; conn = None
    sql = "SELECT * FROM leads WHERE organization_id = ? ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (organization_id, limit, offset)); results = cursor.fetchall()
        for row in results: leads.append(dict(row))
    except sqlite3.Error as e: logger.error(f"DB Error fetching leads for org {organization_id} (limit={limit}, offset={offset}): {e}")
    finally:
        if conn: conn.close()
    return leads

def update_lead_partial(lead_id: int, organization_id: int, update_data: Dict[str, Any]) -> Optional[Dict]:
    if not update_data: return get_lead_by_id(lead_id, organization_id)
    allowed_columns = {"name", "company", "title", "source", "linkedin_profile", "company_size", "industry", "location", "matched", "reason", "crm_status", "appointment_confirmed"}
    valid_updates = {k: v for k, v in update_data.items() if k in allowed_columns}
    if not valid_updates: return get_lead_by_id(lead_id, organization_id)
    set_clause = ", ".join([f"{key} = ?" for key in valid_updates.keys()])
    sql = f"UPDATE leads SET {set_clause} WHERE id = ? AND organization_id = ?"
    params = list(valid_updates.values()) + [lead_id, organization_id]
    conn = None; success = False
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); conn.commit()
        if cursor.rowcount > 0: success = True; logger.debug(f"Partially updated lead ID {lead_id} for org {organization_id}.")
        else: logger.warning(f"Lead ID {lead_id} not found or no changes applied for org {organization_id}.")
    except sqlite3.Error as e: logger.error(f"DB Error partially updating lead ID {lead_id} for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return get_lead_by_id(lead_id, organization_id) if success else None

def delete_lead(lead_id: int, organization_id: int) -> bool:
    sql = "DELETE FROM leads WHERE id = ? AND organization_id = ?"
    conn = None; success = False
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, (lead_id, organization_id)); conn.commit()
        if cursor.rowcount > 0: success = True; logger.info(f"Deleted lead ID {lead_id} for org {organization_id}.")
        else: logger.warning(f"Lead ID {lead_id} not found for org {organization_id} to delete.")
    except sqlite3.Error as e: logger.error(f"DB Error deleting lead ID {lead_id} for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return success


# ==========================================
# ICP CRUD OPERATIONS (Tenant-Aware)
# ==========================================
def _parse_icp_json_fields(icp_row: sqlite3.Row) -> Optional[Dict]:
    # ... (Keep implementation) ...
    pass
def create_or_update_icp(organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    # ... (Keep implementation) ...
    pass
def get_icp_by_organization_id(organization_id: int) -> Optional[Dict]:
    # ... (Keep implementation) ...
    pass
def delete_icp(organization_id: int) -> bool:
    sql = "DELETE FROM icps WHERE organization_id = ?"
    conn = None; success = False
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, (organization_id,)); conn.commit()
        if cursor.rowcount > 0: success = True; logger.info(f"Deleted ICP for org {organization_id}.")
        else: logger.warning(f"ICP not found for org {organization_id} to delete.")
    except sqlite3.Error as e: logger.error(f"DB Error deleting ICP for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return success


# ==========================================
# OFFERING CRUD OPERATIONS (Tenant-Aware)
# ==========================================
def _parse_offering_json_fields(offering_row: sqlite3.Row) -> Optional[Dict]:
    # ... (Keep implementation) ...
    pass
def create_offering(organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    # ... (Keep implementation) ...
    pass
def update_offering(offering_id: int, organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    # ... (Keep implementation) ...
    pass
def get_offering_by_id(offering_id: int, organization_id: int) -> Optional[Dict]:
    # ... (Keep implementation) ...
    pass
def get_offerings_by_organization_id(organization_id: int, active_only: bool = True) -> List[Dict]:
    # ... (Keep implementation) ...
    pass
def delete_offering(offering_id: int, organization_id: int) -> bool:
    # ... (Keep implementation) ...
    pass

# ===========================================================
# CAMPAIGN/STEP/STATUS CRUD (Implementations Added)
# ===========================================================

# --- Campaign CRUD ---
def create_campaign(organization_id: int, name: str, description: Optional[str] = None, is_active: bool = True) -> Optional[Dict]:
    sql = "INSERT INTO email_campaigns (organization_id, name, description, is_active) VALUES (?, ?, ?, ?)"
    params = (organization_id, name, description, int(is_active))
    conn = None; new_id = None; campaign_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); new_id = cursor.lastrowid
        conn.commit(); logger.info(f"Created campaign '{name}' (ID: {new_id}) for Org {organization_id}")
        if new_id: campaign_data = get_campaign_by_id(new_id, organization_id)
    except sqlite3.Error as e: logger.error(f"DB Error creating campaign for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaign_data

def get_campaign_by_id(campaign_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM email_campaigns WHERE id = ? AND organization_id = ?"
    conn = None; campaign = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id)); result = cursor.fetchone()
        if result: campaign = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting campaign ID {campaign_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaign

def get_campaigns_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    sql = "SELECT * FROM email_campaigns WHERE organization_id = ?"
    params = [organization_id]
    if active_only: sql += " AND is_active = 1"
    sql += " ORDER BY name"
    conn = None; campaigns = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, params); results = cursor.fetchall()
        for row in results: campaigns.append(dict(row))
    except sqlite3.Error as e: logger.error(f"DB Error getting campaigns for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaigns

# --- Step CRUD ---
def create_campaign_step(campaign_id: int, organization_id: int, step_number: int, delay_days: int, subject: Optional[str], body: Optional[str], is_ai: bool = False, follow_up_angle: Optional[str] = None) -> Optional[Dict]: # Added follow_up_angle
    sql = """
        INSERT INTO campaign_steps
        (campaign_id, organization_id, step_number, delay_days, subject_template, body_template, is_ai_crafted, follow_up_angle)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """ # Added follow_up_angle
    params = (campaign_id, organization_id, step_number, delay_days, subject, body, int(is_ai), follow_up_angle)
    conn = None; new_id = None; step_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); new_id = cursor.lastrowid
        conn.commit(); logger.info(f"Created step {step_number} (ID: {new_id}) for Campaign {campaign_id}, Org {organization_id}")
        if new_id: step_data = get_campaign_step_by_id(new_id, organization_id)
    except sqlite3.IntegrityError as ie: logger.error(f"DB Integrity Error creating step {step_number} for Camp {campaign_id}: {ie}")
    except sqlite3.Error as e: logger.error(f"DB Error creating step {step_number} for Camp {campaign_id}: {e}")
    finally:
        if conn: conn.close()
    return step_data

def get_campaign_step_by_id(step_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM campaign_steps WHERE id = ? AND organization_id = ?"
    conn = None; step = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (step_id, organization_id)); result = cursor.fetchone()
        if result: step = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting step ID {step_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return step

def get_steps_for_campaign(campaign_id: int, organization_id: int) -> List[Dict]:
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = ? AND organization_id = ? ORDER BY step_number"
    conn = None; steps = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id)); results = cursor.fetchall()
        for row in results: steps.append(dict(row))
    except sqlite3.Error as e: logger.error(f"DB Error getting steps for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return steps

def get_next_campaign_step(campaign_id: int, organization_id: int, current_step_number: int) -> Optional[Dict]:
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = ? AND organization_id = ? AND step_number = ? LIMIT 1"
    next_step_number = current_step_number + 1
    conn = None; step_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id, next_step_number))
        result = cursor.fetchone()
        if result: step_data = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting next step ({next_step_number}) for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return step_data

# --- Lead Status CRUD ---
def enroll_lead_in_campaign(lead_id: int, campaign_id: int, organization_id: int) -> Optional[Dict]:
    sql = """INSERT INTO lead_campaign_status (lead_id, campaign_id, organization_id, status, current_step_number) VALUES (?, ?, ?, 'active', 0)"""
    params = (lead_id, campaign_id, organization_id)
    conn = None; status_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); status_id = cursor.lastrowid
        conn.commit(); logger.info(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {status_id})")
        status_data = get_lead_campaign_status_by_id(status_id, organization_id)
    except sqlite3.IntegrityError as ie: logger.warning(f"DB Integrity Error enrolling lead {lead_id} in camp {campaign_id}: {ie} (Likely already enrolled or FK issue)")
    except sqlite3.Error as e: logger.error(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    allowed_fields = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message"}
    valid_updates = {k:v for k,v in updates.items() if k in allowed_fields}
    if not valid_updates: return get_lead_campaign_status_by_id(status_id, organization_id)
    set_parts = [f"{key} = :{key}" for key in valid_updates.keys()]
    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    set_clause = ", ".join(set_parts)
    params = valid_updates; params["status_id"] = status_id; params["organization_id"] = organization_id
    sql = f"UPDATE lead_campaign_status SET {set_clause} WHERE id = :status_id AND organization_id = :organization_id"
    conn = None; success = False
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); conn.commit()
        if cursor.rowcount > 0: success = True; logger.debug(f"Updated lead campaign status ID {status_id}")
        else: logger.warning(f"Lead campaign status ID {status_id} not found or no change for Org {organization_id}")
    except sqlite3.Error as e: logger.error(f"DB Error updating lead status ID {status_id}: {e}")
    finally:
        if conn: conn.close()
    return get_lead_campaign_status_by_id(status_id, organization_id) if success else None


def get_active_leads_due_for_step(organization_id: Optional[int] = None) -> List[Dict]:
    logger.warning("DB get_active_leads_due_for_step query is simplified. Filtering happens in scheduler agent.")
    leads_due = []; conn = None
    sql = """ SELECT lcs.*, c.name as campaign_name FROM lead_campaign_status lcs
              JOIN email_campaigns c ON lcs.campaign_id = c.id WHERE lcs.status = 'active' """
    params = []
    if organization_id is not None: sql += " AND lcs.organization_id = ?"; params.append(organization_id)
    sql += " ORDER BY lcs.organization_id, lcs.last_email_sent_at ASC NULLS FIRST"
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, params); results = cursor.fetchall()
        for row in results: leads_due.append(dict(row))
        logger.debug(f"DB: Found {len(leads_due)} total active leads {f'for Org {organization_id}' if organization_id else 'across all orgs'}.")
    except sqlite3.Error as e: logger.error(f"DB Error getting active leads{f' for Org {organization_id}' if organization_id else ''}: {e}")
    finally:
        if conn: conn.close()
    return leads_due

def get_lead_campaign_status_by_id(status_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM lead_campaign_status WHERE id = ? AND organization_id = ?"
    conn = None; status_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (status_id, organization_id)); result = cursor.fetchone()
        if result: status_data = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting lead status ID {status_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

def get_lead_campaign_status(lead_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM lead_campaign_status WHERE lead_id = ? AND organization_id = ?"
    conn = None; status_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (lead_id, organization_id)); result = cursor.fetchone()
        if result: status_data = dict(result)
    except sqlite3.Error as e: logger.error(f"DB Error getting campaign status for lead {lead_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

# ==========================================
# NEW: ORGANIZATION EMAIL SETTINGS CRUD
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None: return None
    logger.warning("ENCRYPTION NOT IMPLEMENTED. Storing sensitive data as plain text!")
    return plain_text
def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None: return None
    return encrypted_text

def save_org_email_settings(organization_id: int, settings_data: Dict[str, Any]) -> Optional[Dict]:
    conn = None; saved_settings = None
    encrypted_password = _encrypt_data(settings_data.get("smtp_password"))
    encrypted_api_key = _encrypt_data(settings_data.get("api_key"))
    encrypted_access_token = _encrypt_data(settings_data.get("access_token"))
    encrypted_refresh_token = _encrypt_data(settings_data.get("refresh_token"))
    columns = ["organization_id", "provider_type", "smtp_host", "smtp_port", "smtp_username", "encrypted_smtp_password", "encrypted_api_key", "encrypted_access_token", "encrypted_refresh_token", "token_expiry", "verified_sender_email", "sender_name", "is_configured"]
    params = { "organization_id": organization_id, "provider_type": settings_data.get("provider_type"), "smtp_host": settings_data.get("smtp_host"), "smtp_port": settings_data.get("smtp_port"), "smtp_username": settings_data.get("smtp_username"), "encrypted_smtp_password": encrypted_password, "encrypted_api_key": encrypted_api_key, "encrypted_access_token": encrypted_access_token, "encrypted_refresh_token": encrypted_refresh_token, "token_expiry": settings_data.get("token_expiry"), "verified_sender_email": settings_data.get("verified_sender_email"), "sender_name": settings_data.get("sender_name"), "is_configured": int(settings_data.get("is_configured", 0)) }
    set_clause_parts = [f"{col} = excluded.{col}" for col in columns if col != 'organization_id']; set_clause_parts.append("updated_at = CURRENT_TIMESTAMP"); set_clause = ", ".join(set_clause_parts)
    sql = f"""INSERT INTO organization_email_settings ({", ".join(columns)}) VALUES ({", ".join([f":{col}" for col in columns])}) ON CONFLICT(organization_id) DO UPDATE SET {set_clause};"""
    try:
        if not params["verified_sender_email"]: raise ValueError("Verified sender email is required.")
        if not params["provider_type"]: raise ValueError("Provider type is required.")
        conn = get_connection(); cursor = conn.cursor(); cursor.execute(sql, params); conn.commit()
        logger.info(f"Saved/Updated Email Settings for Org ID: {organization_id}")
        saved_settings = get_org_email_settings_from_db(organization_id)
    except sqlite3.Error as e: logger.error(f"DB Error saving email settings for Org {organization_id}: {e}")
    except ValueError as ve: logger.error(f"Validation Error saving email settings for Org {organization_id}: {ve}")
    except Exception as e: logger.error(f"Unexpected error saving email settings for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return saved_settings

def get_org_email_settings_from_db(organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM organization_email_settings WHERE organization_id = ?"
    conn = None; settings_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (organization_id,)); result = cursor.fetchone()
        if result:
            settings_data = dict(result)
            settings_data["smtp_password"] = _decrypt_data(settings_data.pop("encrypted_smtp_password", None))
            settings_data["api_key"] = _decrypt_data(settings_data.pop("encrypted_api_key", None))
            settings_data["access_token"] = _decrypt_data(settings_data.pop("encrypted_access_token", None))
            settings_data["refresh_token"] = _decrypt_data(settings_data.pop("encrypted_refresh_token", None))
    except sqlite3.Error as e: logger.error(f"DB Error getting email settings for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return settings_data
