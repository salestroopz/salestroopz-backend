# app/db/database.py

import psycopg2 # Use PostgreSQL driver
from psycopg2.extras import RealDictCursor # Get dict results
from urllib.parse import urlparse # For parsing DATABASE_URL
# from pathlib import Path # Seems unused
from typing import Optional, List, Dict, Any
import json
from datetime import datetime, timezone # Use timezone for UTC

# Import logger
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    # Basic config if logger not found externally
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(name)s | %(message)s')

# Import Settings
try:
    from app.utils.config import settings
    logger.info("Successfully imported settings in database.py")
    if not settings or not getattr(settings, 'DATABASE_URL', None) or not settings.DATABASE_URL or settings.DATABASE_URL == "ENV_VAR_DATABASE_URL_NOT_SET":
        logger.critical("DATABASE_URL is not configured in settings or is invalid.")
        settings = None # Mark settings as invalid for DB operations
    elif not settings.DATABASE_URL.startswith("postgresql://") and not settings.DATABASE_URL.startswith("postgres://"):
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
        # Logged critically above, just raise here
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

        # Build connection string suitable for psycopg2.connect()
        # Using keywords is often clearer than DSN string
        conn = psycopg2.connect(
            dbname=db_name,
            user=username,
            password=password,
            host=hostname,
            port=port
            # Add sslmode='require' here if needed for external connections,
            # usually not needed for Render internal connections
        )
        # logger.debug(f"Connecting to PostgreSQL DB: {db_name} on {hostname}:{port}") # Debug level
        # logger.debug("PostgreSQL connection successful.") # Debug level
        return conn
    except ValueError as ve:
        logger.error(f"Error parsing DATABASE_URL '{settings.DATABASE_URL[:50]}...': {ve}", exc_info=True)
        raise ValueError(f"Invalid DATABASE_URL format: {ve}") from ve
    except psycopg2.OperationalError as e:
        logger.error(f"DATABASE CONNECTION ERROR: Failed to connect to PostgreSQL - {e}", exc_info=True)
        # Do not raise ConnectionError here if initialize_db needs to proceed gently
        return None # Return None to indicate connection failure
    except Exception as e:
         logger.error(f"Unexpected error getting PostgreSQL connection: {e}", exc_info=True)
         return None # Return None for unexpected errors too


