# app/db/database.py

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any
import json # Needed for ICP JSON handling

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
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)


# --- Database Initialization (Multi-Tenant + ICPs) ---
def initialize_db():
    """Creates/updates tables: organizations, users, leads, icps."""
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
            name TEXT,
            email TEXT NOT NULL COLLATE NOCASE,
            company TEXT,
            title TEXT,
            source TEXT,
            linkedin_profile TEXT,
            company_size TEXT,
            industry TEXT,
            location TEXT,
            matched INTEGER DEFAULT 0,
            reason TEXT,
            crm_status TEXT DEFAULT 'pending',
            appointment_confirmed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (organization_id, email),
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email)")
        print(" -> Leads table checked/created/modified.")

        # --- 4. NEW: ICPs Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS icps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL UNIQUE, -- One ICP per org for now
            name TEXT DEFAULT 'Default ICP',
            title_keywords TEXT,      -- Stores JSON list: '["cto", "cio"]'
            industry_keywords TEXT,   -- Stores JSON list: '["saas"]'
            company_size_rules TEXT,  -- Stores JSON dict or list: '{"min": 50}' or '["51-200"]'
            location_keywords TEXT,   -- Stores JSON list: '["london"]'
            # Add other criteria fields as needed (e.g., pain_points TEXT)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_icp_organization ON icps (organization_id)")
        print(" -> ICPs table checked/created.")
        # --- End of New Table ---

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
