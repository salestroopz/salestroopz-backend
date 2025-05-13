# app/db/database.py

import psycopg2 # Use PostgreSQL driver
from psycopg2.extras import RealDictCursor # Get dict results
from urllib.parse import urlparse # For parsing DATABASE_URL
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone, timedelta # Use timezone for UTC
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from .models import Lead, LeadCampaignStatus, EmailCampaign # Add EmailCampaign if not already imported
from app.schemas import LeadStatusEnum

# Import logger (assuming configured elsewhere or basic setup)
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    # Basic config if logger not found externally
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

# Import Settings (assuming configured elsewhere)
try:
    from app.utils.config import settings
    logger.info("Successfully imported settings in database.py")
    if not settings or not getattr(settings, 'DATABASE_URL', None) or not settings.DATABASE_URL or settings.DATABASE_URL == "ENV_VAR_DATABASE_URL_NOT_SET":
        logger.critical("DATABASE_URL is not configured in settings or is invalid.")
        settings = None # Mark settings as invalid for DB operations
    elif not settings.DATABASE_URL.startswith(("postgresql://", "postgres://")):
         logger.critical(f"DATABASE_URL does not appear to be a valid PostgreSQL URL: {settings.DATABASE_URL[:50]}...") # Log only prefix
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
        db_name = result.path[1:] if result.path else None
        username = result.username
        password = result.password
        hostname = result.hostname
        port = result.port or 5432

        if not all([db_name, username, password, hostname]):
             raise ValueError("DATABASE_URL is missing required components (dbname, user, password, host).")

        conn = psycopg2.connect(
            dbname=db_name,
            user=username,
            password=password,
            host=hostname,
            port=port
        )
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
    logger.info("Initializing PostgreSQL database schema (with reply handling tables)...")
    conn = None
    tables = {
        "organizations": """CREATE TABLE IF NOT EXISTS organizations ( id SERIAL PRIMARY KEY, name TEXT NOT NULL UNIQUE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "users": """CREATE TABLE IF NOT EXISTS users ( id SERIAL PRIMARY KEY, email TEXT NOT NULL UNIQUE, hashed_password TEXT NOT NULL, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "icps": """CREATE TABLE IF NOT EXISTS icps ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT NOT NULL DEFAULT 'Default ICP', title_keywords JSONB, industry_keywords JSONB, company_size_rules JSONB, location_keywords JSONB, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        "offerings": """CREATE TABLE IF NOT EXISTS offerings ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, name TEXT NOT NULL, description TEXT, key_features JSONB, target_pain_points JSONB, call_to_action TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), UNIQUE (organization_id, name) );""",
        "leads": """
            CREATE TABLE IF NOT EXISTS leads ( 
                id SERIAL PRIMARY KEY, 
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, 
                name TEXT, email TEXT NOT NULL, company TEXT, title TEXT, source TEXT, 
                linkedin_profile TEXT, company_size TEXT, industry TEXT, location TEXT, 
                matched BOOLEAN DEFAULT FALSE, 
                reason TEXT, 
                crm_status TEXT DEFAULT 'pending', 
                appointment_confirmed BOOLEAN DEFAULT FALSE,
                icp_match_id INTEGER REFERENCES icps(id) ON DELETE SET NULL, -- ADDED FOR ICP MATCHING
                created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), 
                updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), 
                UNIQUE (organization_id, email) 
            );""",
        "email_campaigns": """
            CREATE TABLE IF NOT EXISTS email_campaigns (
                id SERIAL PRIMARY KEY,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                icp_id INTEGER REFERENCES icps(id) ON DELETE SET NULL,
                offering_id INTEGER REFERENCES offerings(id) ON DELETE SET NULL,
                name TEXT NOT NULL, description TEXT, is_active BOOLEAN DEFAULT FALSE, -- Default is_active to FALSE
                ai_status TEXT DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                updated_at TIMESTAMPTZ DEFAULT timezone('utc', now())
            );""",
        "campaign_steps": """
            CREATE TABLE IF NOT EXISTS campaign_steps (
                id SERIAL PRIMARY KEY,
                campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                step_number INTEGER NOT NULL, delay_days INTEGER DEFAULT 1,
                subject_template TEXT, body_template TEXT,
                is_ai_crafted BOOLEAN DEFAULT FALSE, follow_up_angle TEXT,
                created_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                UNIQUE (campaign_id, step_number)
            );""",
        "lead_campaign_status": """
            CREATE TABLE IF NOT EXISTS lead_campaign_status ( 
                id SERIAL PRIMARY KEY, 
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE, 
                campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE, 
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE, 
                current_step_number INTEGER DEFAULT 0, 
                status VARCHAR(255) NOT NULL DEFAULT 'pending', -- Increased length
                last_email_sent_at TIMESTAMPTZ, 
                next_email_due_at TIMESTAMPTZ, 
                last_response_type VARCHAR(255), -- Increased length
                last_response_at TIMESTAMPTZ, 
                error_message TEXT, 
                user_notes TEXT, -- NEW field for user notes
                created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), 
                updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()), 
                UNIQUE (lead_id) 
            );""",
        "organization_email_settings": """CREATE TABLE IF NOT EXISTS organization_email_settings ( id SERIAL PRIMARY KEY, organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id) ON DELETE CASCADE, provider_type TEXT, smtp_host TEXT, smtp_port INTEGER, smtp_username TEXT, encrypted_smtp_password TEXT, encrypted_api_key TEXT, encrypted_access_token TEXT, encrypted_refresh_token TEXT, token_expiry TIMESTAMPTZ, verified_sender_email TEXT NOT NULL, sender_name TEXT, is_configured BOOLEAN DEFAULT FALSE, created_at TIMESTAMPTZ DEFAULT timezone('utc', now()), updated_at TIMESTAMPTZ DEFAULT timezone('utc', now()) );""",
        # --- NEW TABLES FOR REPLY HANDLING ---
        "outgoing_email_log": """
            CREATE TABLE IF NOT EXISTS outgoing_email_log (
                id SERIAL PRIMARY KEY,
                lead_campaign_status_id INTEGER REFERENCES lead_campaign_status(id) ON DELETE SET NULL,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE,
                campaign_step_id INTEGER REFERENCES campaign_steps(id) ON DELETE SET NULL,
                message_id_header VARCHAR(512) NOT NULL, 
                sent_at TIMESTAMPTZ DEFAULT timezone('utc', now()),
                to_email VARCHAR(255) NOT NULL,
                subject TEXT,
                CONSTRAINT uq_org_message_id UNIQUE (organization_id, message_id_header) -- Message-ID should be unique per org
            );""",
        "email_replies": """
            CREATE TABLE IF NOT EXISTS email_replies (
                id SERIAL PRIMARY KEY,
                outgoing_email_log_id INTEGER REFERENCES outgoing_email_log(id) ON DELETE SET NULL,
                lead_campaign_status_id INTEGER REFERENCES lead_campaign_status(id) ON DELETE CASCADE,
                organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
                campaign_id INTEGER NOT NULL REFERENCES email_campaigns(id) ON DELETE CASCADE,
                received_at TIMESTAMPTZ NOT NULL,
                from_email VARCHAR(255) NOT NULL,
                reply_subject TEXT,
                raw_body_text TEXT,
                cleaned_reply_text TEXT,
                ai_classification VARCHAR(100),
                ai_summary TEXT,
                ai_extracted_entities JSONB,
                is_actioned_by_user BOOLEAN DEFAULT FALSE,
                user_action_notes TEXT, -- Notes specific to action on this reply
                created_at TIMESTAMPTZ DEFAULT timezone('utc', now())
            );"""
    }
    indexes = {
        "users": ["CREATE INDEX IF NOT EXISTS idx_user_email ON users (email);", "CREATE INDEX IF NOT EXISTS idx_user_organization ON users (organization_id);"],
        "leads": [
            "CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id);", 
            "CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email);",
            "CREATE INDEX IF NOT EXISTS idx_lead_icp_match ON leads (icp_match_id);" # ADDED
            ],
        "icps": ["CREATE INDEX IF NOT EXISTS idx_icp_organization ON icps (organization_id);"],
        "offerings": ["CREATE INDEX IF NOT EXISTS idx_offering_organization ON offerings (organization_id);", "CREATE INDEX IF NOT EXISTS idx_offering_org_name ON offerings (organization_id, name);"],
        "email_campaigns": [
            "CREATE INDEX IF NOT EXISTS idx_campaign_organization ON email_campaigns (organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_campaign_icp ON email_campaigns (icp_id);",
            "CREATE INDEX IF NOT EXISTS idx_campaign_offering ON email_campaigns (offering_id);",
            "CREATE INDEX IF NOT EXISTS idx_campaign_ai_status ON email_campaigns (ai_status);"
        ],
        "campaign_steps": ["CREATE INDEX IF NOT EXISTS idx_step_campaign ON campaign_steps (campaign_id);", "CREATE INDEX IF NOT EXISTS idx_step_organization ON campaign_steps (organization_id);"],
        "lead_campaign_status": [
            "CREATE INDEX IF NOT EXISTS idx_lcs_lead ON lead_campaign_status (lead_id);", # Renamed for consistency
            "CREATE INDEX IF NOT EXISTS idx_lcs_campaign ON lead_campaign_status (campaign_id);",
            "CREATE INDEX IF NOT EXISTS idx_lcs_organization ON lead_campaign_status (organization_id);",
            "CREATE INDEX IF NOT EXISTS idx_lcs_status ON lead_campaign_status (status);",
            "CREATE INDEX IF NOT EXISTS idx_lcs_due ON lead_campaign_status (next_email_due_at);"
        ],
        "organization_email_settings": ["CREATE INDEX IF NOT EXISTS idx_email_settings_organization ON organization_email_settings (organization_id);"],
        # --- NEW INDEXES ---
        "outgoing_email_log": [
            "CREATE INDEX IF NOT EXISTS idx_oel_lcs_id ON outgoing_email_log (lead_campaign_status_id);",
            "CREATE INDEX IF NOT EXISTS idx_oel_org_msg_id ON outgoing_email_log (organization_id, message_id_header);", # For unique constraint
            "CREATE INDEX IF NOT EXISTS idx_oel_lead_id ON outgoing_email_log (lead_id);",
            "CREATE INDEX IF NOT EXISTS idx_oel_sent_at ON outgoing_email_log (sent_at);"
        ],
        "email_replies": [
            "CREATE INDEX IF NOT EXISTS idx_er_oel_id ON email_replies (outgoing_email_log_id);",
            "CREATE INDEX IF NOT EXISTS idx_er_lcs_id ON email_replies (lead_campaign_status_id);",
            "CREATE INDEX IF NOT EXISTS idx_er_org_id_class_actioned ON email_replies (organization_id, ai_classification, is_actioned_by_user);", # For dashboard
            "CREATE INDEX IF NOT EXISTS idx_er_received_at ON email_replies (received_at);"
        ]
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
                    try:
                        cursor.execute(sql_create)
                        logger.debug(f" -> Table '{table_name}' DDL executed.")
                    except Exception as table_e:
                        logger.error(f"Failed to execute DDL for table '{table_name}': {table_e}", exc_info=True)
                        raise # Re-raise to stop initialization if a table fails
                logger.info("Executing CREATE INDEX IF NOT EXISTS statements...")
                for table_name, index_sqls in indexes.items():
                     for sql_index in index_sqls:
                         try:
                            cursor.execute(sql_index)
                         except Exception as index_e:
                             logger.error(f"Failed to execute DDL for index on table '{table_name}': {sql_index}. Error: {index_e}", exc_info=True)
                             # Decide if you want to raise here or just log and continue
                     logger.debug(f" -> Indexes for '{table_name}' DDL executed.")
        logger.info("Database initialization sequence complete.")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f"DATABASE ERROR during initialization (outer try): {error}", exc_info=True)
    finally:
         if conn and not getattr(conn, 'closed', True): conn.close()

# ==========================================
# PLACEHOLDER ENCRYPTION FUNCTIONS - WARNING!
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None: return None
    # logger.warning("ENCRYPTION NOT IMPLEMENTED! Sensitive data is NOT being encrypted.") # Reduce noise for now
    return plain_text
def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None: return None
    return encrypted_text

# ==========================================
# HELPER to handle JSON parsing
# ==========================================
def _parse_json_fields(data_row: Optional[Dict], json_fields: List[str], default_value: Any = None) -> Optional[Dict]:
    if not data_row: return None
    for field in json_fields:
        field_value = data_row.get(field)
        parsed_value = default_value
        if isinstance(field_value, (dict, list)): parsed_value = field_value
        elif field_value and isinstance(field_value, str):
            try: parsed_value = json.loads(field_value)
            except json.JSONDecodeError: logger.warning(f"Could not parse JSON string for field '{field}' in row ID {data_row.get('id')}")
        elif field in data_row and field_value is None: parsed_value = default_value # Handle explicit NULLs in JSONB
        data_row[field] = parsed_value
    return data_row

# ==========================================
# ORGANIZATION CRUD OPERATIONS (Psycopg2)
# ==========================================
def create_organization(name: str) -> Optional[Dict]:
    """Creates an organization or returns existing one by name."""
    sql_insert = "INSERT INTO organizations (name) VALUES (%s) RETURNING id;"
    conn = None; org_data = None; org_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(sql_insert, (name,)); new_id_row = cursor.fetchone()
                    if new_id_row and 'id' in new_id_row:
                        org_id = new_id_row['id']
                        logger.info(f"Created org '{name}' ID: {org_id}")
                    else:
                         logger.error(f"Org creation for '{name}' did not return ID.")
                         return None
                except psycopg2.IntegrityError:
                    logger.warning(f"Org name '{name}' already exists. Fetching existing.")
                    conn.rollback() # Important before another query in same transaction block
                    return get_organization_by_name(name)

        if org_id:
             org_data = get_organization_by_id(org_id)

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating/getting org '{name}': {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return org_data

def get_organization_by_id(organization_id: int) -> Optional[Dict]:
    """Fetches organization data by ID."""
    sql = "SELECT * FROM organizations WHERE id = %s;"
    conn = None; org_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id,)); result = cursor.fetchone()
            if result: org_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return org_data

def get_organization_by_name(name: str) -> Optional[Dict]:
    """Fetches organization data by its unique name."""
    sql = "SELECT * FROM organizations WHERE name = %s;"
    conn = None; org_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (name,)); result = cursor.fetchone()
            if result: org_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting org by name '{name}': {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return org_data

def get_all_organizations() -> List[Dict]:
    """Fetches all organizations."""
    sql = "SELECT * FROM organizations ORDER BY name;"
    conn = None; org_list = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql); results = cursor.fetchall()
            for row in results: org_list.append(dict(row))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting all organizations: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return org_list


# ==========================================
# USER CRUD (Psycopg2)
# ==========================================
def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    """Creates a user or returns existing if email exists."""
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (%s, %s, %s) RETURNING id;"
    conn = None; user_data = None; user_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, (email, hashed_password, organization_id))
                    new_id_row = cursor.fetchone()
                    if new_id_row and 'id' in new_id_row:
                         user_id = new_id_row['id']
                         logger.info(f"Created user '{email}' (ID: {user_id}) for org ID {organization_id}")
                    else:
                         logger.error(f"User creation for '{email}' did not return ID.")
                         return None
                except psycopg2.IntegrityError as e:
                    conn.rollback()
                    logger.warning(f"DB Integrity error creating user '{email}' (email exists or bad org_id?): {e}")
                    return get_user_by_email(email)

        if user_id:
            user_data = get_user_by_id(user_id)

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating user '{email}': {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return user_data

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Fetches user data and organization name by user ID."""
    sql = """
        SELECT
            u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.id = %s;
        """
    conn = None; user_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (user_id,)); result = cursor.fetchone()
            if result: user_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting user ID {user_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return user_data

def get_user_by_email(email: str) -> Optional[Dict]:
    """Fetches user data and organization name by email."""
    sql = """
        SELECT
            u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.email = %s;
        """
    conn = None; user_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (email,)); result = cursor.fetchone()
            if result: user_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting user by email {email}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return user_data