# --- Database Initialization (PostgreSQL Syntax) ---
def initialize_db():
    """Creates/updates tables and indexes for PostgreSQL if they don't exist."""
    logger.info("Initializing PostgreSQL database schema...")
    conn = None
    # Using SERIAL PRIMARY KEY, TIMESTAMPTZ, JSONB, BOOLEAN
    # Ensure table names and column names match your Pydantic models / application logic
    tables = {
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
        if not conn:
            logger.error("DATABASE ERROR during initialization: Could not establish connection.")
            return # Stop initialization if connection failed

        with conn: # Use connection as context manager (auto commit/rollback)
            with conn.cursor() as cursor: # Use cursor context manager
                logger.info("Executing CREATE TABLE IF NOT EXISTS statements for PostgreSQL...")
                for table_name, sql_create in tables.items():
                    cursor.execute(sql_create)
                    logger.debug(f" -> {table_name.capitalize()} table checked/created.")

                logger.info("Executing CREATE INDEX IF NOT EXISTS statements for PostgreSQL...")
                for table_name, index_sqls in indexes.items():
                     for sql_index in index_sqls:
                         cursor.execute(sql_index)
                     logger.debug(f" -> {table_name.capitalize()} indexes checked/created.")
        logger.info("Database initialization sequence complete.")
    except (Exception, psycopg2.DatabaseError) as error:
        logger.error(f"DATABASE ERROR during initialization: {error}", exc_info=True)
        # Error handling within context manager should have rolled back if needed
    finally:
         # Close connection if obtained and not already closed
         if conn and not getattr(conn, 'closed', True): # Check 'closed' attribute safely
            conn.close()
            # logger.debug("DB connection closed after initialization attempt.") # Debug level

# ==========================================
# PLACEHOLDER ENCRYPTION FUNCTIONS - WARNING!
# ==========================================
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    """Placeholder: Encrypts data. REPLACE WITH REAL IMPLEMENTATION using cryptography library."""
    if plain_text is None: return None
    # **WARNING: Storing sensitive data unencrypted in production is a major security risk!**
    logger.warning("ENCRYPTION NOT IMPLEMENTED! Sensitive data is NOT being encrypted.")
    # Example using cryptography library would go here. For now, returning plain text.
    return plain_text # This is insecure!

def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    """Placeholder: Decrypts data. REPLACE WITH REAL IMPLEMENTATION using cryptography library."""
    if encrypted_text is None: return None
    # **WARNING: Retrieving unencrypted sensitive data!**
    # logger.warning("DECRYPTION NOT IMPLEMENTED!") # Redundant if encryption doesn't happen
    # Example using cryptography library would go here. For now, returning as is.
    return encrypted_text # Assumes data wasn't actually encrypted

# ==========================================
# HELPER to handle JSON parsing (needed for ICP/Offering reads)
# ==========================================
def _parse_json_fields(data_row: Optional[Dict], json_fields: List[str], default_value: Any = None) -> Optional[Dict]:
    """Helper to safely parse JSONB fields (which might be pre-parsed) from a dictionary row."""
    if not data_row: return None
    for field in json_fields:
        field_value = data_row.get(field)
        parsed_value = default_value

        # Check if psycopg2/driver already parsed JSONB to dict/list
        if isinstance(field_value, (dict, list)):
            parsed_value = field_value
        # If it's a string, try parsing it
        elif field_value and isinstance(field_value, str):
            try:
                parsed_value = json.loads(field_value)
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON string for field '{field}' in row ID {data_row.get('id')}")
                # Keep default_value
        # Handle cases where field is present but None
        elif field in data_row and field_value is None:
             parsed_value = default_value

        data_row[field] = parsed_value # Store parsed value or default
    return data_row

# ==========================================
# ORGANIZATION CRUD OPERATIONS (Psycopg2)
# ==========================================
def create_organization(name: str) -> Optional[Dict]:
    """Creates an organization or returns existing one by name."""
    sql = "INSERT INTO organizations (name) VALUES (%s) RETURNING id;"
    conn = None; org_data = None
    try:
        conn = get_connection()
        if not conn: return None # Stop if connection failed
        with conn: # Auto commit/rollback
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                try:
                    cursor.execute(sql, (name,)); new_id_row = cursor.fetchone()
                    if new_id_row and 'id' in new_id_row:
                        org_id = new_id_row['id']
                        logger.info(f"Created org '{name}' ID: {org_id}")
                        # Fetch full data after successful insert and commit
                        # Close cursor before calling another function using the same connection implicitly
                        # The 'with cursor' block handles cursor closing
                    else: # Should not happen with RETURNING if insert succeeded
                         logger.error(f"Org creation for '{name}' did not return ID.")
                         return None # Indicate failure

                except psycopg2.IntegrityError:
                    # Name likely exists, fetch the existing one
                    logger.warning(f"Org name '{name}' already exists. Fetching existing.")
                    conn.rollback() # Rollback the failed insert attempt explicitly if needed
                    # Need to call get_organization_by_name here, ensure cursor is closed first or use new one
                    # For simplicity now, just return None or indicate existing without fetching again immediately
                    # Requires get_organization_by_name to be implemented
                    return get_organization_by_name(name) # Assumes this function exists and uses its own cursor

        # If insert was successful, fetch the created org outside the transaction block
        # Note: org_id scope might be an issue if exception occurred before assignment
        if 'org_id' in locals() and org_id:
             org_data = get_organization_by_id(org_id) # Fetch after commit

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating/getting org '{name}': {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return org_data

def get_organization_by_id(organization_id: int) -> Optional[Dict]:
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
    """Fetches organization by name."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'get_organization_by_name' is not implemented.")
    return None

def get_all_organizations() -> List[Dict]:
    """Fetches all organizations."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'get_all_organizations' is not implemented.")
    return []

# ==========================================
# USER CRUD OPERATIONS (Psycopg2)
# ==========================================
def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (%s, %s, %s) RETURNING id;"
    conn = None; user_data = None; user_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
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
                    conn.rollback() # Explicit rollback on integrity error
                    logger.warning(f"DB Integrity error creating user '{email}' (email exists or bad org_id?): {e}")
                    # If email exists, return the existing user
                    return get_user_by_email(email) # Assumes get_user_by_email exists

        # Fetch created user outside transaction block if insert was successful
        if user_id:
            user_data = get_user_by_id(user_id) # Fetch the user data including org name

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

# --- ADDED FUNCTION ---
def get_user_by_email(email: str) -> Optional[Dict]:
    """Fetches user data and organization name by email."""
    sql = """
        SELECT
            u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.email = %s;
        """
    conn = None
    user_data = None
    try:
        conn = get_connection() # Assuming get_connection() function exists
        if not conn: return None # Check if connection failed

        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (email,)) # Pass email as parameter
            result = cursor.fetchone()
            if result:
                user_data = dict(result)
            # else: logger.debug(f"User not found for email: {email}") # Optional: log if not found

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting user by email {email}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True):
            conn.close()
            # logger.debug(f"DB connection closed for email {email}") # Optional debug log
    return user_data # Return the dictionary or None
