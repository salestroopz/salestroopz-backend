# app/db/database.py

import psycopg2 # Use PostgreSQL driver
from psycopg2.extras import RealDictCursor # Get dict results
from urllib.parse import urlparse # For parsing DATABASE_URL
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone # Use timezone for UTC

# Import logger
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# Import Settings
try:
    from app.utils.config import settings
    logger.info("Successfully imported settings in database.py")
    if not settings or not getattr(settings, 'DATABASE_URL', None) or settings.DATABASE_URL == "ENV_VAR_DATABASE_URL_NOT_SET":
        logger.critical("DATABASE_URL is not configured in settings.")
        settings = None # Mark settings as invalid for DB operations
    elif not settings.DATABASE_URL.startswith("postgresql"):
         logger.critical(f"DATABASE_URL is not a PostgreSQL URL: {settings.DATABASE_URL}")
         settings = None
except ImportError:
    logger.critical("Could not import settings from app.utils.config.")
    settings = None
except Exception as e:
    logger.critical(f"Error loading settings in database.py: {e}")
    settings = None

# --- Database Connection Function ---
def get_connection():
    """Establishes and returns a connection to the PostgreSQL database using DATABASE_URL."""
    if not settings:
        raise ValueError("Database settings (DATABASE_URL) not loaded or invalid.")
    try:
        # Parse the DATABASE_URL
        result = urlparse(settings.DATABASE_URL)
        # Build connection string suitable for psycopg2.connect()
        dsn = f"dbname='{result.path[1:]}' user='{result.username}' password='{result.password}' host='{result.hostname}' port='{result.port or 5432}'"
        logger.debug(f"Connecting to PostgreSQL DB: {result.path[1:]} on {result.hostname}:{result.port or 5432}")
        conn = psycopg2.connect(dsn)
        logger.debug("PostgreSQL connection successful.")
        return conn
    except ValueError as ve:
        logger.error(f"Error parsing DATABASE_URL '{settings.DATABASE_URL}': {ve}", exc_info=True)
        raise ValueError(f"Invalid DATABASE_URL format: {ve}") from ve
    except psycopg2.OperationalError as e:
        logger.error(f"DATABASE CONNECTION ERROR: Failed to connect to PostgreSQL - {e}", exc_info=True)
        raise ConnectionError(f"Failed to connect to database: {e}") from e
    except Exception as e:
         logger.error(f"Unexpected error getting PostgreSQL connection: {e}", exc_info=True)
         raise ConnectionError("Unexpected error connecting to database") from e

