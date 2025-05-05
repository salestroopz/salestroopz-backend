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
# ORGANIZATION CRUD (Psycopg2)
# ==========================================
def create_organization(name: str) -> Optional[Dict]:
    # PASTE YOUR ACTUAL IMPLEMENTATION HERE (indented)
    sql = "INSERT INTO organizations (name) VALUES (%s) RETURNING id;"
    # ... (rest of implementation from previous correct version) ...
    pass # Remove pass once implementation is pasted

def get_organization_by_id(organization_id: int) -> Optional[Dict]:
    # PASTE YOUR ACTUAL IMPLEMENTATION HERE (indented)
    sql = "SELECT * FROM organizations WHERE id = %s;"
    # ... (rest of implementation from previous correct version) ...
    pass # Remove pass once implementation is pasted

def get_organization_by_name(name: str) -> Optional[Dict]:
    """Fetches organization by name."""
    logger.warning("Function 'get_organization_by_name' is not implemented.")
    # Add placeholder implementation or 'pass'
    pass # <-- ADD INDENTED PASS

def get_all_organizations() -> List[Dict]:
    """Fetches all organizations."""
    logger.warning("Function 'get_all_organizations' is not implemented.")
    # Add placeholder implementation or 'pass'
    pass # <-- ADD INDENTED PASS


# ==========================================
# USER CRUD (Psycopg2)
# ==========================================
def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    # PASTE YOUR ACTUAL IMPLEMENTATION HERE (indented)
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (%s, %s, %s) RETURNING id;"
    # ... (rest of implementation from previous correct version) ...
    pass # Remove pass once implementation is pasted

def get_user_by_id(user_id: int) -> Optional[Dict]:
    # PASTE YOUR ACTUAL IMPLEMENTATION HERE (indented)
    sql = """ SELECT u.id, u.email, ... """
    # ... (rest of implementation from previous correct version) ...
    pass # Remove pass once implementation is pasted

def get_user_by_email(email: str) -> Optional[Dict]:
    # PASTE YOUR ACTUAL IMPLEMENTATION HERE (indented)
    sql = """ SELECT u.id, u.email, ... """
    # ... (rest of implementation from previous correct version) ...
    pass # Remove pass once implementation is pasted

def get_users_by_organization(organization_id: int) -> List[Dict]:
    """Fetches all users for a given organization."""
    logger.warning("Function 'get_users_by_organization' is not implemented.")
    # Add placeholder implementation or 'pass'
    pass # <-- ADD INDENTED PASS
    
# ==========================================
# LEAD CRUD OPERATIONS (Psycopg2) - NEEDS REVIEW for logic consistency
# ==========================================
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
    """Creates or updates a lead based on organization_id and email."""
    # PASTE YOUR FULL save_lead IMPLEMENTATION HERE (indented)
    # columns = [ "organization_id", ... ]
    # ... (rest of save_lead logic) ...
    pass # Remove pass once implementation is pasted

