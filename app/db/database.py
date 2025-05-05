# app/db/database.py

import psycopg2 # Use PostgreSQL driver
from psycopg2.extras import RealDictCursor # Get dict results
from urllib.parse import urlparse # For parsing DATABASE_URL
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone # Use timezone for UTC

# Import logger (assuming configured elsewhere or basic setup)
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

# Import Settings (assuming configured elsewhere)
try:
    from app.utils.config import settings
    logger.info("Successfully imported settings in database.py")
    if not settings or not getattr(settings, 'DATABASE_URL', None) or not settings.DATABASE_URL or settings.DATABASE_URL == "ENV_VAR_DATABASE_URL_NOT_SET":
        logger.critical("DATABASE_URL is not configured in settings or is invalid.")
        settings = None
    elif not settings.DATABASE_URL.startswith(("postgresql://", "postgres://")):
         logger.critical(f"DATABASE_URL does not appear to be a valid PostgreSQL URL: {settings.DATABASE_URL[:50]}...")
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
        result = urlparse(settings.DATABASE_URL)
        db_name = result.path[1:] if result.path else None
        username = result.username
        password = result.password
        hostname = result.hostname
        port = result.port or 5432
        if not all([db_name, username, password, hostname]):
             raise ValueError("DATABASE_URL is missing required components (dbname, user, password, host).")
        conn = psycopg2.connect(dbname=db_name, user=username, password=password, host=hostname, port=port)
        return conn
    except ValueError as ve:
        logger.error(f"Error parsing DATABASE_URL '{settings.DATABASE_URL[:50]}...': {ve}", exc_info=True)
        raise ValueError(f"Invalid DATABASE_URL format: {ve}") from ve
    except psycopg2.OperationalError as e:
        logger.error(f"DATABASE CONNECTION ERROR: Failed to connect to PostgreSQL - {e}", exc_info=True)
        return None
    except Exception as e:
         logger.error(f"Unexpected error getting PostgreSQL connection: {e}", exc_info=True)
         return None