# --- Database Initialization (PostgreSQL Syntax) ---
def initialize_db():
    """Creates/updates tables for PostgreSQL if they don't exist."""
    logger.info("Initializing PostgreSQL database schema...")
    conn = None
    tables = { # Using SERIAL PRIMARY KEY, TIMESTAMPTZ, JSONB, BOOLEAN
        "organizations": """CREATE TABLE IF NOT EXISTS organizations ( id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "users": """CREATE TABLE IF NOT EXISTS users ( id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, hashed_password TEXT NOT NULL, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "leads": """CREATE TABLE IF NOT EXISTS leads ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT, email TEXT NOT NULL, company TEXT, title TEXT, source TEXT, linkedin_profile TEXT, company_size TEXT, industry TEXT, location TEXT, matched INTEGER DEFAULT 0, reason TEXT, crm_status TEXT DEFAULT 'pending', appointment_confirmed INTEGER DEFAULT 0, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (organization_id, email) );""",
        "icps": """CREATE TABLE IF NOT EXISTS icps ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE, name TEXT DEFAULT 'Default ICP', title_keywords JSONB, industry_keywords JSONB, company_size_rules JSONB, location_keywords JSONB, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "offerings": """CREATE TABLE IF NOT EXISTS offerings ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT, key_features JSONB, target_pain_points JSONB, call_to_action TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "email_campaigns": """CREATE TABLE IF NOT EXISTS email_campaigns ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "campaign_steps": """CREATE TABLE IF NOT EXISTS campaign_steps ( id SERIAL PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, step_number INTEGER NOT NULL, delay_days INTEGER DEFAULT 1, subject_template TEXT, body_template TEXT, is_ai_crafted BOOLEAN DEFAULT FALSE, follow_up_angle TEXT, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (campaign_id, step_number) );""",
        "lead_campaign_status": """CREATE TABLE IF NOT EXISTS lead_campaign_status ( id SERIAL PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE, campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, current_step_number INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', last_email_sent_at TIMESTAMPTZ, next_email_due_at TIMESTAMPTZ, last_response_type TEXT, last_response_at TIMESTAMPTZ, error_message TEXT, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (lead_id) );""",
        "organization_email_settings": """CREATE TABLE IF NOT EXISTS organization_email_settings ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE, provider_type TEXT, smtp_host TEXT, smtp_port INTEGER, smtp_username TEXT, encrypted_smtp_password TEXT, encrypted_api_key TEXT, encrypted_access_token TEXT, encrypted_refresh_token TEXT, token_expiry TIMESTAMPTZ, verified_sender_email TEXT NOT NULL, sender_name TEXT, is_configured BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );"""
    }
    indexes = { # Indexes for PostgreSQL
        "users": ["CREATE INDEX IF NOT EXISTS idx_user_email ON users (email);", "CREATE INDEX IF NOT EXISTS idx_user_organization ON users (organization_id);"],
        "leads": ["CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id);", "CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email);"],
        "icps": ["CREATE INDEX IF NOT EXISTS idx_icp_organization ON icps (organization_id);"],
        "offerings": ["CREATE INDEX IF NOT EXISTS idx_offering_organization ON offerings (organization_id);"],
        "email_campaigns": ["CREATE INDEX IF NOT EXISTS idx_campaign_organization ON email_campaigns (organization_id);"],
        "campaign_steps": ["CREATE INDEX IF NOT EXISTS idx_step_campaign ON campaign_steps (campaign_id);", "CREATE INDEX IF NOT EXISTS idx_step_organization ON campaign_steps (organization_id);"],
        "lead_campaign_status": ["CREATE INDEX IF NOT EXISTS idx_status_lead ON lead_campaign_status (lead_id);", "CREATE INDEX IF NOT EXISTS idx_status_campaign ON lead_campaign_status (campaign_id);", "CREATE INDEX IF NOT EXISTS idx_status_organization ON lead_campaign_status (organization_id);", "CREATE INDEX IF NOT EXISTS idx_status_status ON lead_campaign_status (status);", "CREATE INDEX IF NOT EXISTS idx_status_due ON lead_campaign_status (next_email_due_at);"],
        "organization_email_settings": ["CREATE INDEX IF NOT EXISTS idx_email_settings_organization ON organization_email_settings (organization_id);"]
    }
    try:
        conn = get_connection()
        with conn: # Use connection as context manager (auto commit/rollback)
            with conn.cursor() as cursor: # Use cursor context manager
                logger.info("Executing CREATE TABLE statements for PostgreSQL...")
                for table_name, sql_create in tables.items(): cursor.execute(sql_create); logger.debug(f" -> {table_name.capitalize()} table checked/created.")
                logger.info("Executing CREATE INDEX statements for PostgreSQL...")
                for table_name, index_sqls in indexes.items():
                     for sql_index in index_sqls: cursor.execute(sql_index)
                     logger.debug(f" -> {table_name.capitalize()} indexes checked/created.")
        logger.info("Database initialization sequence complete.")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f"DATABASE ERROR during initialization: {error}", exc_info=True)
        # Error handling within context manager should have rolled back
    finally:
         if conn and not conn.closed: conn.close(); logger.debug("DB connection closed.") # Ensure close if not using 'with conn:'

# ==========================================
# PLACEHOLDER ENCRYPTION FUNCTIONS
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]: # Keep Placeholders
    if plain_text is None: return None; logger.warning("ENCRYPTION NOT IMPLEMENTED!"); return plain_text
def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]: # Keep Placeholders
    if encrypted_text is None: return None; return encrypted_text

# ==========================================
# HELPER to handle JSON parsing (needed for ICP/Offering reads)
# ==========================================
def _parse_json_fields(data_row: Dict, json_fields: List[str], default_value: Any = None) -> Optional[Dict]:
    """Helper to parse JSON fields from a dictionary row."""
    if not data_row: return None
    for field in json_fields:
        field_value = data_row.get(field)
        parsed_value = default_value
        if field_value and isinstance(field_value, str): # Check if it's a string needing parsing
            try: parsed_value = json.loads(field_value)
            except json.JSONDecodeError: logger.warning(f"Could not parse JSON for field '{field}' in row {data_row.get('id')}")
        elif field_value is not None: # If DB/driver already parsed it (e.g., JSONB -> dict/list)
            parsed_value = field_value
        data_row[field] = parsed_value # Store parsed value or default
    return data_row