def get_users_by_organization(organization_id: int) -> List[Dict]:
    """Fetches all users for a given organization."""
    sql = """
        SELECT
            u.id, u.email, u.organization_id, o.name as organization_name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.organization_id = %s ORDER BY u.email;
        """
    conn = None; users_list = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id,)); results = cursor.fetchall()
            for row in results: users_list.append(dict(row))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting users for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return users_list


# ==========================================
# LEAD CRUD OPERATIONS (Psycopg2)
# ==========================================
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
    """Creates or updates a lead based on organization_id and email."""
    columns = [ "organization_id", "name", "email", "company", "title", "source", "linkedin_profile", "company_size", "industry", "location", "matched", "reason", "crm_status", "appointment_confirmed", "updated_at" ]
    params = {col: lead_data.get(col) for col in columns if col != "updated_at"} # updated_at handled by DB or explicit set
    params['organization_id'] = organization_id
    if not params.get('email'):
        logger.warning(f"Skipping lead save for org {organization_id}: missing email")
        return None
    params['matched'] = bool(params.get('matched', False))
    params['appointment_confirmed'] = bool(params.get('appointment_confirmed', False))
    params['updated_at'] = datetime.now(timezone.utc) # Set updated_at for insert/update

    insert_cols_str = ", ".join(columns)
    values_placeholders = ", ".join([f"%({col})s" for col in columns])
    update_cols = [f"{col} = EXCLUDED.{col}" for col in columns if col not in ['id', 'organization_id', 'email', 'created_at']]
    update_clause = ", ".join(update_cols)

    sql = f"""
        INSERT INTO leads ({insert_cols_str})
        VALUES ({values_placeholders})
        ON CONFLICT (organization_id, email) DO UPDATE SET {update_clause}
        RETURNING id;
    """
    conn = None; saved_lead = None; returned_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                returned_id_row = cursor.fetchone()
                if returned_id_row and 'id' in returned_id_row:
                    returned_id = returned_id_row['id']
                else:
                     logger.warning(f"Lead upsert for {params.get('email')}, Org {organization_id} did not return ID consistently.")

        if returned_id:
            saved_lead = get_lead_by_id(returned_id, organization_id)
            if saved_lead:
                 logger.debug(f"Successfully saved/updated lead ID {saved_lead['id']} for org {organization_id}")
            else: # Fallback
                 saved_lead = get_lead_by_email(params['email'], organization_id)
        else: # Fallback if RETURNING ID failed
            saved_lead = get_lead_by_email(params['email'], organization_id)

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error saving lead for org {organization_id}, email {params.get('email')}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_lead