# --- Database Initialization (PostgreSQL Syntax) ---
def initialize_db():
    """Creates/updates tables and indexes for PostgreSQL if they don't exist."""
    logger.info("Initializing PostgreSQL database schema...")
    conn = None
    tables = {
        "organizations": """CREATE TABLE IF NOT EXISTS organizations ( id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "users": """CREATE TABLE IF NOT EXISTS users ( id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, hashed_password TEXT NOT NULL, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "leads": """CREATE TABLE IF NOT EXISTS leads ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT, email TEXT NOT NULL, company TEXT, title TEXT, source TEXT, linkedin_profile TEXT, company_size TEXT, industry TEXT, location TEXT, matched BOOLEAN DEFAULT FALSE, reason TEXT, crm_status TEXT DEFAULT 'pending', appointment_confirmed BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (organization_id, email) );""", # Changed matched/appt_confirmed to BOOLEAN
        # --- MODIFIED ICP Table ---
        "icps": """CREATE TABLE IF NOT EXISTS icps (
                     id SERIAL PRIMARY KEY,
                     organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, -- No longer unique
                     name TEXT NOT NULL DEFAULT 'Default ICP',
                     title_keywords JSONB,
                     industry_keywords JSONB,
                     company_size_rules JSONB,
                     location_keywords JSONB,
                     created_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                     updated_at TIMESTAMPTZ DEFAULT timezone('utc', now())
                   );""",
        "offerings": """CREATE TABLE IF NOT EXISTS offerings ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT, key_features JSONB, target_pain_points JSONB, call_to_action TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (organization_id, name) );""", # Added unique constraint on org_id, name
        # --- MODIFIED CAMPAIGN Table ---
        "email_campaigns": """CREATE TABLE IF NOT EXISTS email_campaigns (
                                id SERIAL PRIMARY KEY,
                                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                                icp_id INTEGER REFERENCES icps(id) ON DELETE SET NULL, -- Added nullable FK to ICP
                                name TEXT NOT NULL,
                                description TEXT,
                                is_active BOOLEAN DEFAULT TRUE,
                                created_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                                updated_at TIMESTAMPTZ DEFAULT timezone('utc', now())
                              );""",
        "campaign_steps": """CREATE TABLE IF NOT EXISTS campaign_steps ( id SERIAL PRIMARY KEY, campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, step_number INTEGER NOT NULL, delay_days INTEGER DEFAULT 1, subject_template TEXT, body_template TEXT, is_ai_crafted BOOLEAN DEFAULT FALSE, follow_up_angle TEXT, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (campaign_id, step_number) );""",
        "lead_campaign_status": """CREATE TABLE IF NOT EXISTS lead_campaign_status ( id SERIAL PRIMARY KEY, lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE, campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, current_step_number INTEGER DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending', last_email_sent_at TIMESTAMPTZ, next_email_due_at TIMESTAMPTZ, last_response_type TEXT, last_response_at TIMESTAMPTZ, error_message TEXT, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (lead_id) );""",
        "organization_email_settings": """CREATE TABLE IF NOT EXISTS organization_email_settings ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE, provider_type TEXT, smtp_host TEXT, smtp_port INTEGER, smtp_username TEXT, encrypted_smtp_password TEXT, encrypted_api_key TEXT, encrypted_access_token TEXT, encrypted_refresh_token TEXT, token_expiry TIMESTAMPTZ, verified_sender_email TEXT NOT NULL, sender_name TEXT, is_configured BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );"""
    }
    indexes = { # Added index for icp_id in campaigns
        "users": ["CREATE INDEX IF NOT EXISTS idx_user_email ON users (email);", "CREATE INDEX IF NOT EXISTS idx_user_organization ON users (organization_id);"],
        "leads": ["CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id);", "CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email);"],
        "icps": ["CREATE INDEX IF NOT EXISTS idx_icp_organization ON icps (organization_id);"],
        "offerings": ["CREATE INDEX IF NOT EXISTS idx_offering_organization ON offerings (organization_id);", "CREATE INDEX IF NOT EXISTS idx_offering_org_name ON offerings (organization_id, name);"],
        "email_campaigns": ["CREATE INDEX IF NOT EXISTS idx_campaign_organization ON email_campaigns (organization_id);", "CREATE INDEX IF NOT EXISTS idx_campaign_icp ON email_campaigns (icp_id);"], # Added index
        "campaign_steps": ["CREATE INDEX IF NOT EXISTS idx_step_campaign ON campaign_steps (campaign_id);", "CREATE INDEX IF NOT EXISTS idx_step_organization ON campaign_steps (organization_id);"],
        "lead_campaign_status": ["CREATE INDEX IF NOT EXISTS idx_status_lead ON lead_campaign_status (lead_id);", "CREATE INDEX IF NOT EXISTS idx_status_campaign ON lead_campaign_status (campaign_id);", "CREATE INDEX IF NOT EXISTS idx_status_organization ON lead_campaign_status (organization_id);", "CREATE INDEX IF NOT EXISTS idx_status_status ON lead_campaign_status (status);", "CREATE INDEX IF NOT EXISTS idx_status_due ON lead_campaign_status (next_email_due_at);"],
        "organization_email_settings": ["CREATE INDEX IF NOT EXISTS idx_email_settings_organization ON organization_email_settings (organization_id);"]
    }
    try:
        conn = get_connection()
        if not conn:
            logger.error("DATABASE ERROR during initialization: Could not establish connection.")
            return
        with conn:
            with conn.cursor() as cursor:
                logger.info("Executing CREATE TABLE IF NOT EXISTS statements...")
                for table_name, sql_create in tables.items():
                    cursor.execute(sql_create)
                    logger.debug(f" -> {table_name.capitalize()} table checked/created.")
                logger.info("Executing CREATE INDEX IF NOT EXISTS statements...")
                for table_name, index_sqls in indexes.items():
                     for sql_index in index_sqls:
                         cursor.execute(sql_index)
                     logger.debug(f" -> {table_name.capitalize()} indexes checked/created.")
        logger.info("Database initialization sequence complete.")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f"DATABASE ERROR during initialization: {error}", exc_info=True)
    finally:
         if conn and not getattr(conn, 'closed', True): conn.close()