# ==========================================
# ORGANIZATION CRUD OPERATIONS (Psycopg2)
# ==========================================
def create_organization(name: str) -> Optional[Dict]:
    sql = "INSERT INTO organizations (name) VALUES (%s) RETURNING id;"
    conn = None; org_data = None
    try:
        conn = get_connection()
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, (name,)); new_id_row = cursor.fetchone()
                    if new_id_row and new_id_row['id']: org_id = new_id_row['id']; logger.info(f"Created org '{name}' ID: {org_id}"); org_data = get_organization_by_id(org_id)
                except psycopg2.IntegrityError: logger.warning(f"Org name '{name}' already exists."); conn.rollback(); org_data = get_organization_by_name(name)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error creating org '{name}': {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return org_data

def get_organization_by_id(organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM organizations WHERE id = %s;"
    conn = None; org_data = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id,)); result = cursor.fetchone()
            if result: org_data = dict(result)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error getting org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return org_data

# ... Implement get_organization_by_name, get_all_organizations with psycopg2 ...

# ==========================================
# USER CRUD OPERATIONS (Psycopg2)
# ==========================================
def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (%s, %s, %s) RETURNING id;"
    conn = None; user_data = None
    try:
        conn = get_connection()
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, (email, hashed_password, organization_id)); new_id_row = cursor.fetchone()
                    if new_id_row and new_id_row['id']: user_id = new_id_row['id']; logger.info(f"Created user '{email}' (ID: {user_id}) for org ID {organization_id}"); user_data = get_user_by_id(user_id)
                except psycopg2.IntegrityError as e: conn.rollback(); logger.warning(f"DB Integrity error creating user '{email}' (email exists or bad org_id?): {e}")
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error creating user '{email}': {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return user_data

def get_user_by_id(user_id: int) -> Optional[Dict]:
    sql = "SELECT u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name FROM users u JOIN organizations o ON u.organization_id = o.id WHERE u.id = %s;"
    conn = None; user = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (user_id,)); result = cursor.fetchone()
            if result: user = dict(result)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error getting user ID {user_id}: {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return user

# ... Implement get_user_by_email, get_users_by_organization with psycopg2 ...

# ==========================================
# LEAD CRUD OPERATIONS (Psycopg2)
# ==========================================
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
    columns = ["organization_id", "name", "email", "company", "title", "source", "linkedin_profile", "company_size", "industry", "location", "matched", "reason", "crm_status", "appointment_confirmed"]
    params = {col: lead_data.get(col) for col in columns}; params['organization_id'] = organization_id
    if not params['email']: logger.warning(f"Skipping lead save for org {organization_id}: missing email"); return None
    params['matched'] = int(params.get('matched', 0)); params['appointment_confirmed'] = int(params.get('appointment_confirmed', 0))
    values_str = ", ".join([f"%({col})s" for col in columns])
    update_cols = [f"{col} = EXCLUDED.{col}" for col in columns if col not in ['organization_id', 'email', 'created_at']]
    update_clause = ", ".join(update_cols)
    sql = f"""INSERT INTO leads ({", ".join(columns)}) VALUES ({values_str})
              ON CONFLICT (organization_id, email) DO UPDATE SET {update_clause} RETURNING id;"""
    conn = None; saved_lead = None
    try:
        conn = get_connection()
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params); returned_id_row = cursor.fetchone()
        # Fetch full data after commit
        saved_lead = get_lead_by_email(params['email'], organization_id)
        if saved_lead: logger.debug(f"Saved/Updated lead ID {saved_lead['id']} for org {organization_id}")
        elif returned_id_row: logger.warning("Saved lead but failed to fetch immediately after.") # Should fetch if save succeeded
        else: logger.warning(f"Lead upsert did not return ID for {params['email']}, Org {organization_id}. Checking existence.") ; saved_lead = get_lead_by_email(params['email'], organization_id)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error saving lead for org {organization_id}, email {params['email']}: {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return saved_lead

# ... Implement get_lead_by_id, get_lead_by_email, get_leads_by_organization, update_lead_partial, delete_lead with psycopg2 ...

# ==========================================
# ICP CRUD OPERATIONS (Psycopg2)
# ==========================================
def create_or_update_icp(organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    conn = None; saved_icp = None
    columns = ["organization_id", "name", "title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    params = { "organization_id": organization_id, "name": icp_definition.get("name", f"Org {organization_id} ICP"),
               "title_keywords": json.dumps(icp_definition.get("title_keywords") or []), "industry_keywords": json.dumps(icp_definition.get("industry_keywords") or []),
               "company_size_rules": json.dumps(icp_definition.get("company_size_rules") or {}), "location_keywords": json.dumps(icp_definition.get("location_keywords") or []),
               "updated_at": datetime.now(timezone.utc) }
    values_str = ", ".join([f"%({col})s" for col in columns])
    update_cols = [f"{col} = EXCLUDED.{col}" for col in columns if col != 'organization_id']; update_cols.append("updated_at = %(updated_at)s"); update_clause = ", ".join(update_cols)
    sql = f"""INSERT INTO icps ({", ".join(columns)}) VALUES ({values_str}) ON CONFLICT(organization_id) DO UPDATE SET {update_clause} RETURNING id;"""
    try:
        conn = get_connection()
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params); returned_id_row = cursor.fetchone()
        logger.info(f"Saved/Updated ICP for Org ID: {organization_id}. Returned ID: {returned_id_row}")
        saved_icp = get_icp_by_organization_id(organization_id)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error saving ICP for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return saved_icp

def get_icp_by_organization_id(organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM icps WHERE organization_id = %s;"
    conn = None; icp_data = None
    try:
        conn = get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id,)); result = cursor.fetchone()
            if result: icp_data = _parse_json_fields(dict(result), ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]) # Parse JSON
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error getting ICP for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return icp_data