def get_lead_by_id(lead_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM leads WHERE id = %s AND organization_id = %s;"
    conn = None; lead_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (lead_id, organization_id)); result = cursor.fetchone()
            if result: lead_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting lead ID {lead_id} for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return lead_data

def get_lead_by_email(email: str, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM leads WHERE email = %s AND organization_id = %s;"
    conn = None; lead_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (email, organization_id)); result = cursor.fetchone()
            if result: lead_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting lead by email '{email}' for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return lead_data

def get_leads_by_organization(organization_id: int, offset: int = 0, limit: int = 100) -> List[Dict]:
    sql = "SELECT * FROM leads WHERE organization_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s;"
    conn = None; leads_list = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id, limit, offset)); results = cursor.fetchall()
            for row in results: leads_list.append(dict(row))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting leads for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return leads_list

def update_lead_partial(lead_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    allowed_fields = {"name", "company", "title", "source", "linkedin_profile", "company_size", "industry", "location", "matched", "reason", "crm_status", "appointment_confirmed"}
    valid_updates = {}
    for key, value in updates.items():
        if key in allowed_fields:
            if key in ['matched', 'appointment_confirmed']: valid_updates[key] = bool(value)
            else: valid_updates[key] = value
    if not valid_updates:
        logger.warning(f"No valid fields provided for updating lead ID {lead_id}")
        return get_lead_by_id(lead_id, organization_id)

    set_parts = [f"{key} = %({key})s" for key in valid_updates.keys()]
    set_parts.append("updated_at = timezone('utc', now())")
    set_clause = ", ".join(set_parts)
    params_for_exec = valid_updates.copy()
    params_for_exec["lead_id"] = lead_id
    params_for_exec["organization_id"] = organization_id
    sql = f"UPDATE leads SET {set_clause} WHERE id = %(lead_id)s AND organization_id = %(organization_id)s RETURNING id;"
    conn = None; success = False
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params_for_exec)
                if cursor.fetchone(): # Check if RETURNING id returned something
                    success = True
                    logger.info(f"Partially updated lead ID {lead_id} for Org {organization_id}")
                else:
                    logger.warning(f"Lead ID {lead_id} not found for Org {organization_id} during partial update or no change.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error partially updating lead ID {lead_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return get_lead_by_id(lead_id, organization_id) if success else None

def delete_lead(lead_id: int, organization_id: int) -> bool:
    sql = "DELETE FROM leads WHERE id = %s AND organization_id = %s;"
    conn = None; deleted = False
    try:
        conn = get_connection()
        if not conn: return False
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (lead_id, organization_id))
                if cursor.rowcount > 0:
                    deleted = True
                    logger.info(f"Deleted lead ID {lead_id} for Org {organization_id}")
                else:
                    logger.warning(f"Lead ID {lead_id} not found for Org {organization_id} during delete.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error deleting lead ID {lead_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return deleted

# ==========================================
# ICP CRUD OPERATIONS
# ==========================================
def create_icp(organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    conn = None; saved_icp = None; new_id = None
    params = {
        "organization_id": organization_id, "name": icp_definition.get("name", f"New ICP"),
        "title_keywords": json.dumps(icp_definition.get("title_keywords") or []),
        "industry_keywords": json.dumps(icp_definition.get("industry_keywords") or []),
        "company_size_rules": json.dumps(icp_definition.get("company_size_rules") or {}),
        "location_keywords": json.dumps(icp_definition.get("location_keywords") or []),
        "updated_at": datetime.now(timezone.utc) # Also set on create
    }
    insert_columns = [k for k in params.keys() if k != "updated_at"] # updated_at is set by default or explicit
    insert_columns.append("updated_at") # ensure it's in the insert list
    
    values_placeholders = ", ".join([f"%({col})s" for col in insert_columns])
    sql = f""" INSERT INTO icps ({", ".join(insert_columns)}) VALUES ({values_placeholders}) RETURNING id; """
    try:
        if not params["name"]: raise ValueError("ICP name cannot be empty")
        conn = get_connection();
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
        if new_id: saved_icp = get_icp_by_id(new_id, organization_id)
    except ValueError as ve: logger.error(f"Validation error creating ICP for Org ID {organization_id}: {ve}")
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error creating ICP for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_icp

def update_icp(icp_id: int, organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    conn = None; success = False
    current_icp = get_icp_by_id(icp_id, organization_id)
    if not current_icp:
        logger.warning(f"ICP ID {icp_id} not found for Org ID {organization_id} for update.")
        return None

    update_fields = {}
    if "name" in icp_definition and icp_definition["name"] is not None:
        update_fields["name"] = icp_definition["name"]
    if "title_keywords" in icp_definition: # Allow setting to empty list
        update_fields["title_keywords"] = json.dumps(icp_definition["title_keywords"])
    if "industry_keywords" in icp_definition:
        update_fields["industry_keywords"] = json.dumps(icp_definition["industry_keywords"])
    if "company_size_rules" in icp_definition:
        update_fields["company_size_rules"] = json.dumps(icp_definition["company_size_rules"])
    if "location_keywords" in icp_definition:
        update_fields["location_keywords"] = json.dumps(icp_definition["location_keywords"])

    if not update_fields:
        logger.info(f"No fields to update for ICP ID {icp_id}.")
        return current_icp # Return current if no actual changes

    update_fields["updated_at"] = datetime.now(timezone.utc)
    set_clause_parts = [f"{key} = %({key})s" for key in update_fields.keys()]
    set_clause = ", ".join(set_clause_parts)
    sql = f""" UPDATE icps SET {set_clause} WHERE id = %(icp_id)s AND organization_id = %(organization_id)s RETURNING id; """
    
    params_for_exec = update_fields.copy()
    params_for_exec["icp_id"] = icp_id
    params_for_exec["organization_id"] = organization_id
    
    try:
        conn = get_connection();
        if not conn: return None
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params_for_exec)
                if cursor.fetchone(): success = True; logger.info(f"Updated ICP ID {icp_id} for Org ID {organization_id}")
                else: logger.warning(f"ICP ID {icp_id} update for Org ID {organization_id} reported no rows affected.")
        return get_icp_by_id(icp_id, organization_id) if success else current_icp # return new or old on failure
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error updating ICP ID {icp_id} for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return current_icp # Fallback

def get_icp_by_id(icp_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM icps WHERE id = %s AND organization_id = %s;"
    conn = None; icp_data = None
    json_fields_to_parse = ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (icp_id, organization_id)); result = cursor.fetchone()
            if result: icp_data = _parse_json_fields(dict(result), json_fields_to_parse, default_value=None) # Use default_value=None for potentially null JSON fields
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error getting ICP ID {icp_id} for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return icp_data

def get_icps_by_organization_id(organization_id: int) -> List[Dict]:
    sql = "SELECT * FROM icps WHERE organization_id = %s ORDER BY name;"
    conn = None; icps_list = []
    json_fields_to_parse = ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    try:
        conn = get_connection();
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id,)); results = cursor.fetchall()
            for row in results:
                parsed_row = _parse_json_fields(dict(row), json_fields_to_parse, default_value=None)
                if parsed_row: icps_list.append(parsed_row)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error getting all ICPs for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return icps_list

def delete_icp(icp_id: int, organization_id: int) -> bool:
    sql = "DELETE FROM icps WHERE id = %s AND organization_id = %s;"
    conn = None; deleted = False
    try:
        conn = get_connection();
        if not conn: return False
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (icp_id, organization_id))
                if cursor.rowcount > 0: deleted = True; logger.info(f"Deleted ICP ID {icp_id} for Org ID {organization_id}")
                else: logger.warning(f"ICP ID {icp_id} not found for Org ID {organization_id} during delete.")
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error deleting ICP ID {icp_id} for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return deleted