# --- END ADDED FUNCTION ---

def get_users_by_organization(organization_id: int) -> List[Dict]:
    """Fetches all users for a given organization."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'get_users_by_organization' is not implemented.")
    return []


# ==========================================
# LEAD CRUD OPERATIONS (Psycopg2) - NEEDS REVIEW for logic consistency
# ==========================================
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
    """Creates or updates a lead based on organization_id and email."""
    # Define columns expected in the 'leads' table
    columns = [ "organization_id", "name", "email", "company", "title", "source", "linkedin_profile", "company_size", "industry", "location", "matched", "reason", "crm_status", "appointment_confirmed" ]
    # Prepare parameters dictionary, ensuring organization_id is set
    params = {col: lead_data.get(col) for col in columns}
    params['organization_id'] = organization_id

    # Basic validation
    if not params.get('email'):
        logger.warning(f"Skipping lead save for org {organization_id}: missing email")
        return None

    # Ensure boolean/integer types are correct
    params['matched'] = bool(params.get('matched', False)) # Use boolean
    params['appointment_confirmed'] = bool(params.get('appointment_confirmed', False)) # Use boolean

    # Prepare for SQL query
    insert_cols_str = ", ".join(columns)
    values_placeholders = ", ".join([f"%({col})s" for col in columns])
    # Exclude unique key columns and created_at from update clause
    update_cols = [f"{col} = EXCLUDED.{col}" for col in columns if col not in ['id', 'organization_id', 'email', 'created_at']]
    update_clause = ", ".join(update_cols)

    # Use ON CONFLICT for PostgreSQL UPSERT
    sql = f"""
        INSERT INTO leads ({insert_cols_str})
        VALUES ({values_placeholders})
        ON CONFLICT (organization_id, email) DO UPDATE SET {update_clause}
        RETURNING id;
    """ # Using RETURNING to get the ID of the inserted or updated row

    conn = None; saved_lead = None; returned_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                returned_id_row = cursor.fetchone()
                if returned_id_row and 'id' in returned_id_row:
                    returned_id = returned_id_row['id']
                else:
                     logger.warning(f"Lead upsert did not return ID for {params['email']}, Org {organization_id}.")

        # Fetch full data after commit using the returned ID
        if returned_id:
            saved_lead = get_lead_by_id(returned_id, organization_id) # Assumes get_lead_by_id exists
            if saved_lead:
                 logger.debug(f"Saved/Updated lead ID {saved_lead['id']} for org {organization_id}")
            else: # Should not happen if RETURNING ID worked
                 logger.error(f"Failed to fetch lead ID {returned_id} immediately after upsert.")
        else: # Fallback if RETURNING failed (unlikely but possible)
            logger.warning(f"Upsert didn't return ID, attempting fetch by email for {params['email']}, Org {organization_id}.")
            saved_lead = get_lead_by_email(params['email'], organization_id) # Assumes get_lead_by_email exists

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error saving lead for org {organization_id}, email {params.get('email')}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_lead

def get_lead_by_id(lead_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a lead by its ID and organization ID."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'get_lead_by_id' is not implemented.")
    return None

def get_lead_by_email(email: str, organization_id: int) -> Optional[Dict]:
    """Fetches a lead by its email and organization ID."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'get_lead_by_email' is not implemented.")
    return None

def get_leads_by_organization(organization_id: int, offset: int = 0, limit: int = 100) -> List[Dict]:
    """Fetches leads for an organization with pagination."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'get_leads_by_organization' is not implemented.")
    return []

def update_lead_partial(lead_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates specific fields for a lead."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'update_lead_partial' is not implemented.")
    return None

def delete_lead(lead_id: int, organization_id: int) -> bool:
    """Deletes a lead."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'delete_lead' is not implemented.")
    return False

