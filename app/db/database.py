# app/db/database.py

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict # Added for type hints
# Removed Enum as AppointmentStatus wasn't in the original file you provided

# --- Import Settings ---
# Assuming your config file is at app/utils/config.py
# This allows using DATABASE_URL from environment variables or .env
try:
    from app.utils.config import settings
except ImportError:
    # Fallback if settings cannot be imported (e.g., during initial setup)
    # You might want a more robust way to handle this depending on your project setup
    print("Warning: Could not import settings from app.utils.config. Using default DB path.")
    settings = None # Set settings to None or a default config object


# --- Determine Database Path ---
if settings and settings.DATABASE_URL.startswith("sqlite"):
    # Extract path for SQLite from settings DATABASE_URL
    # Assumes format like sqlite+aiosqlite:///./path/to/db.db or sqlite:///path/to/db.db
    db_url_path_part = settings.DATABASE_URL.split("///")[-1]
    # Resolve potentially relative paths based on project structure
    # If BASE_DIR is defined in config relative to project root:
    # DB_PATH = (Path(settings.BASE_DIR) / db_url_path_part).resolve()
    # Or simpler if path in URL is absolute or relative to where script runs:
    DB_PATH = Path(db_url_path_part).resolve()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True) # Ensure directory exists
    print(f"Using SQLite database path from settings: {DB_PATH}")
elif settings:
    # Handle other database types if needed - requires different connection logic below
    print(f"Warning: Non-SQLite DATABASE_URL ({settings.DATABASE_URL}) specified in settings. Connection logic assumes SQLite.")
    DB_PATH = None # Indicate non-SQLite setup
else:
    # Fallback if settings import failed
    DB_PATH = Path(__file__).parent / "salestroopz_fallback.db"
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"Using fallback SQLite database path: {DB_PATH}")


# --- Database Connection Function ---
def get_connection():
    """Establishes and returns a connection to the SQLite database."""
    if not DB_PATH:
         raise ValueError("Database path is not configured correctly for SQLite.")
    # check_same_thread=False is needed for FastAPI background tasks with SQLite
    return sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10) # Added timeout


# --- Database Initialization (Multi-Tenant) ---
def initialize_db():
    """Creates organizations, users, and tenant-aware leads tables if they don't exist."""
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
            name TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print(" -> Organizations table checked/created.")

        # 2. Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            hashed_password TEXT NOT NULL,
            organization_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON users (email)")
        print(" -> Users table checked/created.")

        # 3. Leads Table (Modified for Multi-Tenancy + Enriched Fields)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL, -- Added
            name TEXT,
            email TEXT NOT NULL,
            company TEXT,
            title TEXT,
            source TEXT,
            linkedin_profile TEXT,          -- Added for enrichment
            company_size TEXT,              -- Added for enrichment
            industry TEXT,                  -- Added for enrichment
            location TEXT,                  -- Added for enrichment
            matched INTEGER DEFAULT 0,
            reason TEXT,
            crm_status TEXT DEFAULT 'pending',
            appointment_confirmed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Added
            -- Email should be unique *within* an organization
            UNIQUE (organization_id, email),
            FOREIGN KEY (organization_id) REFERENCES organizations (id)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email)") # Index for upsert
        print(" -> Leads table checked/created/modified for multi-tenancy.")

        conn.commit()
        print("Database initialization sequence complete.")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR during initialization: {e}")
        # Consider raising the exception depending on how critical initialization is
        # raise e
    finally:
        if conn:
            conn.close()


# --- NEW User/Org CRUD Functions ---

def create_organization(name: str) -> Optional[int]:
    """Creates a new organization and returns its ID, or None on failure."""
    sql = "INSERT INTO organizations (name) VALUES (?)"
    conn = None
    org_id = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (name,))
        conn.commit()
        org_id = cursor.lastrowid
        print(f"Created organization '{name}' with ID: {org_id}")
    except sqlite3.IntegrityError:
        print(f"Organization name '{name}' already exists.")
        # Optionally, fetch the ID of the existing org here if needed
    except sqlite3.Error as e:
        print(f"Database error creating organization '{name}': {e}")
    finally:
        if conn: conn.close()
    return org_id