# ==========================================
# PLACEHOLDER ENCRYPTION FUNCTIONS - WARNING! (Keep as is for now)
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None: return None
    logger.warning("ENCRYPTION NOT IMPLEMENTED! Sensitive data is NOT being encrypted.")
    return plain_text
def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None: return None
    return encrypted_text

# ==========================================
# HELPER to handle JSON parsing (Keep as is)
# ==========================================
def _parse_json_fields(data_row: Optional[Dict], json_fields: List[str], default_value: Any = None) -> Optional[Dict]:
    # ... (keep existing implementation) ...
    if not data_row: return None
    for field in json_fields:
        field_value = data_row.get(field)
        parsed_value = default_value
        if isinstance(field_value, (dict, list)): parsed_value = field_value
        elif field_value and isinstance(field_value, str):
            try: parsed_value = json.loads(field_value)
            except json.JSONDecodeError: logger.warning(f"Could not parse JSON string for field '{field}' in row ID {data_row.get('id')}")
        elif field in data_row and field_value is None: parsed_value = default_value
        data_row[field] = parsed_value
    return data_row

# ==========================================
# ORGANIZATION CRUD (Keep as is)
# ==========================================
def create_organization(name: str) -> Optional[Dict]:
def get_organization_by_id(organization_id: int) -> Optional[Dict]:
def get_organization_by_name(name: str) -> Optional[Dict]:
def get_all_organizations() -> List[Dict]:
   

# ==========================================
# USER CRUD (Keep as is)
# ==========================================
def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
def get_user_by_id(user_id: int) -> Optional[Dict]:
def get_user_by_email(email: str) -> Optional[Dict]:
def get_users_by_organization(organization_id: int) -> List[Dict]:
   