# ==========================================
# ICP CRUD OPERATIONS (Psycopg2)
# ==========================================
def create_or_update_icp(organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    """Creates or updates the ICP definition for an organization."""
    conn = None; saved_icp = None; returned_id = None
    # Ensure keys exist and handle JSON serialization
    params = {
        "organization_id": organization_id,
        "name": icp_definition.get("name", f"Default ICP"), # Provide a default name if missing
        "title_keywords": json.dumps(icp_definition.get("title_keywords") or []),
        "industry_keywords": json.dumps(icp_definition.get("industry_keywords") or []),
        "company_size_rules": json.dumps(icp_definition.get("company_size_rules") or {}), # Default to empty dict
        "location_keywords": json.dumps(icp_definition.get("location_keywords") or []),
        "updated_at": datetime.now(timezone.utc) # Use keyword for named parameter
    }
    # Columns for INSERT part
    insert_columns = ["organization_id", "name", "title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    values_placeholders = ", ".join([f"%({col})s" for col in insert_columns])
    # Columns for UPDATE part (exclude the unique key)
    update_cols = [f"{col} = EXCLUDED.{col}" for col in insert_columns if col != 'organization_id']
    update_cols.append("updated_at = %(updated_at)s") # Add updated_at timestamp
    update_clause = ", ".join(update_cols)

    # Use ON CONFLICT for PostgreSQL UPSERT
    sql = f"""
        INSERT INTO icps ({", ".join(insert_columns)})
        VALUES ({values_placeholders})
        ON CONFLICT(organization_id) DO UPDATE SET {update_clause}
        RETURNING id;
    """
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params) # Pass the full params dict
                returned_id_row = cursor.fetchone()
                if returned_id_row and 'id' in returned_id_row:
                     returned_id = returned_id_row['id']
                     logger.info(f"Saved/Updated ICP for Org ID: {organization_id}. Returned ID: {returned_id}")
                else:
                     logger.warning(f"ICP upsert for Org ID {organization_id} did not return ID.")


        # Fetch the saved/updated ICP outside transaction block
        if returned_id:
            saved_icp = get_icp_by_organization_id(organization_id) # Fetch by org ID as it's unique
        else: # Fallback if needed
            logger.warning(f"Upsert didn't return ID, attempting fetch by org ID for Org {organization_id}.")
            saved_icp = get_icp_by_organization_id(organization_id)

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error saving ICP for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_icp

def get_icp_by_organization_id(organization_id: int) -> Optional[Dict]:
    """Fetches the ICP definition for an organization, parsing JSON fields."""
    sql = "SELECT * FROM icps WHERE organization_id = %s;"
    conn = None; icp_data = None
    json_fields_to_parse = ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, (organization_id,))
            result = cursor.fetchone()
            if result:
                # Parse JSON fields after fetching
                icp_data = _parse_json_fields(dict(result), json_fields_to_parse, default_value=None)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting ICP for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return icp_data