# ... Implement delete_icp with psycopg2 ...

# ==========================================
# OFFERING CRUD OPERATIONS (Psycopg2)
# ==========================================
def _parse_offering_json_fields(offering_row: Dict) -> Optional[Dict]: # Input is already dict
    if not offering_row: return None; json_fields = ["key_features", "target_pain_points"]
    for field in json_fields:
        field_value = offering_row.get(field); parsed_value = [] # Default to list
        # JSONB might be parsed by driver already
        if isinstance(field_value, (list, dict)): parsed_value = field_value
        elif isinstance(field_value, str):
            try: parsed_value = json.loads(field_value)
            except json.JSONDecodeError: logger.warning(f"Could not parse JSON for Offering field '{field}' ID {offering_row.get('id')}")
        offering_row[field] = parsed_value if isinstance(parsed_value, list) else []
    return offering_row

def create_offering(organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    columns = ["organization_id", "name", "description", "key_features", "target_pain_points", "call_to_action", "is_active"]
    params = { "organization_id": organization_id, "name": offering_data.get("name"), "description": offering_data.get("description"),
               "key_features": json.dumps(offering_data.get("key_features") or []), "target_pain_points": json.dumps(offering_data.get("target_pain_points") or []),
               "call_to_action": offering_data.get("call_to_action"), "is_active": bool(offering_data.get("is_active", True)) }
    sql = f"INSERT INTO offerings ({', '.join(columns)}) VALUES ({', '.join([f'%({col})s' for col in columns])}) RETURNING id;"
    conn = None; saved_offering = None
    try:
        if not params["name"]: raise ValueError("Offering name cannot be empty")
        conn = get_connection()
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params); new_id_row = cursor.fetchone()
        if new_id_row and new_id_row['id']: offering_id = new_id_row['id']; logger.info(f"Created offering '{params['name']}' (ID: {offering_id}) for Org ID {organization_id}"); saved_offering = get_offering_by_id(offering_id, organization_id)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error creating offering for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not conn.closed: conn.close()
    return saved_offering

# ===========================================================
# CAMPAIGN/STEP/STATUS CRUD (Implementations Added)
# ===========================================================