# ==========================================
# OFFERING CRUD OPERATIONS (Psycopg2)
# ==========================================
def _parse_offering_json_fields(offering_row: Dict) -> Optional[Dict]:
    if not offering_row: return None
    json_fields = ["key_features", "target_pain_points"]
    for field in json_fields:
        field_value = offering_row.get(field); parsed_value = None # Default to None
        if isinstance(field_value, list): parsed_value = field_value
        elif isinstance(field_value, dict): logger.warning(f"Offering field '{field}' ID {offering_row.get('id')} was dict, expected list or null."); parsed_value = None
        elif isinstance(field_value, str):
            try: parsed = json.loads(field_value); parsed_value = parsed if isinstance(parsed, list) else None
            except json.JSONDecodeError: logger.warning(f"Could not parse JSON for Offering field '{field}' ID {offering_row.get('id')}")
        offering_row[field] = parsed_value
    return offering_row

def create_offering(organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    columns = ["organization_id", "name", "description", "key_features", "target_pain_points", "call_to_action", "is_active", "updated_at"]
    params = {
        "organization_id": organization_id, "name": offering_data.get("name"), "description": offering_data.get("description"),
        "key_features": json.dumps(offering_data.get("key_features") or None), # Store null if empty
        "target_pain_points": json.dumps(offering_data.get("target_pain_points") or None), # Store null if empty
        "call_to_action": offering_data.get("call_to_action"), "is_active": bool(offering_data.get("is_active", True)),
        "updated_at": datetime.now(timezone.utc)
    }
    sql = f"INSERT INTO offerings ({', '.join(columns)}) VALUES ({', '.join([f'%({col})s' for col in columns])}) RETURNING id;"
    conn = None; saved_offering = None; offering_id = None
    try:
        if not params.get("name"): raise ValueError("Offering name cannot be empty")
        conn = get_connection();
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                 try:
                      cursor.execute(sql, params); new_id_row = cursor.fetchone()
                      if new_id_row and 'id' in new_id_row: offering_id = new_id_row['id']; logger.info(f"Created offering '{params['name']}' (ID: {offering_id}) for Org ID {organization_id}")
                      else: logger.error(f"Offering creation for '{params['name']}' did not return ID."); return None
                 except psycopg2.IntegrityError as ie:
                      conn.rollback()
                      logger.warning(f"DB Integrity Error creating offering '{params['name']}': {ie} (Likely duplicate name for org)")
                      return None

        if offering_id: saved_offering = get_offering_by_id(offering_id, organization_id)
    except ValueError as ve: logger.error(f"Validation error creating offering for Org ID {organization_id}: {ve}")
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error creating offering for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_offering

def get_offering_by_id(offering_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM offerings WHERE id = %s AND organization_id = %s;"
    conn = None; offering_data = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
             cursor.execute(sql, (offering_id, organization_id)); result = cursor.fetchone()
             if result: offering_data = _parse_offering_json_fields(dict(result))
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error getting offering ID {offering_id} for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return offering_data

def get_offerings_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    sql = "SELECT * FROM offerings WHERE organization_id = %s"
    params = [organization_id]
    if active_only: sql += " AND is_active = TRUE"
    sql += " ORDER BY name;"
    conn = None; offerings = []
    try:
        conn = get_connection();
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, tuple(params)); results = cursor.fetchall()
            for row in results:
                parsed_row = _parse_offering_json_fields(dict(row))
                if parsed_row: offerings.append(parsed_row)
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error getting offerings for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return offerings

def update_offering(offering_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    current_offering = get_offering_by_id(offering_id, organization_id)
    if not current_offering:
        logger.warning(f"Offering ID {offering_id} not found for Org {organization_id} during update.")
        return None

    update_fields = {}
    if "name" in updates and updates["name"] is not None:
        update_fields["name"] = updates["name"]
    if "description" in updates: # Allow setting to null
        update_fields["description"] = updates["description"]
    if "key_features" in updates: # Allow setting to empty or null
        update_fields["key_features"] = json.dumps(updates["key_features"] or None)
    if "target_pain_points" in updates:
        update_fields["target_pain_points"] = json.dumps(updates["target_pain_points"] or None)
    if "call_to_action" in updates:
        update_fields["call_to_action"] = updates["call_to_action"]
    if "is_active" in updates and updates["is_active"] is not None:
        update_fields["is_active"] = bool(updates["is_active"])

    if not update_fields:
        logger.info(f"No fields to update for Offering ID {offering_id}.")
        return current_offering

    update_fields["updated_at"] = datetime.now(timezone.utc)
    set_clause_parts = [f"{key} = %({key})s" for key in update_fields.keys()]
    set_clause = ", ".join(set_clause_parts)
    sql = f""" UPDATE offerings SET {set_clause} WHERE id = %(offering_id)s AND organization_id = %(organization_id)s RETURNING id; """
    
    params_for_exec = update_fields.copy()
    params_for_exec["offering_id"] = offering_id
    params_for_exec["organization_id"] = organization_id

    conn = None; success = False
    try:
        conn = get_connection();
        if not conn: return current_offering # Return old if no connection
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params_for_exec)
                if cursor.fetchone(): success = True; logger.info(f"Updated Offering ID {offering_id} for Org {organization_id}")
                else: logger.warning(f"Offering ID {offering_id} update for Org {organization_id} reported no rows affected.")
        return get_offering_by_id(offering_id, organization_id) if success else current_offering
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating offering ID {offering_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return current_offering # Fallback

def delete_offering(offering_id: int, organization_id: int) -> bool:
    sql = "DELETE FROM offerings WHERE id = %s AND organization_id = %s;"
    conn = None; deleted = False
    try:
        conn = get_connection();
        if not conn: return False
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (offering_id, organization_id))
                if cursor.rowcount > 0: deleted = True; logger.info(f"Deleted Offering ID {offering_id} for Org {organization_id}")
                else: logger.warning(f"Offering ID {offering_id} not found for Org {organization_id} during delete.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error deleting offering ID {offering_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return deleted


# ===========================================================
# CAMPAIGN CRUD (MODIFIED FOR AI GENERATION)
# ===========================================================
def create_campaign(organization_id: int, name: str, description: Optional[str] = None,
                    is_active: bool = True, icp_id: Optional[int] = None,
                    offering_id: Optional[int] = None, ai_status: str = "pending") -> Optional[Dict]:
    """Creates a new campaign, linking ICP and Offering, and setting AI status."""
    sql = """
        INSERT INTO email_campaigns
        (organization_id, name, description, is_active, icp_id, offering_id, ai_status, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, timezone('utc', now())) RETURNING id
    """
    params = (organization_id, name, description, is_active, icp_id, offering_id, ai_status)
    conn = None; campaign_data = None; new_id = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn: # Auto-commit
            with conn.cursor() as cursor:
                cursor.execute(sql, params); result = cursor.fetchone()
                if result: new_id = result[0]
        if new_id:
            logger.info(f"Created campaign '{name}' (ID: {new_id}, ICP ID: {icp_id}, Offering ID: {offering_id}, AI Status: {ai_status}) for Org {organization_id}")
            campaign_data = get_campaign_by_id(new_id, organization_id) # Fetch full data including joins
        else:
            logger.error(f"Campaign creation for '{name}' did not return ID.")
    except psycopg2.IntegrityError as ie:
        logger.warning(f"DB Integrity Error creating campaign '{name}' for Org {organization_id}: {ie} (Bad FK or unique constraint?)")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating campaign for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return campaign_data

def get_campaign_by_id(campaign_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a specific campaign, joining ICP and Offering names."""
    sql = """
        SELECT ec.*, i.name as icp_name, o.name as offering_name
        FROM email_campaigns ec
        LEFT JOIN icps i ON ec.icp_id = i.id
        LEFT JOIN offerings o ON ec.offering_id = o.id
        WHERE ec.id = %s AND ec.organization_id = %s
    """
    conn = None; campaign = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (campaign_id, organization_id)); result = cursor.fetchone()
            if result: campaign = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting campaign ID {campaign_id} for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return campaign

def get_campaigns_by_organization(organization_id: int, active_only: Optional[bool] = None) -> List[Dict]:
    """Fetches campaigns for an organization, joining ICP and Offering names."""
    sql_base = """
        SELECT ec.*, i.name as icp_name, o.name as offering_name
        FROM email_campaigns ec
        LEFT JOIN icps i ON ec.icp_id = i.id
        LEFT JOIN offerings o ON ec.offering_id = o.id
        WHERE ec.organization_id = %s
    """
    params = [organization_id]
    if active_only is not None: # Allow filtering by active status (True or False)
        sql_base += " AND ec.is_active = %s"
        params.append(active_only)
    sql_final = sql_base + " ORDER BY ec.name"

    conn = None; campaigns = []
    try:
        conn = get_connection();
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql_final, tuple(params)); results = cursor.fetchall()
            for row in results: campaigns.append(dict(row))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting campaigns for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return campaigns

def update_campaign(campaign_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates a campaign's basic info, ICP, or Offering links."""
    current_campaign = get_campaign_by_id(campaign_id, organization_id)
    if not current_campaign:
        logger.warning(f"Campaign ID {campaign_id} not found for Org {organization_id} for update.")
        return None

    allowed_fields = {"name", "description", "is_active", "icp_id", "offering_id", "ai_status"}
    update_fields = {}

    for field in allowed_fields:
        if field in updates: # Check if key exists in updates
            # Special handling for icp_id and offering_id to allow unsetting (setting to None)
            if field in ["icp_id", "offering_id"] and updates[field] is None:
                update_fields[field] = None
            elif updates[field] is not None: # For other fields, only update if not None
                 update_fields[field] = updates[field]
            # If updates[field] is None and it's not icp_id/offering_id, we don't add it to update_fields
            # to avoid unintentionally nullifying fields like name or description.
            # However, is_active should be settable to False.
            elif field == "is_active" and updates[field] is False:
                update_fields[field] = False


    if not update_fields:
        logger.info(f"No valid fields to update for Campaign ID {campaign_id}.")
        return current_campaign

    update_fields["updated_at"] = datetime.now(timezone.utc)
    set_clause_parts = [f"{key} = %({key})s" for key in update_fields.keys()]
    set_clause = ", ".join(set_clause_parts)
    sql = f""" UPDATE email_campaigns SET {set_clause} WHERE id = %(campaign_id)s AND organization_id = %(organization_id)s RETURNING id; """
    
    params_for_exec = update_fields.copy()
    params_for_exec["campaign_id"] = campaign_id
    params_for_exec["organization_id"] = organization_id

    conn = None; success = False
    try:
        conn = get_connection()
        if not conn: return current_campaign
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params_for_exec)
                if cursor.fetchone(): success = True; logger.info(f"Updated Campaign ID {campaign_id} for Org {organization_id}")
                else: logger.warning(f"Campaign ID {campaign_id} update for Org {organization_id} reported no rows affected.")
        return get_campaign_by_id(campaign_id, organization_id) if success else current_campaign
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating campaign ID {campaign_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return current_campaign # Fallback

def update_campaign_ai_status(campaign_id: int, organization_id: int, ai_status: str) -> Optional[Dict]:
    """Specifically updates the AI status of a campaign."""
    sql = """
        UPDATE email_campaigns
        SET ai_status = %s, updated_at = timezone('utc', now())
        WHERE id = %s AND organization_id = %s
        RETURNING id
    """
    conn = None; success = False
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (ai_status, campaign_id, organization_id))
                if cursor.fetchone(): success = True; logger.info(f"Updated AI status to '{ai_status}' for Campaign ID {campaign_id}")
                else: logger.warning(f"Campaign ID {campaign_id} not found for Org {organization_id} when updating AI status.")
        return get_campaign_by_id(campaign_id, organization_id) if success else None
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating AI status for campaign ID {campaign_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return None

def delete_campaign(campaign_id: int, organization_id: int) -> bool:
    """Deletes a campaign. Steps are deleted via CASCADE."""
    sql = "DELETE FROM email_campaigns WHERE id = %s AND organization_id = %s;"
    conn = None; deleted = False
    try:
        conn = get_connection();
        if not conn: return False
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (campaign_id, organization_id))
                if cursor.rowcount > 0: deleted = True; logger.info(f"Deleted Campaign ID {campaign_id} for Org {organization_id}")
                else: logger.warning(f"Campaign ID {campaign_id} not found for Org {organization_id} during delete.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error deleting campaign ID {campaign_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return deleted

# ===========================================================
# CAMPAIGN STEP CRUD
# ===========================================================
def create_campaign_step(campaign_id: int, organization_id: int, step_number: int, delay_days: int,
                         subject_template: Optional[str], body_template: Optional[str],
                         is_ai_crafted: bool = False, follow_up_angle: Optional[str] = None) -> Optional[Dict]:
    """Creates a new step within a campaign, including follow_up_angle."""
    sql = """
        INSERT INTO campaign_steps
        (campaign_id, organization_id, step_number, delay_days, subject_template, body_template, is_ai_crafted, follow_up_angle, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, timezone('utc', now())) RETURNING id;
    """
    params = (campaign_id, organization_id, step_number, delay_days, subject_template, body_template, is_ai_crafted, follow_up_angle)
    conn = None; new_id = None; step_data = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn:
             with conn.cursor() as cursor:
                  try:
                       cursor.execute(sql, params); result = cursor.fetchone()
                       if result: new_id = result[0]
                  except psycopg2.IntegrityError as ie:
                       conn.rollback(); logger.error(f"DB Integrity Error creating step {step_number} for Camp {campaign_id}: {ie} (Likely duplicate step_number or bad FK)"); return None
        if new_id:
            logger.info(f"Created step {step_number} (ID: {new_id}) for Campaign {campaign_id}, Org {organization_id}")
            step_data = get_campaign_step_by_id(new_id, organization_id)
        else:
            logger.error(f"Step creation for Camp {campaign_id}, Step {step_number} did not return ID.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating step {step_number} for Camp {campaign_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step_data

def get_campaign_step_by_id(step_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a specific campaign step by its ID."""
    sql = "SELECT * FROM campaign_steps WHERE id = %s AND organization_id = %s"
    conn = None; step = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (step_id, organization_id)); result = cursor.fetchone()
            if result: step = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting step ID {step_id} for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step

def get_steps_for_campaign(campaign_id: int, organization_id: int) -> List[Dict]:
    """Fetches all steps for a specific campaign, ordered by step number."""
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = %s AND organization_id = %s ORDER BY step_number"
    conn = None; steps = []
    try:
        conn = get_connection();
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (campaign_id, organization_id)); results = cursor.fetchall()
            for row in results: steps.append(dict(row))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting steps for Camp {campaign_id}, Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return steps

def get_next_campaign_step(campaign_id: int, organization_id: int, current_step_number: int) -> Optional[Dict]:
    """Fetches the next step in sequence for a campaign."""
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = %s AND organization_id = %s AND step_number = %s LIMIT 1"
    next_step_number = current_step_number + 1
    conn = None; step_data = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (campaign_id, organization_id, next_step_number)); result = cursor.fetchone()
            if result: step_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting next step ({next_step_number}) for Camp {campaign_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step_data

def update_campaign_step(step_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    current_step = get_campaign_step_by_id(step_id, organization_id)
    if not current_step:
        logger.warning(f"Campaign Step ID {step_id} not found for Org {organization_id} for update.")
        return None

    allowed_fields = {"step_number", "delay_days", "subject_template", "body_template", "is_ai_crafted", "follow_up_angle"}
    update_fields = {}
    for field in allowed_fields:
        if field in updates: # Allow explicitly setting fields to None or False
            update_fields[field] = updates[field]
    
    if not update_fields:
        logger.info(f"No valid fields to update for Campaign Step ID {step_id}.")
        return current_step

    update_fields["updated_at"] = datetime.now(timezone.utc)
    set_clause_parts = [f"{key} = %({key})s" for key in update_fields.keys()]
    set_clause = ", ".join(set_clause_parts)
    sql = f""" UPDATE campaign_steps SET {set_clause} WHERE id = %(step_id)s AND organization_id = %(organization_id)s RETURNING id; """
    
    params_for_exec = update_fields.copy()
    params_for_exec["step_id"] = step_id
    params_for_exec["organization_id"] = organization_id

    conn = None; success = False
    try:
        conn = get_connection()
        if not conn: return current_step
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params_for_exec)
                if cursor.fetchone(): success = True; logger.info(f"Updated Campaign Step ID {step_id} for Org {organization_id}")
                else: logger.warning(f"Campaign Step ID {step_id} update for Org {organization_id} reported no rows affected.")
        return get_campaign_step_by_id(step_id, organization_id) if success else current_step
    except psycopg2.IntegrityError as ie:
        logger.error(f"DB Integrity Error updating step {step_id}: {ie} (Likely duplicate step_number for campaign)")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating campaign step ID {step_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return current_step # Fallback


def delete_campaign_step(step_id: int, organization_id: int) -> bool:
    sql = "DELETE FROM campaign_steps WHERE id = %s AND organization_id = %s;"
    conn = None; deleted = False
    try:
        conn = get_connection();
        if not conn: return False
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (step_id, organization_id))
                if cursor.rowcount > 0: deleted = True; logger.info(f"Deleted Campaign Step ID {step_id} for Org {organization_id}")
                else: logger.warning(f"Campaign Step ID {step_id} not found for Org {organization_id} during delete.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error deleting campaign step ID {step_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return deleted


# ===========================================================
# LEAD CAMPAIGN STATUS CRUD
# ===========================================================
def enroll_lead_in_campaign(lead_id: int, campaign_id: int, organization_id: int) -> Optional[Dict]:
    sql = """INSERT INTO lead_campaign_status (lead_id, campaign_id, organization_id, status, current_step_number, updated_at) VALUES (%s, %s, %s, 'active', 0, timezone('utc', now())) RETURNING id"""
    params = (lead_id, campaign_id, organization_id)
    conn = None; status_data = None; status_id = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(sql, params); result = cursor.fetchone()
                    if result: status_id = result[0]
                except psycopg2.IntegrityError as ie:
                    conn.rollback(); logger.warning(f"DB Integrity Error enrolling lead {lead_id} in camp {campaign_id}: {ie} (lead already in a campaign due to UNIQUE(lead_id) or bad FK?)");
                    return get_lead_campaign_status(lead_id, organization_id) # Return existing if unique constraint hit
        if status_id:
            logger.info(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {status_id})")
            status_data = get_lead_campaign_status_by_id(status_id, organization_id)
        else:
            logger.error(f"Lead enrollment for lead {lead_id}, camp {campaign_id} did not return ID and no integrity error caught.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return status_data

def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    allowed_fields = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message"}
    valid_updates = {k: v for k, v in updates.items() if k in allowed_fields} # Only update allowed fields
    if not valid_updates:
        logger.warning(f"No valid fields provided for updating lead status ID {status_id}")
        return get_lead_campaign_status_by_id(status_id, organization_id)

    set_parts = [f"{key} = %({key})s" for key in valid_updates.keys()]
    set_parts.append("updated_at = timezone('utc', now())")
    set_clause = ", ".join(set_parts)
    params = valid_updates.copy()
    params["status_id"] = status_id
    params["organization_id"] = organization_id
    sql = f"UPDATE lead_campaign_status SET {set_clause} WHERE id = %(status_id)s AND organization_id = %(organization_id)s RETURNING id"
    conn = None; success = False
    try:
        conn = get_connection();
        if not conn: return None
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                if cursor.fetchone(): success = True; logger.debug(f"Updated lead campaign status ID {status_id}")
                else: logger.warning(f"Lead campaign status ID {status_id} not found for Org {organization_id} during update or no change.");
        return get_lead_campaign_status_by_id(status_id, organization_id) if success else None
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating lead status ID {status_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return None # Fallback

def get_active_leads_due_for_step(organization_id: Optional[int] = None) -> List[Dict]:
    leads_due = []; conn = None
    sql = """
        SELECT lcs.*, c.name as campaign_name, l.email as lead_email, l.name as lead_name
        FROM lead_campaign_status lcs
        JOIN email_campaigns c ON lcs.campaign_id = c.id
        JOIN leads l ON lcs.lead_id = l.id
        WHERE lcs.status = 'active'
        AND (lcs.next_email_due_at <= timezone('utc', now()) OR lcs.next_email_due_at IS NULL) -- Due now or never set (for first step)
    """
    params = []
    if organization_id is not None:
        sql += " AND lcs.organization_id = %s"
        params.append(organization_id)
    sql += " ORDER BY lcs.organization_id, lcs.next_email_due_at ASC NULLS FIRST, lcs.created_at ASC" # Prioritize older enrollments if due time is same or null

    try:
        conn = get_connection();
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, tuple(params)); results = cursor.fetchall()
            if results: leads_due = [dict(row) for row in results]
            logger.debug(f"DB: Found {len(leads_due)} active leads due for step {f'for Org {organization_id}' if organization_id else ''}.")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting active leads due{f' for Org {organization_id}' if organization_id else ''}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return leads_due

def get_lead_campaign_status_by_id(status_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM lead_campaign_status WHERE id = %s AND organization_id = %s"
    conn = None; status_data = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (status_id, organization_id)); result = cursor.fetchone()
            if result: status_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting lead status ID {status_id} for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return status_data

def get_lead_campaign_status(lead_id: int, organization_id: int) -> Optional[Dict]:
    # Assuming a lead can only be in one campaign at a time due to UNIQUE (lead_id)
    sql = "SELECT * FROM lead_campaign_status WHERE lead_id = %s AND organization_id = %s"
    conn = None; status_data = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (lead_id, organization_id)); result = cursor.fetchone()
            if result: status_data = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting campaign status for lead {lead_id}, Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return status_data

# ==========================================
# ORGANIZATION EMAIL SETTINGS CRUD (Psycopg2)
# ==========================================
def save_org_email_settings(organization_id: int, settings_data: Dict[str, Any]) -> Optional[Dict]:
    encrypted_password = _encrypt_data(settings_data.get("smtp_password"))
    encrypted_api_key = _encrypt_data(settings_data.get("api_key"))
    encrypted_access_token = _encrypt_data(settings_data.get("access_token"))
    encrypted_refresh_token = _encrypt_data(settings_data.get("refresh_token"))
    columns = [ "organization_id", "provider_type", "smtp_host", "smtp_port", "smtp_username", "encrypted_smtp_password", "encrypted_api_key", "encrypted_access_token", "encrypted_refresh_token", "token_expiry", "verified_sender_email", "sender_name", "is_configured" ]
    params = {
        "organization_id": organization_id, "provider_type": settings_data.get("provider_type"), "smtp_host": settings_data.get("smtp_host"),
        "smtp_port": settings_data.get("smtp_port"), "smtp_username": settings_data.get("smtp_username"), "encrypted_smtp_password": encrypted_password,
        "encrypted_api_key": encrypted_api_key, "encrypted_access_token": encrypted_access_token, "encrypted_refresh_token": encrypted_refresh_token,
        "token_expiry": settings_data.get("token_expiry"), "verified_sender_email": settings_data.get("verified_sender_email"),
        "sender_name": settings_data.get("sender_name"), "is_configured": bool(settings_data.get("is_configured", False)),
        "updated_at": datetime.now(timezone.utc)
    }
    if not params["verified_sender_email"]: raise ValueError("Verified sender email is required.")
    if not params["provider_type"]: raise ValueError("Provider type is required.")
    if params["smtp_port"] is not None:
        try: params["smtp_port"] = int(params["smtp_port"])
        except (ValueError, TypeError): raise ValueError("SMTP port must be a valid integer.")

    insert_cols_list = columns + ["updated_at"]
    insert_cols_str = ", ".join(insert_cols_list)
    values_placeholders = ", ".join([f"%({col})s" for col in insert_cols_list])

    # For ON CONFLICT, exclude organization_id from SET, and ensure updated_at is also set
    update_cols = [f"{col} = EXCLUDED.{col}" for col in columns if col != 'organization_id']
    update_cols.append("updated_at = EXCLUDED.updated_at") # Use EXCLUDED.updated_at from values
    update_clause = ", ".join(update_cols)

    sql = f""" INSERT INTO organization_email_settings ({insert_cols_str}) VALUES ({values_placeholders}) ON CONFLICT (organization_id) DO UPDATE SET {update_clause} RETURNING id; """
    conn = None; saved_settings = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params); returned_id_row = cursor.fetchone()
                if returned_id_row and 'id' in returned_id_row: logger.info(f"Saved/Updated Email Settings for Org ID: {organization_id}")
                else: logger.warning(f"Email settings upsert for Org {organization_id} did not return ID.")
        saved_settings = get_org_email_settings_from_db(organization_id) # Fetch fresh after commit
    except ValueError as ve: logger.error(f"Validation Error saving email settings for Org {organization_id}: {ve}")
    except (Exception, psycopg2.Error) as e: logger.error(f"DB Error saving email settings for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_settings

def get_org_email_settings_from_db(organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM organization_email_settings WHERE organization_id = %s"
    conn = None; settings_data = None
    try:
        conn = get_connection();
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Changed to use conn.cursor within with conn
            cursor.execute(sql, (organization_id,)); result = cursor.fetchone()
            if result:
                settings_data = dict(result)
                settings_data["smtp_password"] = _decrypt_data(settings_data.pop("encrypted_smtp_password", None))
                settings_data["api_key"] = _decrypt_data(settings_data.pop("encrypted_api_key", None))
                settings_data["access_token"] = _decrypt_data(settings_data.pop("encrypted_access_token", None))
                settings_data["refresh_token"] = _decrypt_data(settings_data.pop("encrypted_refresh_token", None))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting email settings for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return settings_data

def get_leads_by_icp_match(organization_id: int, icp_id: int, limit: int = 1000) -> List[Dict]:
    """Fetches leads that are marked as matching a specific ICP and are 'matched = TRUE'."""
    # Added check for matched = TRUE to be explicit
    sql = """
        SELECT id, email, name, organization_id, icp_match_id /* add other fields you might need for logging/checks */
        FROM leads 
        WHERE organization_id = %s AND icp_match_id = %s AND matched = TRUE
        ORDER BY created_at DESC LIMIT %s;
    """
    conn = None; leads_list = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor: # Use RealDictCursor
            cursor.execute(sql, (organization_id, icp_id, limit))
            results = cursor.fetchall()
            for row in results:
                leads_list.append(dict(row)) # Ensure rows are dicts
    except (Exception, psycopg2.Error) as e: # Catch psycopg2.Error specifically
        logger.error(f"DB Error getting leads by ICP match for Org {organization_id}, ICP {icp_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return leads_list

# --- NEW/MODIFIED CRUD FUNCTIONS for reply handling ---

def log_sent_email(
    lead_campaign_status_id: int,
    organization_id: int,
    lead_id: int,
    campaign_id: int,
    campaign_step_id: int,
    message_id_header: str,
    to_email: str,
    subject: str
) -> Optional[Dict]:
    """Logs a sent email into the outgoing_email_log table."""
    sql = """
        INSERT INTO outgoing_email_log 
        (lead_campaign_status_id, organization_id, lead_id, campaign_id, campaign_step_id, 
         message_id_header, to_email, subject, sent_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, timezone('utc', now()))
        RETURNING id, message_id_header, sent_at; 
    """
    params = (
        lead_campaign_status_id, organization_id, lead_id, campaign_id, campaign_step_id,
        message_id_header, to_email, subject
    )
    conn = None; new_log_entry = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone()
                if result:
                    new_log_entry = dict(result)
                    logger.info(f"Logged sent email: LCS_ID {lead_campaign_status_id}, Message-ID: {message_id_header}")
                else:
                    logger.error(f"Failed to log sent email for LCS_ID {lead_campaign_status_id}, no ID returned.")
    except psycopg2.IntegrityError as ie:
        logger.error(f"DB Integrity Error logging sent email (likely duplicate Message-ID '{message_id_header}' for org {organization_id}): {ie}", exc_info=False) # Keep exc_info False if too noisy
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error logging sent email for LCS_ID {lead_campaign_status_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return new_log_entry

def store_email_reply(reply_data: Dict[str, Any]) -> Optional[Dict]:
    """Stores an incoming email reply and its AI classification."""
    required_fields = ["lead_campaign_status_id", "organization_id", "lead_id", "campaign_id", "received_at", "from_email"]
    if not all(field in reply_data and reply_data[field] is not None for field in required_fields): # Ensure values are not None
        logger.error(f"Missing or None values in required fields for storing email reply. Data: {reply_data}")
        return None

    sql = """
        INSERT INTO email_replies 
        (outgoing_email_log_id, lead_campaign_status_id, organization_id, lead_id, campaign_id, 
         received_at, from_email, reply_subject, raw_body_text, cleaned_reply_text,
         ai_classification, ai_summary, ai_extracted_entities, user_action_notes, is_actioned_by_user, created_at)
        VALUES (%(outgoing_email_log_id)s, %(lead_campaign_status_id)s, %(organization_id)s, %(lead_id)s, %(campaign_id)s,
                %(received_at)s, %(from_email)s, %(reply_subject)s, %(raw_body_text)s, %(cleaned_reply_text)s,
                %(ai_classification)s, %(ai_summary)s, %(ai_extracted_entities_json)s, %(user_action_notes)s, %(is_actioned_by_user)s, timezone('utc', now()))
        RETURNING id;
    """
    params = reply_data.copy() # Work on a copy
    # Ensure ai_extracted_entities is passed as a JSON string
    if isinstance(params.get("ai_extracted_entities"), dict):
        params["ai_extracted_entities_json"] = json.dumps(params["ai_extracted_entities"])
    elif params.get("ai_extracted_entities") is None: # Handle explicit None
         params["ai_extracted_entities_json"] = None
    else: # If it's already a string or other, pass as is or nullify if invalid
        params["ai_extracted_entities_json"] = str(params.get("ai_extracted_entities")) if params.get("ai_extracted_entities") else None


    # Set defaults for optional fields if not present in reply_data
    defaults = {
        "outgoing_email_log_id": None, "reply_subject": None, "raw_body_text": None,
        "cleaned_reply_text": None, "ai_classification": None, "ai_summary": None,
        "ai_extracted_entities_json": params.get("ai_extracted_entities_json"), # Use the processed one
        "user_action_notes": None, "is_actioned_by_user": False
    }
    final_params = {**defaults, **params} # Merge, params will overwrite defaults

    conn = None; new_reply_dict = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, final_params)
                result = cursor.fetchone()
                if result:
                    # Construct a more complete dict to return, useful for caller
                    new_reply_dict = {"id": result["id"], **final_params} 
                    # Remove json helper field if it was added
                    if "ai_extracted_entities_json" in new_reply_dict and "ai_extracted_entities" in new_reply_dict :
                        del new_reply_dict["ai_extracted_entities_json"]

                    logger.info(f"Stored email reply ID {result['id']} from {final_params.get('from_email')} for lead {final_params.get('lead_id')}")
                else:
                    logger.error(f"Failed to store email reply, no ID returned. From: {final_params.get('from_email')}, Lead: {final_params.get('lead_id')}")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error storing email reply: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return new_reply_dict


def get_outgoing_email_log_by_message_id(organization_id: int, message_id_header: str) -> Optional[Dict]:
    sql = "SELECT * FROM outgoing_email_log WHERE organization_id = %s AND message_id_header = %s;"
    conn = None; log_entry = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id, message_id_header))
            result = cursor.fetchone()
            if result: log_entry = dict(result)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error fetching outgoing log by Message-ID {message_id_header} for Org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return log_entry

def get_leads_with_positive_status_for_dashboard(organization_id: int, limit: int = 100) -> List[Dict]:
    actionable_statuses = ( # Use a tuple for IN operator
        'positive_reply_ai_flagged', 'question_ai_flagged',
        'appointment_manually_set', 'positive_reply_received',
        'manual_follow_up_needed'
    )
    sql = """
        SELECT 
            lcs.id as lead_campaign_status_id, lcs.lead_id, lcs.campaign_id, lcs.organization_id,
            lcs.status as lead_campaign_status, lcs.last_response_type, lcs.last_response_at,
            lcs.user_notes, lcs.updated_at as status_updated_at,
            l.name as lead_name, l.email as lead_email, l.company as lead_company,
            ec.name as campaign_name,
            er.id as latest_reply_id, 
            SUBSTRING(er.cleaned_reply_text FROM 1 FOR 150) as latest_reply_snippet, -- Get a snippet
            er.ai_summary as latest_reply_ai_summary,
            er.ai_classification as latest_reply_ai_classification,
            er.received_at as latest_reply_received_at
        FROM lead_campaign_status lcs
        JOIN leads l ON lcs.lead_id = l.id
        JOIN email_campaigns ec ON lcs.campaign_id = ec.id
        LEFT JOIN ( 
            SELECT DISTINCT ON (er_sub.lead_campaign_status_id) -- Get only the latest reply
                   er_sub.id, er_sub.lead_campaign_status_id,
                   er_sub.cleaned_reply_text, er_sub.ai_summary,
                   er_sub.ai_classification, er_sub.received_at
            FROM email_replies er_sub
            WHERE er_sub.organization_id = %s -- Filter subquery by org_id for efficiency
            ORDER BY er_sub.lead_campaign_status_id, er_sub.received_at DESC
        ) er ON lcs.id = er.lead_campaign_status_id
        WHERE lcs.organization_id = %s 
          AND lcs.status IN %s
        ORDER BY lcs.updated_at DESC
        LIMIT %s;
    """
    conn = None; results_list = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Pass organization_id twice: once for subquery, once for main query
            cursor.execute(sql, (organization_id, organization_id, actionable_statuses, limit))
            results = cursor.fetchall()
            if results: results_list = [dict(row) for row in results]
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB error fetching positive engagement for dashboard (Org {organization_id}): {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return results_list
    
def get_organizations_with_imap_enabled(limit: int = 1000) -> List[Dict]:
    """Fetches organization email settings where IMAP reply detection is enabled and configured."""
    sql = """
        SELECT 
            oes.organization_id, oes.provider_type,
            oes.imap_host, oes.imap_port, oes.imap_username, oes.encrypted_imap_password, oes.imap_use_ssl
            -- Add other fields from organization_email_settings if needed by _process_single_inbox
        FROM organization_email_settings oes
        WHERE oes.is_configured = TRUE AND oes.enable_reply_detection = TRUE 
          AND oes.imap_host IS NOT NULL AND oes.imap_username IS NOT NULL 
          -- AND (oes.encrypted_imap_password IS NOT NULL OR oes.imap_password IS NOT NULL) -- If you add plain imap_password
        LIMIT %s;
    """
    # Note: The above query assumes 'imap_host', 'imap_port', 'imap_username', 'encrypted_imap_password', 'imap_use_ssl', 'enable_reply_detection'
    # are columns in your 'organization_email_settings' table.
    # You need to add these columns in initialize_db() if they don't exist.

    conn = None; org_settings_list = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (limit,))
            results = cursor.fetchall()
            if results:
                org_settings_list = [dict(row) for row in results]
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error fetching organizations with IMAP enabled: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return org_settings_list

def update_organization_email_settings_field(organization_id: int, updates: Dict[str, Any]) -> bool:
    """Updates specific fields in the organization_email_settings table."""
    if not updates:
        logger.warning(f"No updates provided for organization_email_settings for org {organization_id}")
        return False
    
    # Only allow updating specific, safe fields like last_imap_poll_uid
    allowed_fields_to_update = {"last_imap_poll_uid", "last_imap_poll_timestamp"} # Add more if needed
    
    valid_updates = {k: v for k, v in updates.items() if k in allowed_fields_to_update}
    if not valid_updates:
        logger.warning(f"No valid fields to update in organization_email_settings for org {organization_id}. Updates: {updates}")
        return False

    set_parts = [f"{key} = %({key})s" for key in valid_updates.keys()]
    # Always update 'updated_at'
    valid_updates["updated_at"] = datetime.now(timezone.utc)
    set_parts.append("updated_at = %(updated_at)s")
    
    set_clause = ", ".join(set_parts)
    params_for_exec = valid_updates.copy()
    params_for_exec["organization_id"] = organization_id

    sql = f"UPDATE organization_email_settings SET {set_clause} WHERE organization_id = %(organization_id)s RETURNING id;"
    
    conn = None
    success = False
    try:
        conn = get_connection()
        if not conn: return False
        with conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, params_for_exec)
                if cursor.fetchone():
                    success = True
                    logger.info(f"Updated organization_email_settings for org {organization_id} with: {valid_updates}")
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating organization_email_settings for org {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return success

def get_leads_with_positive_status_for_dashboard(organization_id: int, limit: int = 100) -> List[Dict]:
    actionable_statuses = (
        'positive_reply_ai_flagged', 'question_ai_flagged',
        'appointment_manually_set', # Keep this for now, UI can filter or highlight
        'positive_reply_received',
        'manual_follow_up_needed'
    )
    sql = """
        SELECT 
            lcs.id as lead_campaign_status_id, lcs.lead_id, lcs.campaign_id, lcs.organization_id,
            lcs.status as lead_campaign_status, lcs.last_response_type, lcs.last_response_at,
            lcs.user_notes, lcs.updated_at as status_updated_at,
            l.name as lead_name, l.email as lead_email, l.company as lead_company,
            ec.name as campaign_name,
            er.id as latest_reply_id, 
            SUBSTRING(er.cleaned_reply_text FROM 1 FOR 250) as latest_reply_snippet, -- Increased snippet length
            er.ai_summary as latest_reply_ai_summary,
            er.ai_classification as latest_reply_ai_classification,
            er.received_at as latest_reply_received_at -- Make sure this is selected
        FROM lead_campaign_status lcs
        JOIN leads l ON lcs.lead_id = l.id
        JOIN email_campaigns ec ON lcs.campaign_id = ec.id
        LEFT JOIN ( 
            SELECT DISTINCT ON (er_sub.lead_campaign_status_id)
                   er_sub.id, er_sub.lead_campaign_status_id,
                   er_sub.cleaned_reply_text, er_sub.ai_summary,
                   er_sub.ai_classification, er_sub.received_at -- Ensure received_at is here
            FROM email_replies er_sub
            WHERE er_sub.organization_id = %s 
            ORDER BY er_sub.lead_campaign_status_id, er_sub.received_at DESC
        ) er ON lcs.id = er.lead_campaign_status_id
        WHERE lcs.organization_id = %s 
          AND lcs.status IN %s
          -- AND er.is_actioned_by_user = FALSE -- Add this if you only want unactioned items
        ORDER BY lcs.updated_at DESC
        LIMIT %s;
    """
    # ... (rest of the function: connection, execution, error handling) ...
    conn = None; results_list = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Pass organization_id twice: once for subquery, once for main query
            cursor.execute(sql, (organization_id, organization_id, actionable_statuses, limit))
            results = cursor.fetchall()
            if results: results_list = [dict(row) for row in results]
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB error fetching positive engagement for dashboard (Org {organization_id}): {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return results_list

def count_appointments_set(db: Session, organization_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
    """Counts leads marked with appointment_confirmed = True for the organization."""
    base_query = db.query(func.count(Lead.id)).filter(
    Lead.organization_id == organization_id,
    Lead.appointment_confirmed == True
)
    if start_date:
        base_query = base_query.filter(Lead.updated_at >= start_date)
    if end_date:
        base_query = base_query.filter(Lead.updated_at <= end_date)
    count = base_query.scalar()
    return count if count else 0

def count_positive_replies_status(db: Session, organization_id: int, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None) -> int:
    """Counts leads flagged with a positive reply status."""
    # Define the relevant positive statuses
    positive_statuses = [
        LeadStatusEnum.positive_reply_ai_flagged,
        LeadStatusEnum.positive_reply_received, # Add any other relevant status
        # Important: Should we include 'appointment_manually_set' here?
        # If yes, it means "positive reply OR appointment set".
        # If no, it strictly means "positive reply received but maybe not yet converted".
        # Let's assume *not* including appointment_manually_set for a clearer conversion rate.
        # LeadStatusEnum.appointment_manually_set
    ]

    query = db.query(func.count(LeadCampaignStatus.id)).join(Lead).filter(
        Lead.organization_id == organization_id,
        LeadCampaignStatus.status.in_(positive_statuses)
    )
    # Add date filtering (e.g., based on LeadCampaignStatus.last_response_at or updated_at)
    if start_date:
        query = query.filter(LeadCampaignStatus.last_response_at >= start_date) # Adjust field if necessary
    if end_date:
        query = query.filter(LeadCampaignStatus.last_response_at <= end_date) # Adjust field if necessary

    count = query.scalar()
    return count if count else 0

# --- Potentially needed later, but implement the basics first ---

def get_recent_appointments_list(db: Session, organization_id: int, limit: int = 5) -> List[Dict]:
    """Fetches the most recent leads marked with an appointment."""
    results = db.query(
        Lead.first_name,
        Lead.last_name,
        Lead.company_name,
        EmailCampaign.name.label("campaign_name"),
        LeadCampaignStatus.last_response_at.label("action_date") # Or Lead.updated_at
    ).join(LeadCampaignStatus, Lead.id == LeadCampaignStatus.lead_id)\
     .join(EmailCampaign, LeadCampaignStatus.campaign_id == EmailCampaign.id)\
     .filter(
         Lead.organization_id == organization_id,
         Lead.appointment_confirmed == True # Or use LeadCampaignStatus.status == LeadStatusEnum.appointment_manually_set
     )\
     .order_by(LeadCampaignStatus.last_response_at.desc()) # Or Lead.updated_at.desc()
     .limit(limit)\
     .all()

    # Convert results to list of dicts for easier JSON serialization
    appointments = [
        {
            "lead_name": f"{r.first_name or ''} {r.last_name or ''}".strip(),
            "company_name": r.company_name,
            "campaign_name": r.campaign_name,
            "date_marked": r.action_date.strftime('%Y-%m-%d %H:%M') if r.action_date else 'N/A'
        } for r in results
    ]
    return appointments



# ==========================================
# Run initialization if script is executed directly
# ==========================================
if __name__ == "__main__":
    logger.info("Running database.py directly, attempting initialization...")
    if settings and settings.DATABASE_URL and not settings.DATABASE_URL == "ENV_VAR_DATABASE_URL_NOT_SET":
        initialize_db()
        # Example usage (optional, for testing)
        # test_org = create_organization("Test AI Corp")
        # if test_org:
        #     logger.info(f"Test org: {test_org}")
        #     test_offering = create_offering(test_org['id'], {"name": "AI Product X", "description": "Solves all problems"})
        #     if test_offering:
        #         logger.info(f"Test offering: {test_offering}")
        #         test_campaign = create_campaign(test_org['id'], "AI Test Campaign", offering_id=test_offering['id'])
        #         if test_campaign:
        #             logger.info(f"Test campaign created: {test_campaign}")
        #             create_campaign_step(test_campaign['id'], test_org['id'], 1, 2, "Subject 1", "Body 1", follow_up_angle="Intro")
        #             create_campaign_step(test_campaign['id'], test_org['id'], 2, 3, "Subject 2", "Body 2", follow_up_angle="Value Prop")
        #             steps = get_steps_for_campaign(test_campaign['id'], test_org['id'])
        #             logger.info(f"Campaign steps: {steps}")

        logger.info("Direct execution initialization attempt finished.")
    else:
        logger.error("Cannot initialize database directly because settings (DATABASE_URL) are not configured or invalid.")