def delete_icp(organization_id: int) -> bool:
    """Deletes the ICP definition for an organization."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'delete_icp' is not implemented.")
    return False

# ==========================================
# OFFERING CRUD OPERATIONS (Psycopg2)
# ==========================================
def _parse_offering_json_fields(offering_row: Dict) -> Optional[Dict]: # Input is already dict
    """Helper to parse JSON fields from an Offering dictionary row."""
    if not offering_row: return None
    json_fields = ["key_features", "target_pain_points"]
    # Ensure target fields are parsed into lists, default to empty list
    for field in json_fields:
        field_value = offering_row.get(field)
        parsed_value = [] # Default to list
        # Check if psycopg2/driver already parsed JSONB to dict/list
        if isinstance(field_value, list):
            parsed_value = field_value
        elif isinstance(field_value, dict): # If it parsed to dict, maybe wrap in list or log warning
             logger.warning(f"Offering field '{field}' ID {offering_row.get('id')} was dict, expected list. Using empty list.")
             parsed_value = [] # Or handle dict case if appropriate
        # If it's a string, try parsing it
        elif isinstance(field_value, str):
            try:
                parsed = json.loads(field_value)
                # Ensure the result is a list
                parsed_value = parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                logger.warning(f"Could not parse JSON for Offering field '{field}' ID {offering_row.get('id')}")
        offering_row[field] = parsed_value
    return offering_row

def create_offering(organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    """Creates a new offering for an organization."""
    # Define columns and prepare parameters, ensuring JSON fields are dumped
    columns = ["organization_id", "name", "description", "key_features", "target_pain_points", "call_to_action", "is_active"]
    params = {
        "organization_id": organization_id,
        "name": offering_data.get("name"),
        "description": offering_data.get("description"),
        "key_features": json.dumps(offering_data.get("key_features") or []), # Default to empty list JSON
        "target_pain_points": json.dumps(offering_data.get("target_pain_points") or []), # Default to empty list JSON
        "call_to_action": offering_data.get("call_to_action"),
        "is_active": bool(offering_data.get("is_active", True)) # Ensure boolean
    }
    sql = f"INSERT INTO offerings ({', '.join(columns)}) VALUES ({', '.join([f'%({col})s' for col in columns])}) RETURNING id;"

    conn = None; saved_offering = None; offering_id = None
    try:
        if not params.get("name"): raise ValueError("Offering name cannot be empty")
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, params)
                new_id_row = cursor.fetchone()
                if new_id_row and 'id' in new_id_row:
                     offering_id = new_id_row['id']
                     logger.info(f"Created offering '{params['name']}' (ID: {offering_id}) for Org ID {organization_id}")
                else:
                     logger.error(f"Offering creation for '{params['name']}' did not return ID.")
                     return None

        # Fetch the created offering outside transaction block
        if offering_id:
             saved_offering = get_offering_by_id(offering_id, organization_id) # Assumes exists

    except ValueError as ve:
         logger.error(f"Validation error creating offering for Org ID {organization_id}: {ve}")
    except (Exception, psycopg2.Error) as e:
         logger.error(f"DB Error creating offering for Org ID {organization_id}: {e}", exc_info=True)
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return saved_offering

def get_offering_by_id(offering_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches an offering by its ID and organization ID, parsing JSON."""
    sql = "SELECT * FROM offerings WHERE id = %s AND organization_id = %s;"
    conn = None; offering_data = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
             cursor.execute(sql, (offering_id, organization_id))
             result = cursor.fetchone()
             if result: offering_data = _parse_offering_json_fields(dict(result))
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting offering ID {offering_id} for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return offering_data

def get_offerings_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    """Fetches offerings for an organization, parsing JSON."""
    sql = "SELECT * FROM offerings WHERE organization_id = %s"
    params = [organization_id]
    if active_only:
        sql += " AND is_active = TRUE"
    sql += " ORDER BY name;"
    conn = None; offerings = []
    try:
        conn = get_connection()
        if not conn: return []
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(sql, params)
            results = cursor.fetchall()
            for row in results:
                parsed_row = _parse_offering_json_fields(dict(row))
                if parsed_row: offerings.append(parsed_row)
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error getting offerings for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return offerings

def update_offering(offering_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates an existing offering."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'update_offering' is not implemented.")
    return get_offering_by_id(offering_id, organization_id) # Return current state as placeholder

def delete_offering(offering_id: int, organization_id: int) -> bool:
    """Deletes an offering."""
    # --- IMPLEMENTATION NEEDED ---
    logger.warning("Function 'delete_offering' is not implemented.")
    return False

# ===========================================================
# CAMPAIGN/STEP/STATUS CRUD (Corrected for PostgreSQL)
# ===========================================================

# --- Campaign CRUD ---
def create_campaign(organization_id: int, name: str, description: Optional[str] = None, is_active: bool = True) -> Optional[Dict]:
    sql = "INSERT INTO email_campaigns (organization_id, name, description, is_active) VALUES (%s, %s, %s, %s) RETURNING id"
    params = (organization_id, name, description, is_active)
    conn = None; campaign_data = None; new_id = None
    try:
        conn = get_connection()
        if not conn: return None
        with conn: # Auto commit/rollback
            with conn.cursor() as cursor: # Use default cursor for single return value
                cursor.execute(sql, params)
                result = cursor.fetchone()
                if result: new_id = result[0]
        if new_id:
            logger.info(f"Created campaign '{name}' (ID: {new_id}) for Org {organization_id}")
            campaign_data = get_campaign_by_id(new_id, organization_id) # Fetch full data
        else:
             logger.error(f"Campaign creation for '{name}' did not return ID.")

    except psycopg2.IntegrityError as ie:
         logger.warning(f"DB Integrity Error creating campaign '{name}' for Org {organization_id}: {ie}")
         # Potentially handle duplicate name error if name should be unique per org
    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error creating campaign for Org {organization_id}: {e}")
        # Rollback happened automatically due to 'with conn:' on error
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return campaign_data