def get_lead_by_id(lead_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a lead by its ID and organization ID."""
    logger.warning("Function 'get_lead_by_id' is not implemented.")
    pass # <-- ADD INDENTED PASS

def get_lead_by_email(email: str, organization_id: int) -> Optional[Dict]:
    """Fetches a lead by its email and organization ID."""
    logger.warning("Function 'get_lead_by_email' is not implemented.")
    pass # <-- ADD INDENTED PASS

def get_leads_by_organization(organization_id: int, offset: int = 0, limit: int = 100) -> List[Dict]:
    """Fetches leads for an organization with pagination."""
    logger.warning("Function 'get_leads_by_organization' is not implemented.")
    pass # <-- ADD INDENTED PASS

def update_lead_partial(lead_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates specific fields for a lead."""
    logger.warning("Function 'update_lead_partial' is not implemented.")
    pass # <-- ADD INDENTED PASS

def delete_lead(lead_id: int, organization_id: int) -> bool:
    """Deletes a lead."""
    logger.warning("Function 'delete_lead' is not implemented.")
    pass # <-- ADD INDENTED PASS (Return False if keeping placeholder)
    # return False

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
# OFFERING CRUD OPERATIONS (Psycopg2)
# ==========================================
def _parse_offering_json_fields(offering_row: Dict) -> Optional[Dict]: # Input is already dict
    """Helper to parse JSON fields from an Offering dictionary row."""
    # PASTE YOUR FULL _parse_offering_json_fields IMPLEMENTATION HERE (indented)
    # if not offering_row: return None
    # ... (rest of parsing logic) ...
    pass # Remove pass once implementation is pasted

def create_offering(organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    """Creates a new offering for an organization."""
    # PASTE YOUR FULL create_offering IMPLEMENTATION HERE (indented)
    # columns = ["organization_id", ... ]
    # ... (rest of create logic) ...
    pass # Remove pass once implementation is pasted

def get_offering_by_id(offering_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches an offering by its ID and organization ID, parsing JSON."""
    # PASTE YOUR FULL get_offering_by_id IMPLEMENTATION HERE (indented)
    # sql = "SELECT * FROM offerings WHERE id = %s AND organization_id = %s;"
    # ... (rest of get logic) ...
    pass # Remove pass once implementation is pasted

def get_offerings_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    """Fetches offerings for an organization, parsing JSON."""
    # PASTE YOUR FULL get_offerings_by_organization IMPLEMENTATION HERE (indented)
    # sql = "SELECT * FROM offerings WHERE organization_id = %s"
    # ... (rest of list logic) ...
    pass # Remove pass once implementation is pasted

def update_offering(offering_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates an existing offering."""
    logger.warning("Function 'update_offering' is not implemented.")
    # Return current state as placeholder or just pass
    pass # <-- ADD INDENTED PASS
    # return get_offering_by_id(offering_id, organization_id)

def delete_offering(offering_id: int, organization_id: int) -> bool:
    """Deletes an offering."""
    logger.warning("Function 'delete_offering' is not implemented.")
    pass # <-- ADD INDENTED PASS
    # return False


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

# ===========================================================
# CAMPAIGN STEP CRUD (Corrected for PostgreSQL)
# ===========================================================
def create_campaign_step(campaign_id: int, organization_id: int, step_number: int, delay_days: int, subject: Optional[str], body: Optional[str], is_ai: bool = False, follow_up_angle: Optional[str] = None) -> Optional[Dict]:
    """Creates a new step within a campaign."""
    sql = """
        INSERT INTO campaign_steps
        (campaign_id, organization_id, step_number, delay_days, subject_template, body_template, is_ai_crafted, follow_up_angle)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
        """ # Use %s placeholders and RETURNING id
    params = (campaign_id, organization_id, step_number, delay_days, subject, body, is_ai, follow_up_angle)
    conn = None; new_id = None; step_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
             with conn.cursor() as cursor: # Default cursor for RETURNING
                  try:
                       cursor.execute(sql, params)
                       result = cursor.fetchone()
                       if result: new_id = result[0]
                  except psycopg2.IntegrityError as ie:
                       conn.rollback() # Explicit rollback needed within 'with conn:' if we handle error here
                       logger.error(f"DB Integrity Error creating step {step_number} for Camp {campaign_id}: {ie} (Duplicate step number?)")
                       return None # Return None on integrity error

        if new_id:
             logger.info(f"Created step {step_number} (ID: {new_id}) for Campaign {campaign_id}, Org {organization_id}")
             step_data = get_campaign_step_by_id(new_id, organization_id) # Fetch full data
        else:
             logger.error(f"Step creation for Camp {campaign_id}, Step {step_number} did not return ID.")

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating step {step_number} for Camp {campaign_id}: {e}", exc_info=True)
        # Rollback happens automatically due to 'with conn:' if exception bubbles up
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step_data

def get_campaign_step_by_id(step_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a specific campaign step by its ID."""
    sql = "SELECT * FROM campaign_steps WHERE id = %s AND organization_id = %s" # Use %s
    conn = None; step = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Use RealDictCursor
            cursor.execute(sql, (step_id, organization_id))
            result = cursor.fetchone()
            if result: step = dict(result)
    except (Exception, psycopg2.Error) as e: # Use psycopg2.Error
        logger.error(f"DB Error getting step ID {step_id} for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step

def get_steps_for_campaign(campaign_id: int, organization_id: int) -> List[Dict]:
    """Fetches all steps for a specific campaign, ordered by step number."""
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = %s AND organization_id = %s ORDER BY step_number" # Use %s
    conn = None; steps = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Use RealDictCursor
            cursor.execute(sql, (campaign_id, organization_id))
            results = cursor.fetchall()
            for row in results: steps.append(dict(row))
    except (Exception, psycopg2.Error) as e: # Use psycopg2.Error
        logger.error(f"DB Error getting steps for Camp {campaign_id}, Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return steps

def get_next_campaign_step(campaign_id: int, organization_id: int, current_step_number: int) -> Optional[Dict]:
    """Fetches the next step in sequence for a campaign."""
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = %s AND organization_id = %s AND step_number = %s LIMIT 1" # Use %s
    next_step_number = current_step_number + 1
    conn = None; step_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Use RealDictCursor
            cursor.execute(sql, (campaign_id, organization_id, next_step_number))
            result = cursor.fetchone()
            if result: step_data = dict(result)
    except (Exception, psycopg2.Error) as e: # Use psycopg2.Error
        logger.error(f"DB Error getting next step ({next_step_number}) for Camp {campaign_id}, Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step_data

# --- TODO: Add update_campaign_step and delete_campaign_step ---
def update_campaign_step(step_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
     logger.warning(f"Function 'update_campaign_step' (ID: {step_id}) is not implemented.")
     pass # IMPLEMENT ME
     return get_campaign_step_by_id(step_id, organization_id) # Return current as placeholder

def delete_campaign_step(step_id: int, organization_id: int) -> bool:
     logger.warning(f"Function 'delete_campaign_step' (ID: {step_id}) is not implemented.")
     pass # IMPLEMENT ME
     return False

# ===========================================================
# LEAD CAMPAIGN STATUS CRUD (Corrected for PostgreSQL)
# ===========================================================
def enroll_lead_in_campaign(lead_id: int, campaign_id: int, organization_id: int) -> Optional[Dict]:
    """Enrolls a lead into a campaign by creating a status record."""
    sql = """INSERT INTO lead_campaign_status (lead_id, campaign_id, organization_id, status, current_step_number)
             VALUES (%s, %s, %s, 'active', 0) RETURNING id""" # Use %s and RETURNING
    params = (lead_id, campaign_id, organization_id)
    conn = None; status_data = None; status_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
            with conn.cursor() as cursor: # Default cursor for RETURNING
                try:
                    cursor.execute(sql, params)
                    result = cursor.fetchone()
                    if result: status_id = result[0]
                except psycopg2.IntegrityError as ie:
                    conn.rollback() # Explicit rollback
                    logger.warning(f"DB Integrity Error enrolling lead {lead_id} in camp {campaign_id}: {ie} (Likely already enrolled or FK issue)")
                    # Fetch existing status if already enrolled
                    return get_lead_campaign_status(lead_id, organization_id)

        if status_id:
            logger.info(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {status_id})")
            status_data = get_lead_campaign_status_by_id(status_id, organization_id) # Fetch full data
        else:
            logger.error(f"Lead enrollment for lead {lead_id}, camp {campaign_id} did not return ID.")

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}", exc_info=True)
        # Rollback happened automatically if exception bubbled up from 'with conn:'
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return status_data

def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates the status record for a lead in a campaign."""
    allowed_fields = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message"}
    valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

    # Optional: Add timezone handling for datetime fields if necessary before saving
    # ...

    if not valid_updates:
         logger.warning(f"No valid fields provided for updating lead status ID {status_id}")
         # Return current status without making changes
         return get_lead_campaign_status_by_id(status_id, organization_id)


    # Use named placeholders %(key)s for psycopg2 dictionary execution
    set_parts = [f"{key} = %({key})s" for key in valid_updates.keys()]
    # Always update 'updated_at' timestamp
    set_parts.append("updated_at = timezone('utc', now())") # Use PostgreSQL function
    set_clause = ", ".join(set_parts)

    params = valid_updates.copy()
    params["status_id"] = status_id
    params["organization_id"] = organization_id

    sql = f"UPDATE lead_campaign_status SET {set_clause} WHERE id = %(status_id)s AND organization_id = %(organization_id)s"

    conn = None; success = False
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                if cursor.rowcount > 0:
                    success = True
                    logger.debug(f"Updated lead campaign status ID {status_id}")
                else:
                    # This means the status_id + organization_id combination wasn't found
                    logger.warning(f"Lead campaign status ID {status_id} not found for Org {organization_id} during update.")
                    success = False

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating lead status ID {status_id}: {e}", exc_info=True)
        success = False # Mark as failed on error
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()

    # Fetch and return updated status only if update affected a row
    return get_lead_campaign_status_by_id(status_id, organization_id) if success else None


def get_active_leads_due_for_step(organization_id: Optional[int] = None) -> List[Dict]:
    """Fetches active leads potentially due for the next step. Further filtering needed in application logic."""
    logger.debug(f"Fetching active leads {f'for Org {organization_id}' if organization_id else 'across all orgs'}.")
    leads_due = []; conn = None
    # Select relevant fields including lead email, campaign name for context
    sql = """
        SELECT lcs.*, c.name as campaign_name, l.email as lead_email
        FROM lead_campaign_status lcs
        JOIN email_campaigns c ON lcs.campaign_id = c.id
        JOIN leads l ON lcs.lead_id = l.id
        WHERE lcs.status = 'active'
        """
    params = []
    if organization_id is not None:
        sql += " AND lcs.organization_id = %s"
        params.append(organization_id)
    # Order results consistently
    sql += " ORDER BY lcs.organization_id, lcs.next_email_due_at ASC NULLS FIRST, lcs.last_email_sent_at ASC NULLS FIRST"

    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, params)
            results = cursor.fetchall()
            if results:
                 leads_due = [dict(row) for row in results] # Convert all rows to dict
            logger.debug(f"DB: Found {len(leads_due)} total active leads matching initial criteria {f'for Org {organization_id}' if organization_id else ''}.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting active leads{f' for Org {organization_id}' if organization_id else ''}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()

    return leads_due


def get_lead_campaign_status_by_id(status_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a specific lead campaign status record by its ID."""
    sql = "SELECT * FROM lead_campaign_status WHERE id = %s AND organization_id = %s" # Use %s
    conn = None; status_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Use RealDictCursor
            cursor.execute(sql, (status_id, organization_id))
            result = cursor.fetchone()
            if result: status_data = dict(result)
    except (Exception, psycopg2.Error) as e: # Use psycopg2.Error
        logger.error(f"DB Error getting lead status ID {status_id} for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return status_data

def get_lead_campaign_status(lead_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches the campaign status for a specific lead."""
    sql = "SELECT * FROM lead_campaign_status WHERE lead_id = %s AND organization_id = %s" # Use %s
    conn = None; status_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Use RealDictCursor
            cursor.execute(sql, (lead_id, organization_id))
            result = cursor.fetchone()
            if result: status_data = dict(result)
    except (Exception, psycopg2.Error) as e: # Use psycopg2.Error
        logger.error(f"DB Error getting campaign status for lead {lead_id}, Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return status_data

# ==========================================
# ORGANIZATION EMAIL SETTINGS CRUD (Psycopg2)
# ==========================================
def save_org_email_settings(organization_id: int, settings_data: Dict[str, Any]) -> Optional[Dict]:
    """Saves or updates email settings for an organization, 'encrypting' sensitive fields."""
    # Use the placeholder encryption - replace with real implementation!
    encrypted_password = _encrypt_data(settings_data.get("smtp_password"))
    encrypted_api_key = _encrypt_data(settings_data.get("api_key"))
    encrypted_access_token = _encrypt_data(settings_data.get("access_token"))
    encrypted_refresh_token = _encrypt_data(settings_data.get("refresh_token"))

    columns = [ "organization_id", "provider_type", "smtp_host", "smtp_port", "smtp_username", "encrypted_smtp_password", "encrypted_api_key", "encrypted_access_token", "encrypted_refresh_token", "token_expiry", "verified_sender_email", "sender_name", "is_configured" ]

    # Prepare params dict matching column order for %s placeholders if not using named execution
    params = {
        "organization_id": organization_id,
        "provider_type": settings_data.get("provider_type"),
        "smtp_host": settings_data.get("smtp_host"),
        "smtp_port": settings_data.get("smtp_port"), # Ensure it's int or None
        "smtp_username": settings_data.get("smtp_username"),
        "encrypted_smtp_password": encrypted_password,
        "encrypted_api_key": encrypted_api_key,
        "encrypted_access_token": encrypted_access_token,
        "encrypted_refresh_token": encrypted_refresh_token,
        "token_expiry": settings_data.get("token_expiry"), # Ensure it's datetime or None
        "verified_sender_email": settings_data.get("verified_sender_email"),
        "sender_name": settings_data.get("sender_name"),
        "is_configured": bool(settings_data.get("is_configured", False)), # Ensure boolean
        "updated_at": datetime.now(timezone.utc) # Add updated_at timestamp
    }

    # Validate required fields
    if not params["verified_sender_email"]: raise ValueError("Verified sender email is required.")
    if not params["provider_type"]: raise ValueError("Provider type is required.")
    # Convert port to int if present, else None
    if params["smtp_port"] is not None:
        try: params["smtp_port"] = int(params["smtp_port"])
        except (ValueError, TypeError): raise ValueError("SMTP port must be a valid integer.")

    insert_cols_str = ", ".join(columns)
    values_placeholders = ", ".join([f"%({col})s" for col in columns])
    # Exclude unique key from update, include updated_at
    update_cols = [f"{col} = EXCLUDED.{col}" for col in columns if col != 'organization_id']
    update_cols.append("updated_at = %(updated_at)s")
    update_clause = ", ".join(update_cols)

    # Use ON CONFLICT for PostgreSQL UPSERT
    sql = f"""
        INSERT INTO organization_email_settings ({insert_cols_str})
        VALUES ({values_placeholders})
        ON CONFLICT (organization_id) DO UPDATE SET {update_clause}
        RETURNING id;
    """

    conn = None; saved_settings = None; returned_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params) # Pass dictionary for named placeholders
                returned_id_row = cursor.fetchone()
                if returned_id_row and 'id' in returned_id_row:
                    returned_id = returned_id_row['id']
                    logger.info(f"Saved/Updated Email Settings for Org ID: {organization_id}")
                else:
                     logger.warning(f"Email settings upsert for Org {organization_id} did not return ID.")


        # Fetch updated settings outside transaction block
        # Fetch by org ID as it's unique
        saved_settings = get_org_email_settings_from_db(organization_id)

    except ValueError as ve: # Catch specific validation errors
        logger.error(f"Validation Error saving email settings for Org {organization_id}: {ve}")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error saving email settings for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()

    return saved_settings


def get_org_email_settings_from_db(organization_id: int) -> Optional[Dict]:
    """Fetches email settings for an organization, 'decrypting' sensitive fields."""
    sql = "SELECT * FROM organization_email_settings WHERE organization_id = %s" # Use %s

    conn = None
    settings_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Use context manager
            with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Use RealDictCursor
                cursor.execute(sql, (organization_id,)) # Pass parameters as tuple
                result = cursor.fetchone()

                if result:
                    settings_data = dict(result)
                    # Use placeholder decryption - replace with real implementation!
                    settings_data["smtp_password"] = _decrypt_data(settings_data.pop("encrypted_smtp_password", None))
                    settings_data["api_key"] = _decrypt_data(settings_data.pop("encrypted_api_key", None))
                    settings_data["access_token"] = _decrypt_data(settings_data.pop("encrypted_access_token", None))
                    settings_data["refresh_token"] = _decrypt_data(settings_data.pop("encrypted_refresh_token", None))

    except (Exception, psycopg2.Error) as e: # Catch specific psycopg2 errors
        logger.error(f"DB Error getting email settings for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True):
            conn.close()

    return settings_data

# Ensure the next block (like `if __name__ == "__main__":`) starts at column 0