# ==========================================
# LEAD CRUD (Keep as is, ensure correct boolean handling)
# ==========================================
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
def get_lead_by_id(lead_id: int, organization_id: int) -> Optional[Dict]:
def get_lead_by_email(email: str, organization_id: int) -> Optional[Dict]:
def get_leads_by_organization(organization_id: int, offset: int = 0, limit: int = 100) -> List[Dict]:
def update_lead_partial(lead_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
def delete_lead(lead_id: int, organization_id: int) -> bool:
 

# ==========================================
# REFACTORED ICP CRUD OPERATIONS
# ==========================================

def create_icp(organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    """Creates a new ICP definition for an organization."""
    conn = None; saved_icp = None; new_id = None
    # Ensure keys exist and handle JSON serialization
    params = {
        "organization_id": organization_id,
        "name": icp_definition.get("name", f"New ICP"), # Require a name on creation via API model
        "title_keywords": json.dumps(icp_definition.get("title_keywords") or []),
        "industry_keywords": json.dumps(icp_definition.get("industry_keywords") or []),
        "company_size_rules": json.dumps(icp_definition.get("company_size_rules") or {}),
        "location_keywords": json.dumps(icp_definition.get("location_keywords") or []),
    }
    insert_columns = list(params.keys()) # Get columns from params
    values_placeholders = ", ".join([f"%({col})s" for col in insert_columns])

    sql = f"""
        INSERT INTO icps ({", ".join(insert_columns)})
        VALUES ({values_placeholders})
        RETURNING id;
    """
    try:
        if not params["name"]: raise ValueError("ICP name cannot be empty")
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                returned_id_row = cursor.fetchone()
                if returned_id_row and 'id' in returned_id_row:
                    new_id = returned_id_row['id']
                    logger.info(f"Created ICP '{params['name']}' (ID: {new_id}) for Org ID: {organization_id}")
                else:
                    logger.error(f"ICP creation for Org ID {organization_id} did not return ID.")
                    return None

        if new_id:
            saved_icp = get_icp_by_id(new_id, organization_id) # Fetch the newly created ICP

    except ValueError as ve:
         logger.error(f"Validation error creating ICP for Org ID {organization_id}: {ve}")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating ICP for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_icp


def update_icp(icp_id: int, organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    """Updates an existing ICP definition."""
    conn = None; updated_icp = None; success = False
    # Prepare fields to update
    params = {
        "icp_id": icp_id,
        "organization_id": organization_id,
        "name": icp_definition.get("name"),
        "title_keywords": json.dumps(icp_definition.get("title_keywords")), # Allow None to clear
        "industry_keywords": json.dumps(icp_definition.get("industry_keywords")),
        "company_size_rules": json.dumps(icp_definition.get("company_size_rules")),
        "location_keywords": json.dumps(icp_definition.get("location_keywords")),
        "updated_at": datetime.now(timezone.utc)
    }
    # Filter out None values unless explicitly allowed by DB schema/logic
    update_fields = {k: v for k, v in params.items() if v is not None and k not in ['icp_id', 'organization_id']}

    if not update_fields or not params["name"]: # Need at least name
        logger.warning(f"No valid fields provided for updating ICP ID {icp_id} or name is missing.")
        return get_icp_by_id(icp_id, organization_id) # Return current state

    set_clause_parts = [f"{key} = %({key})s" for key in update_fields.keys()]
    set_clause = ", ".join(set_clause_parts)

    sql = f"""
        UPDATE icps SET {set_clause}
        WHERE id = %(icp_id)s AND organization_id = %(organization_id)s;
        """
    # Merge icp_id and organization_id back into params for execution
    params_for_exec = update_fields
    params_for_exec["icp_id"] = icp_id
    params_for_exec["organization_id"] = organization_id

    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params_for_exec)
                if cursor.rowcount > 0:
                    success = True
                    logger.info(f"Updated ICP ID {icp_id} for Org ID {organization_id}")
                else:
                    logger.warning(f"ICP ID {icp_id} not found for Org ID {organization_id} during update, or no changes made.")

        if success:
            updated_icp = get_icp_by_id(icp_id, organization_id) # Fetch updated ICP

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating ICP ID {icp_id} for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return updated_icp


def get_icp_by_id(icp_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a specific ICP definition by its ID and organization ID."""
    sql = "SELECT * FROM icps WHERE id = %s AND organization_id = %s;"
    conn = None; icp_data = None
    json_fields_to_parse = ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (icp_id, organization_id))
            result = cursor.fetchone()
            if result:
                icp_data = _parse_json_fields(dict(result), json_fields_to_parse, default_value=None)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting ICP ID {icp_id} for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return icp_data


def get_icps_by_organization_id(organization_id: int) -> List[Dict]:
    """Fetches all ICP definitions for an organization, parsing JSON fields."""
    sql = "SELECT * FROM icps WHERE organization_id = %s ORDER BY name;" # Order by name
    conn = None; icps_list = []
    json_fields_to_parse = ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id,))
            results = cursor.fetchall()
            for row in results:
                parsed_row = _parse_json_fields(dict(row), json_fields_to_parse, default_value=None)
                if parsed_row: icps_list.append(parsed_row)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting all ICPs for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return icps_list


def delete_icp(icp_id: int, organization_id: int) -> bool:
    """Deletes a specific ICP definition."""
    sql = "DELETE FROM icps WHERE id = %s AND organization_id = %s;"
    conn = None; deleted = False
    try:
        conn = get_connection()
        if not conn: return False
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (icp_id, organization_id))
                if cursor.rowcount > 0:
                    deleted = True
                    logger.info(f"Deleted ICP ID {icp_id} for Org ID {organization_id}")
                else:
                    logger.warning(f"ICP ID {icp_id} not found for Org ID {organization_id} during delete.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error deleting ICP ID {icp_id} for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return deleted


# ==========================================
# OFFERING CRUD OPERATIONS (Keep as is, ensure _parse works)
# ==========================================
def _parse_offering_json_fields(offering_row: Dict) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def create_offering(organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def get_offering_by_id(offering_id: int, organization_id: int) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def get_offerings_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    # ... (keep existing implementation) ...
def update_offering(offering_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    # ... (keep existing implementation - Needs implementation) ...
def delete_offering(offering_id: int, organization_id: int) -> bool:
    # ... (keep existing implementation - Needs implementation) ...


# ===========================================================
# CAMPAIGN/STEP/STATUS CRUD (MODIFIED FOR ICP LINK)
# ===========================================================

# --- Campaign CRUD ---
def create_campaign(organization_id: int, name: str, description: Optional[str] = None, is_active: bool = True, icp_id: Optional[int] = None) -> Optional[Dict]: # Added icp_id
    sql = "INSERT INTO email_campaigns (organization_id, name, description, is_active, icp_id) VALUES (%s, %s, %s, %s, %s) RETURNING id" # Added icp_id column
    params = (organization_id, name, description, is_active, icp_id) # Added icp_id value
    conn = None; campaign_data = None; new_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
                if result: new_id = result[0]
        if new_id:
            logger.info(f"Created campaign '{name}' (ID: {new_id}, ICP ID: {icp_id}) for Org {organization_id}")
            campaign_data = get_campaign_by_id(new_id, organization_id)
        else:
             logger.error(f"Campaign creation for '{name}' did not return ID.")
    except psycopg2.IntegrityError as ie:
         logger.warning(f"DB Integrity Error creating campaign '{name}' for Org {organization_id}: {ie} (Bad FK?)")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating campaign for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return campaign_data

def get_campaign_by_id(campaign_id: int, organization_id: int) -> Optional[Dict]:
    # Select icp_id as well
    sql = "SELECT ec.*, i.name as icp_name FROM email_campaigns ec LEFT JOIN icps i ON ec.icp_id = i.id WHERE ec.id = %s AND ec.organization_id = %s"
    conn = None; campaign = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (campaign_id, organization_id))
            result = cursor.fetchone()
            if result: campaign = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting campaign ID {campaign_id} for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return campaign

def get_campaigns_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    # Select icp_id as well
    sql = "SELECT ec.*, i.name as icp_name FROM email_campaigns ec LEFT JOIN icps i ON ec.icp_id = i.id WHERE ec.organization_id = %s"
    params = [organization_id]
    if active_only:
        sql += " AND ec.is_active = TRUE"
    sql += " ORDER BY ec.name"
    conn = None; campaigns = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, params)
            results = cursor.fetchall()
            for row in results: campaigns.append(dict(row))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting campaigns for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return campaigns

# --- Step CRUD (Keep as is) ---
def create_campaign_step(campaign_id: int, organization_id: int, step_number: int, delay_days: int, subject: Optional[str], body: Optional[str], is_ai: bool = False, follow_up_angle: Optional[str] = None) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def get_campaign_step_by_id(step_id: int, organization_id: int) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def get_steps_for_campaign(campaign_id: int, organization_id: int) -> List[Dict]:
    # ... (keep existing implementation) ...
def get_next_campaign_step(campaign_id: int, organization_id: int, current_step_number: int) -> Optional[Dict]:
    # ... (keep existing implementation) ...

# --- Lead Status CRUD (Keep as is) ---
def enroll_lead_in_campaign(lead_id: int, campaign_id: int, organization_id: int) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def get_active_leads_due_for_step(organization_id: Optional[int] = None) -> List[Dict]:
    # ... (keep existing implementation) ...
def get_lead_campaign_status_by_id(status_id: int, organization_id: int) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def get_lead_campaign_status(lead_id: int, organization_id: int) -> Optional[Dict]:
    # ... (keep existing implementation) ...

# ==========================================
# ORGANIZATION EMAIL SETTINGS CRUD (Keep as is)
# ==========================================
def save_org_email_settings(organization_id: int, settings_data: Dict[str, Any]) -> Optional[Dict]:
    # ... (keep existing implementation) ...
def get_org_email_settings_from_db(organization_id: int) -> Optional[Dict]:
    # ... (keep existing implementation) ...

# ==========================================
# Run initialization if script is executed directly (Keep as is)
# ==========================================
if __name__ == "__main__":
    logger.info("Running database.py directly, attempting initialization...")
    if settings:
        initialize_db()
        logger.info("Direct execution initialization attempt finished.")
    else:
        logger.error("Cannot initialize database directly because settings (DATABASE_URL) are not configured.")