def get_campaign_by_id(campaign_id: int, organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM email_campaigns WHERE id = %s AND organization_id = %s"
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
    sql = "SELECT * FROM email_campaigns WHERE organization_id = %s"
    params = [organization_id]
    if active_only:
        sql += " AND is_active = TRUE"
    sql += " ORDER BY name"
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

# --- Step CRUD ---
def create_campaign_step(campaign_id: int, organization_id: int, step_number: int, delay_days: int, subject: Optional[str], body: Optional[str], is_ai: bool = False, follow_up_angle: Optional[str] = None) -> Optional[Dict]:
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
        logger.error(f"DB Error creating step {step_number} for Camp {campaign_id}: {e}")
        # Rollback happens automatically due to 'with conn:' if exception bubbles up
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step_data

def get_campaign_step_by_id(step_id: int, organization_id: int) -> Optional[Dict]:
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
        logger.error(f"DB Error getting step ID {step_id} for Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step

def get_steps_for_campaign(campaign_id: int, organization_id: int) -> List[Dict]:
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
        logger.error(f"DB Error getting steps for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return steps

def get_next_campaign_step(campaign_id: int, organization_id: int, current_step_number: int) -> Optional[Dict]:
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
        logger.error(f"DB Error getting next step ({next_step_number}) for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return step_data


# --- Lead Status CRUD ---
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
                    return None # Return None if already enrolled or other integrity issue

        if status_id:
            logger.info(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {status_id})")
            status_data = get_lead_campaign_status_by_id(status_id, organization_id) # Fetch full data
        else:
            logger.error(f"Lead enrollment for lead {lead_id}, camp {campaign_id} did not return ID.")

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}")
        # Rollback happened automatically if exception bubbled up from 'with conn:'
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()
    return status_data

def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates the status record for a lead in a campaign."""
    allowed_fields = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message"}
    valid_updates = {k: v for k, v in updates.items() if k in allowed_fields}

    # Ensure timestamps are timezone-aware if needed by DB/logic
    # Example: Convert naive datetime to UTC before saving
    # if 'last_email_sent_at' in valid_updates and isinstance(valid_updates['last_email_sent_at'], datetime) and valid_updates['last_email_sent_at'].tzinfo is None:
    #     valid_updates['last_email_sent_at'] = valid_updates['last_email_sent_at'].replace(tzinfo=timezone.utc)
    # Similarly for other timestamp fields...

    if not valid_updates:
        # Maybe just fetch and return current status if no valid fields provided?
        # return get_lead_campaign_status_by_id(status_id, organization_id)
         logger.warning(f"No valid fields provided for updating lead status ID {status_id}")
         return None


    # Use named placeholders %(key)s for psycopg2 dictionary execution
    set_parts = [f"{key} = %({key})s" for key in valid_updates.keys()]
    set_parts.append("updated_at = timezone('utc', now())") # Use PostgreSQL function for current UTC time
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
                    logger.warning(f"Lead campaign status ID {status_id} not found or no change needed for Org {organization_id}")
                    success = False # Explicitly mark as not updated if rowcount is 0

    except (Exception, psycopg2.Error) as e:
        logger.error(f"DB Error updating lead status ID {status_id}: {e}", exc_info=True)
        success = False # Mark as failed on error
    finally:
        if conn and not getattr(conn, 'closed', True): conn.close()

    # Fetch and return updated status only if update was successful
    return get_lead_campaign_status_by_id(status_id, organization_id) if success else None


def get_active_leads_due_for_step(organization_id: Optional[int] = None) -> List[Dict]:
    """Fetches active leads potentially due for the next step. Filtering refined later."""
    logger.debug(f"Fetching active leads {f'for Org {organization_id}' if organization_id else 'across all orgs'}.")
    leads_due = []; conn = None
    # Selecting relevant fields for processing
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
    # Ordering might be useful for processing, e.g., by due date or last sent
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
        logger.error(f"DB Error getting lead status ID {status_id} for Org {organization_id}: {e}")
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
        logger.error(f"DB Error getting campaign status for lead {lead_id}, Org {organization_id}: {e}")
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

# ==========================================
# Run initialization if script is executed directly (optional)
# ==========================================
if __name__ == "__main__":
    logger.info("Running database.py directly, attempting initialization...")
    # Check if settings are valid before trying to initialize
    if settings:
        initialize_db()
        logger.info("Direct execution initialization attempt finished.")
    else:
        logger.error("Cannot initialize database directly because settings (DATABASE_URL) are not configured.")