# --- Campaign CRUD ---
def create_campaign(organization_id: int, name: str, description: Optional[str] = None, is_active: bool = True) -> Optional[Dict]:
    sql = "INSERT INTO email_campaigns (organization_id, name, description, is_active) VALUES (%s, %s, %s, %s) RETURNING id"
    params = (organization_id, name, description, is_active)
    conn = None; new_id = None; campaign_data = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        new_id = cursor.fetchone()[0]  # PostgreSQL returns inserted ID via RETURNING
        conn.commit()
        logger.info(f"Created campaign '{name}' (ID: {new_id}) for Org {organization_id}")
        if new_id:
            campaign_data = get_campaign_by_id(new_id, organization_id)
    except psycopg2.Error as e:
        logger.error(f"DB Error creating campaign for Org {organization_id}: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()
    return campaign_data

def get_campaign_by_id(campaign_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM email_campaigns WHERE id = %s AND organization_id = %s"
    conn = None; campaign = None
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql, (campaign_id, organization_id))
        result = cursor.fetchone()
        if result:
            campaign = dict(result)
    except psycopg2.Error as e:
        logger.error(f"DB Error getting campaign ID {campaign_id} for Org {organization_id}: {e}")
    finally:
        if conn:
            conn.close()
    return campaign

def get_campaigns_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    sql = "SELECT * FROM email_campaigns WHERE organization_id = %s"
    params = [organization_id]
    if active_only:
        sql += " AND is_active = TRUE"
    sql += " ORDER BY name"
    conn = None; campaigns = []
    try:
        conn = get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(sql, params)
        results = cursor.fetchall()
        for row in results:
            campaigns.append(dict(row))
    except psycopg2.Error as e:
        logger.error(f"DB Error getting campaigns for Org {organization_id}: {e}")
    finally:
        if conn:
            conn.close()
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
# --- Enroll Lead in Campaign ---
def enroll_lead_in_campaign(lead_id: int, campaign_id: int, organization_id: int) -> Optional[Dict]:
    sql = """INSERT INTO lead_campaign_status (lead_id, campaign_id, organization_id, status, current_step_number) 
             VALUES (%s, %s, %s, 'active', 0) RETURNING id"""
    params = (lead_id, campaign_id, organization_id)
    conn = None; status_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params)
        status_id = cursor.fetchone()[0]
        conn.commit()
        logger.info(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {status_id})")
        status_data = get_lead_campaign_status_by_id(status_id, organization_id)
    except psycopg2.IntegrityError as ie:
        logger.warning(f"DB Integrity Error enrolling lead {lead_id} in camp {campaign_id}: {ie} (Likely already enrolled or FK issue)")
        if conn: conn.rollback()
    except psycopg2.Error as e:
        logger.error(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()
    return status_data


# --- Update Lead Campaign Status ---
def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    allowed_fields = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message"}
    valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    if not valid_updates:
        return get_lead_campaign_status_by_id(status_id, organization_id)

    set_parts = [f"{key} = %({key})s" for key in valid_updates.keys()]
    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    set_clause = ", ".join(set_parts)

    params = valid_updates.copy()
    params["status_id"] = status_id
    params["organization_id"] = organization_id

    sql = f"UPDATE lead_campaign_status SET {set_clause} WHERE id = %(status_id)s AND organization_id = %(organization_id)s"

    conn = None; success = False
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        if cursor.rowcount > 0:
            success = True
            logger.debug(f"Updated lead campaign status ID {status_id}")
        else:
            logger.warning(f"Lead campaign status ID {status_id} not found or no change for Org {organization_id}")
    except psycopg2.Error as e:
        logger.error(f"DB Error updating lead status ID {status_id}: {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

    return get_lead_campaign_status_by_id(status_id, organization_id) if success else None


# --- Get Active Leads Due for Step ---
def get_active_leads_due_for_step(organization_id: Optional[int] = None) -> List[Dict]:
    logger.warning("DB get_active_leads_due_for_step query is simplified. Filtering happens in scheduler agent.")
    leads_due = []; conn = None
    sql = """SELECT lcs.*, c.name as campaign_name FROM lead_campaign_status lcs
             JOIN email_campaigns c ON lcs.campaign_id = c.id WHERE lcs.status = 'active'"""
    params = []
    if organization_id is not None:
        sql += " AND lcs.organization_id = %s"
        params.append(organization_id)
    sql += " ORDER BY lcs.organization_id, lcs.last_email_sent_at ASC NULLS FIRST"

    try:
        conn = get_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql, params)
        leads_due = cursor.fetchall()
        logger.debug(f"DB: Found {len(leads_due)} total active leads {f'for Org {organization_id}' if organization_id else 'across all orgs'}.")
    except psycopg2.Error as e:
        logger.error(f"DB Error getting active leads{f' for Org {organization_id}' if organization_id else ''}: {e}")
    finally:
        if conn: conn.close()

    return leads_due


# --- Get Lead Campaign Status by ID ---
def get_lead_campaign_status_by_id(status_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM lead_campaign_status WHERE id = %s AND organization_id = %s"
    conn = None; status_data = None
    try:
        conn = get_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql, (status_id, organization_id))
        result = cursor.fetchone()
        if result:
            status_data = dict(result)
    except psycopg2.Error as e:
        logger.error(f"DB Error getting lead status ID {status_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data


# --- Get Lead Campaign Status by Lead ---
def get_lead_campaign_status(lead_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM lead_campaign_status WHERE lead_id = %s AND organization_id = %s"
    conn = None; status_data = None
    try:
        conn = get_connection(); cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cursor.execute(sql, (lead_id, organization_id))
        result = cursor.fetchone()
        if result:
            status_data = dict(result)
    except psycopg2.Error as e:
        logger.error(f"DB Error getting campaign status for lead {lead_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data
# ==========================================
# NEW: ORGANIZATION EMAIL SETTINGS CRUD
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None:
        return None
    logger.warning("ENCRYPTION NOT IMPLEMENTED. Storing sensitive data as plain text!")
    return plain_text

def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None:
        return None
    return encrypted_text

def save_org_email_settings(organization_id: int, settings_data: Dict[str, Any]) -> Optional[Dict]:
    encrypted_password = _encrypt_data(settings_data.get("smtp_password"))
    encrypted_api_key = _encrypt_data(settings_data.get("api_key"))
    encrypted_access_token = _encrypt_data(settings_data.get("access_token"))
    encrypted_refresh_token = _encrypt_data(settings_data.get("refresh_token"))

    columns = [
        "organization_id", "provider_type", "smtp_host", "smtp_port", "smtp_username",
        "encrypted_smtp_password", "encrypted_api_key", "encrypted_access_token",
        "encrypted_refresh_token", "token_expiry", "verified_sender_email",
        "sender_name", "is_configured"
    ]

    values = [
        organization_id,
        settings_data.get("provider_type"),
        settings_data.get("smtp_host"),
        settings_data.get("smtp_port"),
        settings_data.get("smtp_username"),
        encrypted_password,
        encrypted_api_key,
        encrypted_access_token,
        encrypted_refresh_token,
        settings_data.get("token_expiry"),
        settings_data.get("verified_sender_email"),
        settings_data.get("sender_name"),
        int(settings_data.get("is_configured", 0))
    ]

    set_clause_parts = [
        f"{col} = EXCLUDED.{col}" for col in columns if col != 'organization_id'
    ]
    set_clause_parts.append("updated_at = CURRENT_TIMESTAMP")
    set_clause = ", ".join(set_clause_parts)

    placeholders = ", ".join(["%s"] * len(columns))
    sql = f"""
        INSERT INTO organization_email_settings ({", ".join(columns)})
        VALUES ({placeholders})
        ON CONFLICT (organization_id) DO UPDATE SET {set_clause}
    """

    conn = None
    saved_settings = None
    try:
        if not settings_data.get("verified_sender_email"):
            raise ValueError("Verified sender email is required.")
        if not settings_data.get("provider_type"):
            raise ValueError("Provider type is required.")

        conn = get_connection()
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, values)
            conn.commit()

        logger.info(f"Saved/Updated Email Settings for Org ID: {organization_id}")
        saved_settings = get_org_email_settings_from_db(organization_id)

    except psycopg2.Error as e:
        logger.error(f"DB Error saving email settings for Org {organization_id}: {e}")
    except ValueError as ve:
        logger.error(f"Validation Error saving email settings for Org {organization_id}: {ve}")
    except Exception as e:
        logger.error(f"Unexpected error saving email settings for Org {organization_id}: {e}")
    finally:
        if conn:
            conn.close()

    return saved_settings

def get_org_email_settings_from_db(organization_id: int) -> Optional[Dict]:
    sql = """
        SELECT *
        FROM organization_email_settings
        WHERE organization_id = %s
    """

    conn = None
    settings_data = None
    try:
        conn = get_connection()
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(sql, (organization_id,))
                result = cursor.fetchone()

                if result:
                    settings_data = dict(result)
                    settings_data["smtp_password"] = _decrypt_data(settings_data.pop("encrypted_smtp_password", None))
                    settings_data["api_key"] = _decrypt_data(settings_data.pop("encrypted_api_key", None))
                    settings_data["access_token"] = _decrypt_data(settings_data.pop("encrypted_access_token", None))
                    settings_data["refresh_token"] = _decrypt_data(settings_data.pop("encrypted_refresh_token", None))

    except psycopg2.Error as e:
        logger.error(f"DB Error getting email settings for Org {organization_id}: {e}")
    finally:
        if conn:
            conn.close()

    return settings_data
