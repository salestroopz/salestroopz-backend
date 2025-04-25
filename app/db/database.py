# app/db/database.py

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
import json
from datetime import datetime # Import datetime for timestamp comparisons later

# --- Import Settings ---
try:
    from app.utils.config import settings
    print("Successfully imported settings in database.py")
except ImportError:
    print("Warning: Could not import settings from app.utils.config. Using default DB path.")
    settings = None

# --- Determine Database Path ---
if settings and settings.DATABASE_URL.startswith("sqlite"):
    db_url_path_part = settings.DATABASE_URL.split("///")[-1]
    DB_PATH = Path(db_url_path_part).resolve()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Using SQLite database path from settings: {DB_PATH}")
elif settings:
    print(f"Warning: Non-SQLite DATABASE_URL ({settings.DATABASE_URL}). Connection logic assumes SQLite.")
    DB_PATH = None
else:
    DB_PATH = Path(__file__).parent / "salestroopz_fallback.db"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Using fallback SQLite database path: {DB_PATH}")


# --- Database Connection Function ---
def get_connection():
    """Establishes and returns a connection to the SQLite database."""
    if not DB_PATH:
         raise ValueError("Database path is not configured correctly for SQLite.")
    # Enable FOREIGN KEY constraint enforcement for SQLite
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# --- Database Initialization (ALL Tables) ---
def initialize_db():
    """Creates/updates tables: organizations, users, leads, icps, offerings, email_campaigns, campaign_steps, lead_campaign_status."""
    # **IMPORTANT**: Running this after schema change might require deleting the old DB file.
    print("Initializing database schema...")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 1. Organizations Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print(" -> Organizations table checked/created.")

        # 2. Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            hashed_password TEXT NOT NULL,
            organization_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON users (email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_organization ON users (organization_id)")
        print(" -> Users table checked/created.")

        # 3. Leads Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            name TEXT, email TEXT NOT NULL COLLATE NOCASE, company TEXT, title TEXT, source TEXT,
            linkedin_profile TEXT, company_size TEXT, industry TEXT, location TEXT,
            matched INTEGER DEFAULT 0, reason TEXT, crm_status TEXT DEFAULT 'pending',
            appointment_confirmed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (organization_id, email),
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email)")
        print(" -> Leads table checked/created/modified.")

        # 4. ICPs Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS icps (
            id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL UNIQUE,
            name TEXT DEFAULT 'Default ICP', title_keywords TEXT, industry_keywords TEXT,
            company_size_rules TEXT, location_keywords TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_icp_organization ON icps (organization_id)")
        print(" -> ICPs table checked/created.")

        # 5. Offerings Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS offerings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, organization_id INTEGER NOT NULL, name TEXT NOT NULL,
            description TEXT, key_features TEXT, target_pain_points TEXT, call_to_action TEXT,
            is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_offering_organization ON offerings (organization_id)")
        print(" -> Offerings table checked/created.")

        # --- 6. NEW: Email Campaigns Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_campaigns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            name TEXT NOT NULL,             -- e.g., "Default Outreach Q2", "Feature X Launch"
            description TEXT,
            is_active INTEGER DEFAULT 1,    -- Campaign is usable (1) or archived (0)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaign_organization ON email_campaigns (organization_id)")
        print(" -> Email Campaigns table checked/created.")

        # --- 7. NEW: Campaign Steps Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS campaign_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id INTEGER NOT NULL,
            organization_id INTEGER NOT NULL,      -- Denormalized for easier filtering
            step_number INTEGER NOT NULL,         -- Order of the email (1, 2, 3...)
            delay_days INTEGER DEFAULT 1,         -- Days after previous step/enrollment
            subject_template TEXT,                -- Subject line (can include {{placeholders}})
            body_template TEXT,                   -- Email body (can include {{placeholders}})
            is_ai_crafted INTEGER DEFAULT 0,      -- 0=Use template, 1=Call AI crafter
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (campaign_id, step_number),    -- Step order unique per campaign
            FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id) ON DELETE CASCADE,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_step_campaign ON campaign_steps (campaign_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_step_organization ON campaign_steps (organization_id)")
        print(" -> Campaign Steps table checked/created.")

        # --- 8. NEW: Lead Campaign Status Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS lead_campaign_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            campaign_id INTEGER NOT NULL,
            organization_id INTEGER NOT NULL,      -- Denormalized
            current_step_number INTEGER DEFAULT 0, -- Last step COMPLETED (0=not started)
            status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'active', 'paused', 'completed', 'replied', 'bounced', 'unsubscribed', 'awaiting_scheduling', 'scheduled'
            last_email_sent_at TIMESTAMP,         -- When last step email was sent
            next_email_due_at TIMESTAMP,          -- OPTIONAL pre-calculated time for next send (can help scheduler query)
            last_response_type TEXT,              -- 'positive', 'negative', 'neutral', 'oof', 'none'
            last_response_at TIMESTAMP,
            error_message TEXT,                   -- Store bounce/error details
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (lead_id),                     -- Lead can only be in one status record at a time
            FOREIGN KEY (lead_id) REFERENCES leads (id) ON DELETE CASCADE,
            FOREIGN KEY (campaign_id) REFERENCES email_campaigns (id) ON DELETE CASCADE,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_lead ON lead_campaign_status (lead_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_campaign ON lead_campaign_status (campaign_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_organization ON lead_campaign_status (organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_status ON lead_campaign_status (status)") # For finding 'active' leads etc.
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status_due ON lead_campaign_status (next_email_due_at)") # If using this field
        print(" -> Lead Campaign Status table checked/created.")
        # --- End of New Tables ---

          # --- 9. NEW: Organization Email Settings Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organization_email_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL UNIQUE, -- One settings record per org
            provider_type TEXT,                      -- 'smtp', 'google_oauth', 'm365_oauth', 'sendgrid_api', etc.
            -- SMTP Specific (Store securely - **NEEDS ENCRYPTION IMPLEMENTATION**)
            smtp_host TEXT,
            smtp_port INTEGER,
            smtp_username TEXT,
            encrypted_smtp_password TEXT,            -- Store encrypted password/app password
            -- API Key Specific (Store securely - **NEEDS ENCRYPTION IMPLEMENTATION**)
            encrypted_api_key TEXT,                  -- e.g., for SendGrid
            -- OAuth Specific (Store securely - **NEEDS ENCRYPTION IMPLEMENTATION**)
            encrypted_access_token TEXT,
            encrypted_refresh_token TEXT,
            token_expiry TIMESTAMP,
            -- Common Fields
            verified_sender_email TEXT NOT NULL,     -- The validated email address they send from
            sender_name TEXT,                        -- Default display name
            is_configured INTEGER DEFAULT 0,         -- Flag: 0=Not setup, 1=Setup complete/validated
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_settings_organization ON organization_email_settings (organization_id)")
        print(" -> Organization Email Settings table checked/created.")
       
         # --- 9. NEW: Organization Email Settings Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organization_email_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL UNIQUE, -- One settings record per org
            provider_type TEXT,                      -- 'smtp', 'google_oauth', 'm365_oauth', 'sendgrid_api', etc.
            -- SMTP Specific (Store securely - **NEEDS ENCRYPTION IMPLEMENTATION**)
            smtp_host TEXT,
            smtp_port INTEGER,
            smtp_username TEXT,
            encrypted_smtp_password TEXT,            -- Store encrypted password/app password
            -- API Key Specific (Store securely - **NEEDS ENCRYPTION IMPLEMENTATION**)
            encrypted_api_key TEXT,                  -- e.g., for SendGrid
            -- OAuth Specific (Store securely - **NEEDS ENCRYPTION IMPLEMENTATION**)
            encrypted_access_token TEXT,
            encrypted_refresh_token TEXT,
            token_expiry TIMESTAMP,
            -- Common Fields
            verified_sender_email TEXT NOT NULL,     -- The validated email address they send from
            sender_name TEXT,                        -- Default display name
            is_configured INTEGER DEFAULT 0,         -- Flag: 0=Not setup, 1=Setup complete/validated
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_email_settings_organization ON organization_email_settings (organization_id)")
        print(" -> Organization Email Settings table checked/created.")
        # --- End New Table ---

        conn.commit()
        print("Database initialization sequence complete.")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR during initialization: {e}")
    finally:
        if conn: conn.close()




# ==========================================
# ORGANIZATION CRUD OPERATIONS
# ==========================================
# (Keep create_organization, get_organization_by_id, get_organization_by_name, get_all_organizations functions as they were)
def create_organization(name: str) -> Optional[Dict]:
    sql = "INSERT INTO organizations (name) VALUES (?)"
    # ... (rest of function) ...
    pass
def get_organization_by_id(organization_id: int) -> Optional[Dict]:
    sql = "SELECT * FROM organizations WHERE id = ?"
    # ... (rest of function) ...
    pass
def get_organization_by_name(name: str) -> Optional[Dict]:
    sql = "SELECT * FROM organizations WHERE name = ?"
    # ... (rest of function) ...
    pass
def get_all_organizations() -> List[Dict]:
    sql = "SELECT * FROM organizations ORDER BY name"
    # ... (rest of function) ...
    pass

# ==========================================
# USER CRUD OPERATIONS
# ==========================================
# (Keep create_user, get_user_by_id, get_user_by_email, get_users_by_organization functions as they were)
def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (?, ?, ?)"
    # ... (rest of function) ...
    pass
def get_user_by_id(user_id: int) -> Optional[Dict]:
    sql = "SELECT u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name FROM users u JOIN organizations o ON u.organization_id = o.id WHERE u.id = ?"
    # ... (rest of function) ...
    pass
def get_user_by_email(email: str) -> Optional[Dict]:
    sql = "SELECT u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name FROM users u JOIN organizations o ON u.organization_id = o.id WHERE u.email = ?"
    # ... (rest of function) ...
    pass
def get_users_by_organization(organization_id: int) -> List[Dict]:
    sql = "SELECT u.id, u.email, u.organization_id, o.name as organization_name FROM users u JOIN organizations o ON u.organization_id = o.id WHERE u.organization_id = ? ORDER BY u.email"
    # ... (rest of function) ...
    pass

# ==========================================
# LEAD CRUD OPERATIONS (Tenant-Aware)
# ==========================================
# (Keep save_lead, get_lead_by_id, get_lead_by_email, get_leads_by_organization, update_lead_partial, delete_lead functions as they were)
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
    # ... (UPSERT logic) ...
    pass
def get_lead_by_id(lead_id: int, organization_id: int) -> Optional[Dict]:
    # ... (SELECT logic) ...
    pass
def get_lead_by_email(email: str, organization_id: int) -> Optional[Dict]:
    # ... (SELECT logic) ...
    pass
def get_leads_by_organization(organization_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
    # ... (SELECT logic with pagination) ...
    pass
def update_lead_partial(lead_id: int, organization_id: int, update_data: Dict[str, Any]) -> Optional[Dict]:
    # ... (UPDATE logic) ...
    pass
def delete_lead(lead_id: int, organization_id: int) -> bool:
    # ... (DELETE logic) ...
    pass


# ==========================================
# NEW: ICP CRUD OPERATIONS (Tenant-Aware)
# ==========================================

def _parse_icp_json_fields(icp_row: sqlite3.Row) -> Optional[Dict]:
    """Helper to parse JSON fields from an ICP database row."""
    if not icp_row:
        return None
    icp_data = dict(icp_row)
    # List all columns expected to store JSON strings
    json_fields = ["title_keywords", "industry_keywords", "company_size_rules", "location_keywords"]
    for field in json_fields:
        field_value = icp_data.get(field)
        if field_value and isinstance(field_value, str): # Check if it's a non-empty string
            try:
                icp_data[field] = json.loads(field_value)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON for field '{field}' in ICP ID {icp_data.get('id')}")
                icp_data[field] = None # Set to None if parsing fails
        elif not field_value:
             icp_data[field] = None # Ensure key exists as None if DB value was NULL or empty
        # If field_value is already parsed (e.g., if DB supports JSON type natively), keep it
    return icp_data

def create_or_update_icp(organization_id: int, icp_definition: Dict[str, Any]) -> Optional[Dict]:
    """
    Creates or updates the ICP definition for a specific organization.
    Expects criteria fields in icp_definition (e.g., 'title_keywords' as a list).
    Returns the saved ICP data as a dictionary (with JSON parsed).
    """
    conn = None
    saved_icp = None
    columns = [
        "organization_id", "name", "title_keywords", "industry_keywords",
        "company_size_rules", "location_keywords" # Add other ICP columns here
    ]
    # Prepare data, converting Python lists/dicts to JSON strings
    params = {
        "organization_id": organization_id,
        "name": icp_definition.get("name", f"Org {organization_id} ICP"), # Default name
        # Use json.dumps ensuring None is stored if input is None or empty list/dict
        "title_keywords": json.dumps(icp_definition.get("title_keywords") or []),
        "industry_keywords": json.dumps(icp_definition.get("industry_keywords") or []),
        "company_size_rules": json.dumps(icp_definition.get("company_size_rules") or {}),
        "location_keywords": json.dumps(icp_definition.get("location_keywords") or []),
    }

    set_clause_parts = [f"{col} = excluded.{col}" for col in columns if col != 'organization_id']
    set_clause_parts.append("updated_at = CURRENT_TIMESTAMP") # Update timestamp on update
    set_clause = ", ".join(set_clause_parts)

    sql = f"""
        INSERT INTO icps ({", ".join(columns)})
        VALUES ({", ".join([f":{col}" for col in columns])})
        ON CONFLICT(organization_id) DO UPDATE SET {set_clause};
    """

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        print(f"Saved/Updated ICP for Org ID: {organization_id}")
        saved_icp = get_icp_by_organization_id(organization_id)
    except sqlite3.IntegrityError as e:
         print(f"Database integrity error saving ICP for Org ID {organization_id}: {e}")
    except sqlite3.Error as e:
        print(f"Database error saving ICP for Org ID {organization_id}: {e}")
    except Exception as e:
        print(f"Unexpected error saving ICP for Org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return saved_icp

def get_icp_by_organization_id(organization_id: int) -> Optional[Dict]:
    """
    Fetches the ICP definition for a specific organization.
    Returns a dictionary with JSON fields parsed, or None if not found.
    """
    sql = "SELECT * FROM icps WHERE organization_id = ?"
    conn = None
    icp_data = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (organization_id,))
        result = cursor.fetchone()
        if result:
            icp_data = _parse_icp_json_fields(result)
    except sqlite3.Error as e:
        print(f"Database error getting ICP for Org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return icp_data

def delete_icp(organization_id: int) -> bool:
    """Deletes the ICP definition for a specific organization."""
    sql = "DELETE FROM icps WHERE organization_id = ?"
    # ... (rest of delete logic) ...
    pass

# ==========================================
# NEW: OFFERING CRUD OPERATIONS (Tenant-Aware)
# ==========================================

def _parse_offering_json_fields(offering_row: sqlite3.Row) -> Optional[Dict]:
    """Helper to parse JSON fields from an Offering database row."""
    if not offering_row:
        return None
    offering_data = dict(offering_row)
    # List columns storing JSON strings
    json_fields = ["key_features", "target_pain_points"]
    for field in json_fields:
        field_value = offering_data.get(field)
        if field_value and isinstance(field_value, str):
            try:
                offering_data[field] = json.loads(field_value)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON for field '{field}' in Offering ID {offering_data.get('id')}")
                offering_data[field] = [] # Default to empty list on parse error
        elif not field_value:
             offering_data[field] = [] # Default to empty list if NULL/empty
    return offering_data

def create_offering(organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    """Creates a new offering for an organization."""
    conn = None
    saved_offering = None
    columns = [
        "organization_id", "name", "description", "key_features",
        "target_pain_points", "call_to_action", "is_active"
    ]
    params = {
        "organization_id": organization_id,
        "name": offering_data.get("name", "Unnamed Offering"), # Require name ideally
        "description": offering_data.get("description"),
        "key_features": json.dumps(offering_data.get("key_features") or []),
        "target_pain_points": json.dumps(offering_data.get("target_pain_points") or []),
        "call_to_action": offering_data.get("call_to_action"),
        "is_active": int(offering_data.get("is_active", 1)) # Default to active
    }
    sql = f"""
        INSERT INTO offerings ({", ".join(columns)})
        VALUES ({", ".join([f":{col}" for col in columns])})
    """
    try:
        if not params["name"]: raise ValueError("Offering name cannot be empty") # Basic validation

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        offering_id = cursor.lastrowid
        conn.commit()
        print(f"Created offering '{params['name']}' (ID: {offering_id}) for Org ID: {organization_id}")
        saved_offering = get_offering_by_id(offering_id, organization_id) # Fetch created offering
    except sqlite3.Error as e:
        print(f"Database error creating offering for Org ID {organization_id}: {e}")
    except Exception as e:
        print(f"Unexpected error creating offering for Org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return saved_offering


def update_offering(offering_id: int, organization_id: int, offering_data: Dict[str, Any]) -> Optional[Dict]:
    """Updates an existing offering for an organization."""
    conn = None
    updated_offering = None
    # Filter allowed update fields
    allowed_columns = {
        "name", "description", "key_features", "target_pain_points",
        "call_to_action", "is_active"
    }
    update_fields = {k:v for k,v in offering_data.items() if k in allowed_columns}

    if not update_fields:
        print(f"No valid fields provided for updating offering ID {offering_id}")
        return get_offering_by_id(offering_id, organization_id) # Return current if no changes

    # Prepare params, converting lists to JSON
    params = {}
    set_parts = []
    for key, value in update_fields.items():
        param_name = f"p_{key}" # Use unique param names
        if key in ["key_features", "target_pain_points"]:
             params[param_name] = json.dumps(value or [])
        elif key == "is_active":
             params[param_name] = int(bool(value)) # Ensure 0 or 1
        else:
             params[param_name] = value
        set_parts.append(f"{key} = :{param_name}")

    # Add updated_at timestamp
    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    set_clause = ", ".join(set_parts)

    # Add WHERE clause params
    params["offering_id"] = offering_id
    params["organization_id"] = organization_id

    sql = f"""
        UPDATE offerings SET {set_clause}
        WHERE id = :offering_id AND organization_id = :organization_id
    """

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        if cursor.rowcount > 0:
            print(f"Updated offering ID {offering_id} for Org ID: {organization_id}")
            updated_offering = get_offering_by_id(offering_id, organization_id)
        else:
             print(f"Offering ID {offering_id} not found or not owned by Org ID {organization_id} for update.")

    except sqlite3.Error as e:
        print(f"Database error updating offering ID {offering_id} for Org ID {organization_id}: {e}")
    except Exception as e:
        print(f"Unexpected error updating offering ID {offering_id} for Org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return updated_offering


def get_offering_by_id(offering_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a single offering by ID, ensuring it belongs to the organization."""
    sql = "SELECT * FROM offerings WHERE id = ? AND organization_id = ?"
    conn = None
    offering_data = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (offering_id, organization_id))
        result = cursor.fetchone()
        if result: offering_data = _parse_offering_json_fields(result)
    except sqlite3.Error as e:
        print(f"Database error getting offering ID {offering_id} for Org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return offering_data


def get_offerings_by_organization_id(organization_id: int, active_only: bool = True) -> List[Dict]:
    """
    Fetches all offerings for a specific organization.
    Returns a list of dictionaries with JSON fields parsed.
    """
    offerings = []
    conn = None
    sql = "SELECT * FROM offerings WHERE organization_id = ?"
    params = [organization_id]
    if active_only:
        sql += " AND is_active = 1"
    sql += " ORDER BY name" # Or order by created_at

    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        results = cursor.fetchall()
        for row in results:
            parsed = _parse_offering_json_fields(row)
            if parsed: offerings.append(parsed)
    except sqlite3.Error as e:
        print(f"Database error getting offerings for Org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return offerings


def delete_offering(offering_id: int, organization_id: int) -> bool:
    """Deletes an offering by ID, ensuring it belongs to the organization."""
    sql = "DELETE FROM offerings WHERE id = ? AND organization_id = ?"
    conn = None
    success = False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (offering_id, organization_id))
        conn.commit()
        if cursor.rowcount > 0:
            print(f"Deleted offering ID {offering_id} for Org ID {organization_id}.")
            success = True
        else:
            print(f"Offering ID {offering_id} not found for Org ID {organization_id}.")
    except sqlite3.Error as e:
        print(f"Database error deleting offering ID {offering_id} for Org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return success

# --- Campaign CRUD ---
def create_campaign(organization_id: int, name: str, description: Optional[str] = None, is_active: bool = True) -> Optional[Dict]:
    """Creates a new email campaign for an organization."""
    sql = "INSERT INTO email_campaigns (organization_id, name, description, is_active) VALUES (?, ?, ?, ?)"
    params = (organization_id, name, description, int(is_active))
    conn = None; new_id = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); new_id = cursor.lastrowid
        conn.commit(); print(f"Created campaign '{name}' (ID: {new_id}) for Org {organization_id}")
    except sqlite3.Error as e: print(f"DB Error creating campaign for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    # Fetch the created campaign to return full data
    return get_campaign_by_id(new_id, organization_id) if new_id else None

def get_campaign_by_id(campaign_id: int, organization_id: int) -> Optional[Dict]:
    """Gets a specific campaign ensuring it belongs to the organization."""
    sql = "SELECT * FROM email_campaigns WHERE id = ? AND organization_id = ?"
    conn = None; campaign = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id)); result = cursor.fetchone()
        if result: campaign = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting campaign ID {campaign_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaign

def get_campaigns_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    """Fetches all campaigns for a specific organization."""
    sql = "SELECT * FROM email_campaigns WHERE organization_id = ?"
    params = [organization_id]
    if active_only: sql += " AND is_active = 1"
    sql += " ORDER BY name"
    conn = None; campaigns = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, params); results = cursor.fetchall()
        for row in results: campaigns.append(dict(row))
    except sqlite3.Error as e: print(f"DB Error getting campaigns for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaigns

# --- Step CRUD ---
def create_campaign_step(campaign_id: int, organization_id: int, step_number: int, delay_days: int, subject: Optional[str], body: Optional[str], is_ai: bool = False) -> Optional[Dict]:
    """Creates a step within a campaign."""
    sql = """
        INSERT INTO campaign_steps
        (campaign_id, organization_id, step_number, delay_days, subject_template, body_template, is_ai_crafted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
    params = (campaign_id, organization_id, step_number, delay_days, subject, body, int(is_ai))
    conn = None; new_id = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); new_id = cursor.lastrowid
        conn.commit(); print(f"Created step {step_number} (ID: {new_id}) for Campaign {campaign_id}, Org {organization_id}")
    except sqlite3.IntegrityError as ie: print(f"DB Integrity Error creating step {step_number} for Camp {campaign_id}: {ie}") # e.g., step exists, FK fail
    except sqlite3.Error as e: print(f"DB Error creating step {step_number} for Camp {campaign_id}: {e}")
    finally:
        if conn: conn.close()
    # Fetch created step if needed, or just return ID/success? Returning ID for now.
    return {"id": new_id} if new_id else None # Basic return

def get_steps_for_campaign(campaign_id: int, organization_id: int) -> List[Dict]:
    """Fetches all steps for a campaign, ordered by step number."""
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = ? AND organization_id = ? ORDER BY step_number"
    conn = None; steps = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id)); results = cursor.fetchall()
        for row in results: steps.append(dict(row))
    except sqlite3.Error as e: print(f"DB Error getting steps for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return steps

def get_next_campaign_step(campaign_id: int, organization_id: int, current_step_number: int) -> Optional[Dict]:
    """Fetches the details of the step AFTER the current_step_number."""
    sql = """
        SELECT * FROM campaign_steps
        WHERE campaign_id = ? AND organization_id = ? AND step_number = ?
        ORDER BY step_number
        LIMIT 1
    """
    next_step_number = current_step_number + 1
    conn = None; step_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id, next_step_number))
        result = cursor.fetchone()
        if result: step_data = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting next step ({next_step_number}) for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return step_data

# --- Lead Status CRUD ---
def enroll_lead_in_campaign(lead_id: int, campaign_id: int, organization_id: int) -> Optional[Dict]:
    """Creates the initial 'active' status record for a lead entering a campaign."""
    # Potentially calculate first due date here based on step 1 delay? Or handle in scheduler.
    # next_due = datetime.now() + timedelta(days=step1_delay) # Example
    sql = """
        INSERT INTO lead_campaign_status (lead_id, campaign_id, organization_id, status, current_step_number)
        VALUES (?, ?, ?, 'active', 0)
    """
    params = (lead_id, campaign_id, organization_id)
    conn = None; status_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); status_id = cursor.lastrowid
        conn.commit(); print(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {status_id})")
        status_data = get_lead_campaign_status_by_id(status_id, organization_id) # Fetch created record
    except sqlite3.IntegrityError as ie: print(f"DB Integrity Error enrolling lead {lead_id} in camp {campaign_id}: {ie}") # Lead already enrolled? FK fail?
    except sqlite3.Error as e: print(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates specific fields (like status, step, timestamps) for a lead's campaign status."""
    # Ensure only allowed fields are updated
    allowed_fields = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message"}
    valid_updates = {k:v for k,v in updates.items() if k in allowed_fields}
    if not valid_updates: return get_lead_campaign_status_by_id(status_id, organization_id) # No changes

    set_parts = [f"{key} = :{key}" for key in valid_updates.keys()]
    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    set_clause = ", ".join(set_parts)
    params = valid_updates
    params["status_id"] = status_id
    params["organization_id"] = organization_id

    sql = f"UPDATE lead_campaign_status SET {set_clause} WHERE id = :status_id AND organization_id = :organization_id"
    conn = None; success = False
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); conn.commit()
        if cursor.rowcount > 0: success = True; print(f"Updated lead campaign status ID {status_id}")
        else: print(f"Lead campaign status ID {status_id} not found for Org {organization_id}")
    except sqlite3.Error as e: print(f"DB Error updating lead status ID {status_id}: {e}")
    finally:
        if conn: conn.close()
    return get_lead_campaign_status_by_id(status_id, organization_id) if success else None


def get_active_leads_due_for_step(organization_id: int) -> List[Dict]:
    """
    Finds leads in 'active' status potentially due for their next email.
    Requires JOINING to get next step delay and comparing timestamps.
    NOTE: This is a complex query, simplified here. May need optimization or rely on pre-calculated 'next_email_due_at'.
    """
    print(f"DB: Querying for active leads due for Org {organization_id}...") # Add log
    leads_due = []
    conn = None
    # This simplified query assumes you will calculate due date in the scheduler based on last_sent + delay
    # It just gets active leads and their current state.
    # A better query would pre-calculate or filter on next_email_due_at <= current_time
    sql = """
        SELECT lcs.*, c.name as campaign_name -- Select all status fields, maybe campaign name
        FROM lead_campaign_status lcs
        JOIN email_campaigns c ON lcs.campaign_id = c.id
        WHERE lcs.organization_id = ? AND lcs.status = 'active'
        ORDER BY lcs.last_email_sent_at ASC -- Process oldest first potentially
    """
    params = (organization_id,)
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, params); results = cursor.fetchall()
        for row in results: leads_due.append(dict(row))
        print(f"DB: Found {len(leads_due)} potentially active leads for Org {organization_id}.") # Add log
    except sqlite3.Error as e: print(f"DB Error getting active due leads for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return leads_due

def get_lead_campaign_status_by_id(status_id: int, organization_id: int) -> Optional[Dict]:
    """Gets a specific lead campaign status record by its ID, ensuring org match."""
    sql = "SELECT * FROM lead_campaign_status WHERE id = ? AND organization_id = ?"
    conn = None; status_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (status_id, organization_id)); result = cursor.fetchone()
        if result: status_data = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting lead status ID {status_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

def get_lead_campaign_status(lead_id: int, organization_id: int) -> Optional[Dict]:
    """Gets the current campaign status for a specific lead."""
    sql = "SELECT * FROM lead_campaign_status WHERE lead_id = ? AND organization_id = ?"
    conn = None; status_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (lead_id, organization_id)); result = cursor.fetchone()
        if result: status_data = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting campaign status for lead {lead_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

# ==========================================
# NEW: ORGANIZATION EMAIL SETTINGS CRUD
# ==========================================

# --- === IMPORTANT: Encryption/Decryption === ---
# You MUST implement functions to encrypt/decrypt sensitive fields
# before saving to/after reading from the DB. Use a strong library like 'cryptography'.
# Store the main encryption key SECURELY (e.g., Render Secret File or KMS).
# These are placeholders!
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None: return None
    logger.warning("ENCRYPTION NOT IMPLEMENTED. Storing sensitive data as plain text!") # Add logger import if not present
    # Replace with actual encryption using cryptography library and your secret key
    return plain_text # Placeholder only

def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None: return None
    logger.warning("DECRYPTION NOT IMPLEMENTED. Returning plain text (assuming not encrypted).")
    # Replace with actual decryption using cryptography library and your secret key
    return encrypted_text # Placeholder only
# --- ====================================== ---


def save_org_email_settings(organization_id: int, settings_data: Dict[str, Any]) -> Optional[Dict]:
    """Creates or updates the email settings for an organization."""
    conn = None
    saved_settings = None
    # Encrypt sensitive fields before saving
    encrypted_password = _encrypt_data(settings_data.get("smtp_password")) # Get raw password from input dict
    encrypted_api_key = _encrypt_data(settings_data.get("api_key"))
    encrypted_access_token = _encrypt_data(settings_data.get("access_token"))
    encrypted_refresh_token = _encrypt_data(settings_data.get("refresh_token"))

    columns = [
        "organization_id", "provider_type", "smtp_host", "smtp_port", "smtp_username",
        "encrypted_smtp_password", "encrypted_api_key", "encrypted_access_token",
        "encrypted_refresh_token", "token_expiry", "verified_sender_email",
        "sender_name", "is_configured"
    ]
    params = {
        "organization_id": organization_id,
        "provider_type": settings_data.get("provider_type"),
        "smtp_host": settings_data.get("smtp_host"),
        "smtp_port": settings_data.get("smtp_port"),
        "smtp_username": settings_data.get("smtp_username"),
        "encrypted_smtp_password": encrypted_password,
        "encrypted_api_key": encrypted_api_key,
        "encrypted_access_token": encrypted_access_token,
        "encrypted_refresh_token": encrypted_refresh_token,
        "token_expiry": settings_data.get("token_expiry"), # Store expiry if using OAuth
        "verified_sender_email": settings_data.get("verified_sender_email"), # This MUST be validated elsewhere
        "sender_name": settings_data.get("sender_name"),
        "is_configured": int(settings_data.get("is_configured", 0))
    }

    set_clause_parts = [f"{col} = excluded.{col}" for col in columns if col != 'organization_id']
    set_clause_parts.append("updated_at = CURRENT_TIMESTAMP")
    set_clause = ", ".join(set_clause_parts)

    sql = f"""
        INSERT INTO organization_email_settings ({", ".join(columns)})
        VALUES ({", ".join([f":{col}" for col in columns])})
        ON CONFLICT(organization_id) DO UPDATE SET {set_clause};
    """
    try:
        # Basic validation
        if not params["verified_sender_email"]: raise ValueError("Verified sender email is required.")
        if not params["provider_type"]: raise ValueError("Provider type is required.")

        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); conn.commit()
        print(f"Saved/Updated Email Settings for Org ID: {organization_id}")
        saved_settings = get_org_email_settings_from_db(organization_id) # Fetch to return decrypted data
    except sqlite3.Error as e: print(f"DB Error saving email settings for Org {organization_id}: {e}")
    except ValueError as ve: print(f"Validation Error saving email settings for Org {organization_id}: {ve}")
    except Exception as e: print(f"Unexpected error saving email settings for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return saved_settings


def get_org_email_settings_from_db(organization_id: int) -> Optional[Dict]:
    """Fetches email settings for an organization and decrypts sensitive fields."""
    sql = "SELECT * FROM organization_email_settings WHERE organization_id = ?"
    conn = None
    settings_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (organization_id,)); result = cursor.fetchone()
        if result:
            settings_data = dict(result)
            # Decrypt sensitive fields after fetching
            settings_data["smtp_password"] = _decrypt_data(settings_data.pop("encrypted_smtp_password", None))
            settings_data["api_key"] = _decrypt_data(settings_data.pop("encrypted_api_key", None))
            settings_data["access_token"] = _decrypt_data(settings_data.pop("encrypted_access_token", None))
            settings_data["refresh_token"] = _decrypt_data(settings_data.pop("encrypted_refresh_token", None))
    except sqlite3.Error as e: print(f"DB Error getting email settings for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return settings_data

# --- Campaign CRUD ---
def create_campaign(organization_id: int, name: str, description: Optional[str] = None, is_active: bool = True) -> Optional[Dict]:
    """Creates a new email campaign for an organization."""
    sql = "INSERT INTO email_campaigns (organization_id, name, description, is_active) VALUES (?, ?, ?, ?)"
    params = (organization_id, name, description, int(is_active))
    conn = None; new_id = None; campaign_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); new_id = cursor.lastrowid
        conn.commit(); print(f"Created campaign '{name}' (ID: {new_id}) for Org {organization_id}")
        if new_id: campaign_data = get_campaign_by_id(new_id, organization_id) # Fetch created data
    except sqlite3.Error as e: print(f"DB Error creating campaign for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaign_data

def get_campaign_by_id(campaign_id: int, organization_id: int) -> Optional[Dict]:
    """Gets a specific campaign ensuring it belongs to the organization."""
    sql = "SELECT * FROM email_campaigns WHERE id = ? AND organization_id = ?"
    conn = None; campaign = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id)); result = cursor.fetchone()
        if result: campaign = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting campaign ID {campaign_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaign

def get_campaigns_by_organization(organization_id: int, active_only: bool = True) -> List[Dict]:
    """Fetches all campaigns for a specific organization."""
    sql = "SELECT * FROM email_campaigns WHERE organization_id = ?"
    params = [organization_id]
    if active_only: sql += " AND is_active = 1"
    sql += " ORDER BY name"
    conn = None; campaigns = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, params); results = cursor.fetchall()
        for row in results: campaigns.append(dict(row))
    except sqlite3.Error as e: print(f"DB Error getting campaigns for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return campaigns

# --- Step CRUD ---
def create_campaign_step(campaign_id: int, organization_id: int, step_number: int, delay_days: int, subject: Optional[str], body: Optional[str], is_ai: bool = False) -> Optional[Dict]:
    """Creates a step within a campaign."""
    sql = """
        INSERT INTO campaign_steps
        (campaign_id, organization_id, step_number, delay_days, subject_template, body_template, is_ai_crafted)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """
    params = (campaign_id, organization_id, step_number, delay_days, subject, body, int(is_ai))
    conn = None; new_id = None; step_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); new_id = cursor.lastrowid
        conn.commit(); print(f"Created step {step_number} (ID: {new_id}) for Campaign {campaign_id}, Org {organization_id}")
        if new_id: step_data = get_campaign_step_by_id(new_id, organization_id) # Fetch created step
    except sqlite3.IntegrityError as ie: print(f"DB Integrity Error creating step {step_number} for Camp {campaign_id}: {ie}") # e.g., step exists, FK fail
    except sqlite3.Error as e: print(f"DB Error creating step {step_number} for Camp {campaign_id}: {e}")
    finally:
        if conn: conn.close()
    return step_data # Return full step data dict

def get_campaign_step_by_id(step_id: int, organization_id: int) -> Optional[Dict]:
    """Gets a specific campaign step ensuring it belongs to the organization."""
    # Added organization_id check for security/multi-tenancy
    sql = "SELECT * FROM campaign_steps WHERE id = ? AND organization_id = ?"
    conn = None; step = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (step_id, organization_id)); result = cursor.fetchone()
        if result: step = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting step ID {step_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return step

def get_steps_for_campaign(campaign_id: int, organization_id: int) -> List[Dict]:
    """Fetches all steps for a campaign, ordered by step number."""
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = ? AND organization_id = ? ORDER BY step_number"
    conn = None; steps = []
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id)); results = cursor.fetchall()
        for row in results: steps.append(dict(row))
    except sqlite3.Error as e: print(f"DB Error getting steps for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return steps

def get_next_campaign_step(campaign_id: int, organization_id: int, current_step_number: int) -> Optional[Dict]:
    """Fetches the details of the step AFTER the current_step_number."""
    sql = "SELECT * FROM campaign_steps WHERE campaign_id = ? AND organization_id = ? AND step_number = ? LIMIT 1"
    next_step_number = current_step_number + 1
    conn = None; step_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (campaign_id, organization_id, next_step_number))
        result = cursor.fetchone()
        if result: step_data = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting next step ({next_step_number}) for Camp {campaign_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return step_data

# --- Lead Status CRUD ---
def enroll_lead_in_campaign(lead_id: int, campaign_id: int, organization_id: int) -> Optional[Dict]:
    """Creates the initial 'active' status record for a lead entering a campaign."""
    sql = """
        INSERT INTO lead_campaign_status (lead_id, campaign_id, organization_id, status, current_step_number)
        VALUES (?, ?, ?, 'active', 0)
        """
    params = (lead_id, campaign_id, organization_id)
    conn = None; status_data = None
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); status_id = cursor.lastrowid
        conn.commit(); print(f"Enrolled Lead ID {lead_id} in Campaign ID {campaign_id} (Status ID: {status_id})")
        status_data = get_lead_campaign_status_by_id(status_id, organization_id)
    except sqlite3.IntegrityError as ie: print(f"DB Integrity Error enrolling lead {lead_id} in camp {campaign_id}: {ie}") # Likely already enrolled
    except sqlite3.Error as e: print(f"DB Error enrolling lead {lead_id} in camp {campaign_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

def update_lead_campaign_status(status_id: int, organization_id: int, updates: Dict[str, Any]) -> Optional[Dict]:
    """Updates specific fields (like status, step, timestamps) for a lead's campaign status."""
    allowed_fields = {"current_step_number", "status", "last_email_sent_at", "next_email_due_at", "last_response_type", "last_response_at", "error_message"}
    valid_updates = {k:v for k,v in updates.items() if k in allowed_fields}
    if not valid_updates: return get_lead_campaign_status_by_id(status_id, organization_id)

    set_parts = [f"{key} = :{key}" for key in valid_updates.keys()]
    set_parts.append("updated_at = CURRENT_TIMESTAMP")
    set_clause = ", ".join(set_parts)
    params = valid_updates
    params["status_id"] = status_id
    params["organization_id"] = organization_id

    sql = f"UPDATE lead_campaign_status SET {set_clause} WHERE id = :status_id AND organization_id = :organization_id"
    conn = None; success = False
    try:
        conn = get_connection(); cursor = conn.cursor()
        cursor.execute(sql, params); conn.commit()
        if cursor.rowcount > 0: success = True; print(f"Updated lead campaign status ID {status_id}")
        else: print(f"Lead campaign status ID {status_id} not found for Org {organization_id}")
    except sqlite3.Error as e: print(f"DB Error updating lead status ID {status_id}: {e}")
    finally:
        if conn: conn.close()
    return get_lead_campaign_status_by_id(status_id, organization_id) if success else None


def get_active_leads_due_for_step(organization_id: Optional[int] = None) -> List[Dict]:
    """
    Finds leads in 'active' status potentially due for their next email.
    Currently fetches ALL active leads across all orgs if organization_id is None.
    Needs enhancement to properly calculate due time based on last_sent + next_step_delay.
    """
    # WARNING: This simplified query fetches ALL active leads.
    # The scheduler logic currently recalculates due time in Python.
    # A production query should filter based on calculated next_email_due_at <= now()
    logger.warning("DB get_active_leads_due_for_step query is simplified. Filtering happens in scheduler agent.")
    leads_due = []
    conn = None
    sql = """
        SELECT lcs.*, c.name as campaign_name
        FROM lead_campaign_status lcs
        JOIN email_campaigns c ON lcs.campaign_id = c.id
        WHERE lcs.status = 'active'
    """
    params = []
    if organization_id is not None:
        sql += " AND lcs.organization_id = ?"
        params.append(organization_id)
    sql += " ORDER BY lcs.organization_id, lcs.last_email_sent_at ASC NULLS FIRST" # Process uncontacted first

    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, params); results = cursor.fetchall()
        for row in results: leads_due.append(dict(row))
        logger.debug(f"DB: Found {len(leads_due)} total active leads {f'for Org {organization_id}' if organization_id else 'across all orgs'}.")
    except sqlite3.Error as e: print(f"DB Error getting active leads{f' for Org {organization_id}' if organization_id else ''}: {e}")
    finally:
        if conn: conn.close()
    return leads_due

def get_lead_campaign_status_by_id(status_id: int, organization_id: int) -> Optional[Dict]:
    """Gets a specific lead campaign status record by its ID, ensuring org match."""
    sql = "SELECT * FROM lead_campaign_status WHERE id = ? AND organization_id = ?"
    conn = None; status_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (status_id, organization_id)); result = cursor.fetchone()
        if result: status_data = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting lead status ID {status_id} for Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

def get_lead_campaign_status(lead_id: int, organization_id: int) -> Optional[Dict]:
    """Gets the current campaign status for a specific lead."""
    sql = "SELECT * FROM lead_campaign_status WHERE lead_id = ? AND organization_id = ?"
    conn = None; status_data = None
    try:
        conn = get_connection(); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
        cursor.execute(sql, (lead_id, organization_id)); result = cursor.fetchone()
        if result: status_data = dict(result)
    except sqlite3.Error as e: print(f"DB Error getting campaign status for lead {lead_id}, Org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return status_data

# Ensure logger is available if used in _encrypt_data/_decrypt_data
try:
    from app.utils.logger import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# --- === Placeholder Encryption Functions === ---
# Replace with actual implementation using 'cryptography' library
def _encrypt_data(plain_text: Optional[str]) -> Optional[str]:
    if plain_text is None: return None
    logger.warning("ENCRYPTION NOT IMPLEMENTED. Storing sensitive data as plain text!")
    return plain_text # Placeholder only

def _decrypt_data(encrypted_text: Optional[str]) -> Optional[str]:
    if encrypted_text is None: return None
    # logger.warning("DECRYPTION NOT IMPLEMENTED.") # Reduce log noise
    return encrypted_text # Placeholder only
# --- ======================================= ---