def get_user_by_email(email: str) -> Optional[Dict]:
    """Fetches a user by email, returns dict (incl org name) or None."""
    sql = """
        SELECT u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.email = ?
    """
    user = None
    conn = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row # Return dict-like rows
        cursor = conn.cursor()
        cursor.execute(sql, (email,))
        result = cursor.fetchone()
        if result:
            user = dict(result)
    except sqlite3.Error as e:
        print(f"Database error getting user by email '{email}': {e}")
    finally:
        if conn: conn.close()
    return user

def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    """Creates a new user associated with an organization."""
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (?, ?, ?)"
    conn = None
    user_data = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (email, hashed_password, organization_id))
        conn.commit()
        user_id = cursor.lastrowid
        print(f"Created user '{email}' for org ID {organization_id} with user ID: {user_id}")
        user_data = get_user_by_email(email) # Fetch created user data
    except sqlite3.IntegrityError:
        print(f"User email '{email}' already exists.")
    except sqlite3.Error as e:
        print(f"Database error creating user '{email}': {e}")
    finally:
        if conn: conn.close()
    return user_data # Return user data as dict or None


# --- MODIFIED Lead Functions (Multi-Tenant) ---

def save_lead_result(lead: dict, organization_id: int): # Added organization_id
    """Saves or updates a lead result for a specific organization."""
    conn = None
    required_fields = ["email"] # Only email needed for upsert logic
    if not lead.get("email"):
        print(f"Skipping lead save due to missing email: {lead.get('name')}")
        return

    # Include all columns from the new leads table schema
    sql_upsert = """
        INSERT INTO leads (
            organization_id, name, email, company, title, source, linkedin_profile,
            company_size, industry, location, matched, reason, crm_status,
            appointment_confirmed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(organization_id, email) DO UPDATE SET
            name=excluded.name,
            company=excluded.company,
            title=excluded.title,
            source=excluded.source,
            linkedin_profile=excluded.linkedin_profile,
            company_size=excluded.company_size,
            industry=excluded.industry,
            location=excluded.location,
            matched=excluded.matched,
            reason=excluded.reason,
            crm_status=excluded.crm_status,
            appointment_confirmed=excluded.appointment_confirmed;
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Prepare data, handling potential missing keys and types
        match_result_dict = lead.get("match_result", {}) # Check if agent provides this
        matched_int = int(match_result_dict.get("matched", lead.get("matched", 0)))
        appt_confirmed_int = int(lead.get("appointment_confirmed", 0))

        # Safely get potentially missing enrichment fields
        linkedin = lead.get("linkedin_profile")
        size = lead.get("company_size")
        industry = lead.get("industry")
        location = lead.get("location")

        params = (
            organization_id,
            lead.get("name", ""),
            lead.get("email"), # Already checked for presence
            lead.get("company", ""),
            lead.get("title", ""),
            lead.get("source", "unknown"),
            linkedin,
            size,
            industry,
            location,
            matched_int,
            match_result_dict.get("reason", lead.get("reason", "")),
            lead.get("crm_status", "pending"),
            appt_confirmed_int
        )
        cursor.execute(sql_upsert, params)
        conn.commit()
    except sqlite3.Error as e:
        print(f"DATABASE ERROR saving lead for org {organization_id}, email {lead.get('email')}: {e}")
    except Exception as e:
         # Catch other potential errors (e.g., type conversion)
         print(f"UNEXPECTED ERROR saving lead for org {organization_id}, email {lead.get('email')}: {e}")
    finally:
        if conn:
            conn.close()


def get_all_leads(organization_id: int) -> List[Dict]: # Added organization_id
    """Fetches all leads for a SPECIFIC organization."""
    leads = []
    conn = None
    # Select columns relevant to API response (e.g., LeadResponse schema)
    sql = """
        SELECT id, name, email, company, title, source, linkedin_profile, company_size,
               industry, location, matched, reason, crm_status, appointment_confirmed, created_at
        FROM leads
        WHERE organization_id = ?
        ORDER BY created_at DESC, id DESC
    """
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row # Return dict-like rows
        cursor = conn.cursor()
        cursor.execute(sql, (organization_id,)) # Filter by organization_id
        results = cursor.fetchall()
        for row in results:
            leads.append(dict(row))
    except sqlite3.Error as e:
        print(f"DATABASE ERROR fetching leads for org {organization_id}: {e}")
    finally:
        if conn:
            conn.close()
    return leads
