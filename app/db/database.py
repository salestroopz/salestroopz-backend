# app/db/database.py

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Any # Added Any for update data flexibility

# --- Import Settings ---
try:
    from app.utils.config import settings
    print("Successfully imported settings in database.py")
except ImportError:
    print("Warning: Could not import settings from app.utils.config. Using default DB path.")
    settings = None

# --- Determine Database Path ---
# (Keep the logic from the previous step to determine DB_PATH from settings or fallback)
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


# --- Database Initialization (Multi-Tenant) ---
def initialize_db():
    """Creates organizations, users, and tenant-aware leads tables if they don't exist."""
    print("Initializing database schema...")
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # 1. Organizations Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE, -- Added COLLATE NOCASE for case-insensitive unique names
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print(" -> Organizations table checked/created.")
        # 2. Users Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE, -- Added COLLATE NOCASE for case-insensitive unique emails
            hashed_password TEXT NOT NULL,
            organization_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE -- Added ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_email ON users (email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_organization ON users (organization_id)") # Index for get by org
        print(" -> Users table checked/created.")
        # 3. Leads Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            name TEXT,
            email TEXT NOT NULL COLLATE NOCASE, -- Added COLLATE NOCASE
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
            UNIQUE (organization_id, email), -- Case-insensitive handled by column COLLATE
            FOREIGN KEY (organization_id) REFERENCES organizations (id) ON DELETE CASCADE -- Added ON DELETE CASCADE
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_organization ON leads (organization_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_lead_org_email ON leads (organization_id, email)")
        print(" -> Leads table checked/created/modified for multi-tenancy.")

        conn.commit()
        print("Database initialization sequence complete.")
    except sqlite3.Error as e:
        print(f"DATABASE ERROR during initialization: {e}")
    finally:
        if conn: conn.close()

# ==========================================
# ORGANIZATION CRUD OPERATIONS
# ==========================================

def create_organization(name: str) -> Optional[Dict]:
    """Creates a new organization and returns its data, or None on failure."""
    sql = "INSERT INTO organizations (name) VALUES (?)"
    conn = None
    org_data = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (name,))
        conn.commit()
        org_id = cursor.lastrowid
        print(f"Created organization '{name}' with ID: {org_id}")
        org_data = get_organization_by_id(org_id) # Fetch the created org data
    except sqlite3.IntegrityError:
        print(f"Organization name '{name}' already exists.")
        org_data = get_organization_by_name(name) # Return existing org data instead
    except sqlite3.Error as e:
        print(f"Database error creating organization '{name}': {e}")
    finally:
        if conn: conn.close()
    return org_data

def get_organization_by_id(organization_id: int) -> Optional[Dict]:
    """Fetches an organization by its ID."""
    sql = "SELECT * FROM organizations WHERE id = ?"
    conn = None
    org_data = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (organization_id,))
        result = cursor.fetchone()
        if result: org_data = dict(result)
    except sqlite3.Error as e:
        print(f"Database error getting organization by ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return org_data

def get_organization_by_name(name: str) -> Optional[Dict]:
    """Fetches an organization by its name (case-insensitive)."""
    sql = "SELECT * FROM organizations WHERE name = ?"
    conn = None
    org_data = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (name,)) # Assumes COLLATE NOCASE on the column
        result = cursor.fetchone()
        if result: org_data = dict(result)
    except sqlite3.Error as e:
        print(f"Database error getting organization by name '{name}': {e}")
    finally:
        if conn: conn.close()
    return org_data

def get_all_organizations() -> List[Dict]:
    """Fetches all organizations (likely for admin purposes)."""
    sql = "SELECT * FROM organizations ORDER BY name"
    conn = None
    orgs = []
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql)
        results = cursor.fetchall()
        for row in results: orgs.append(dict(row))
    except sqlite3.Error as e:
        print(f"Database error getting all organizations: {e}")
    finally:
        if conn: conn.close()
    return orgs

# Note: Update/Delete for organizations might need careful handling due to relationships
# def update_organization(...)
# def delete_organization(...)

# ==========================================
# USER CRUD OPERATIONS
# ==========================================

def create_user(email: str, hashed_password: str, organization_id: int) -> Optional[Dict]:
    """Creates a new user, returns user data (incl org name) or None."""
    sql = "INSERT INTO users (email, hashed_password, organization_id) VALUES (?, ?, ?)"
    conn = None
    user_data = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (email, hashed_password, organization_id))
        conn.commit()
        user_id = cursor.lastrowid
        print(f"Created user '{email}' (ID: {user_id}) for org ID {organization_id}")
        user_data = get_user_by_id(user_id) # Use get_user_by_id to include org name
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: users.email" in str(e):
            print(f"User email '{email}' already exists.")
        elif "FOREIGN KEY constraint failed" in str(e):
             print(f"Organization with ID {organization_id} does not exist.")
        else:
            print(f"Database integrity error creating user '{email}': {e}")
    except sqlite3.Error as e:
        print(f"Database error creating user '{email}': {e}")
    finally:
        if conn: conn.close()
    return user_data

def get_user_by_id(user_id: int) -> Optional[Dict]:
    """Fetches a user by ID, including organization name."""
    sql = """
        SELECT u.id, u.email, u.hashed_password, u.organization_id, o.name as organization_name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.id = ?
    """
    user = None
    conn = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (user_id,))
        result = cursor.fetchone()
        if result: user = dict(result)
    except sqlite3.Error as e:
        print(f"Database error getting user by ID {user_id}: {e}")
    finally:
        if conn: conn.close()
    return user

def get_user_by_email(email: str) -> Optional[Dict]:
    """Fetches a user by email (case-insensitive), including organization name."""
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
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (email,)) # Assumes COLLATE NOCASE on users.email
        result = cursor.fetchone()
        if result: user = dict(result)
    except sqlite3.Error as e:
        print(f"Database error getting user by email '{email}': {e}")
    finally:
        if conn: conn.close()
    return user

def get_users_by_organization(organization_id: int) -> List[Dict]:
    """Fetches all users for a specific organization."""
    sql = """
        SELECT u.id, u.email, u.organization_id, o.name as organization_name
        FROM users u
        JOIN organizations o ON u.organization_id = o.id
        WHERE u.organization_id = ?
        ORDER BY u.email
    """
    users = []
    conn = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (organization_id,))
        results = cursor.fetchall()
        for row in results: users.append(dict(row))
    except sqlite3.Error as e:
        print(f"Database error getting users for org ID {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return users

# Note: Update/Delete for users might involve more logic (e.g., password update)
# def update_user(...)
# def delete_user(...)


# ==========================================
# LEAD CRUD OPERATIONS (Tenant-Aware)
# ==========================================

# save_lead_result acts as the Create/Update (Upsert) operation
def save_lead(lead_data: Dict, organization_id: int) -> Optional[Dict]:
    """
    Saves (inserts or updates) a lead for a specific organization.
    Returns the saved lead data or None on failure.
    This is essentially the full UPSERT logic.
    """
    conn = None
    saved_lead = None
    required_fields = ["email"]
    if not lead_data.get("email"):
        print(f"Skipping lead save for org {organization_id} due to missing email: {lead_data.get('name')}")
        return None

    # Columns correspond to the leads table definition
    columns = [
        "organization_id", "name", "email", "company", "title", "source",
        "linkedin_profile", "company_size", "industry", "location",
        "matched", "reason", "crm_status", "appointment_confirmed"
    ]
    sql_upsert = f"""
        INSERT INTO leads ({", ".join(columns)})
        VALUES ({", ".join(["?"] * len(columns))})
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

        # Prepare data tuple in the correct order
        match_result_dict = lead_data.get("match_result", {})
        params = (
            organization_id,
            lead_data.get("name", ""),
            lead_data.get("email"),
            lead_data.get("company", ""),
            lead_data.get("title", ""),
            lead_data.get("source", "unknown"),
            lead_data.get("linkedin_profile"),
            lead_data.get("company_size"),
            lead_data.get("industry"),
            lead_data.get("location"),
            int(match_result_dict.get("matched", lead_data.get("matched", 0))),
            match_result_dict.get("reason", lead_data.get("reason", "")),
            lead_data.get("crm_status", "pending"),
            int(lead_data.get("appointment_confirmed", 0))
        )

        cursor.execute(sql_upsert, params)
        conn.commit()
        # Fetch the possibly updated/inserted lead to return it
        saved_lead = get_lead_by_email(lead_data['email'], organization_id) # Fetch by unique key
        if saved_lead: print(f"Saved/Updated lead ID {saved_lead['id']} for org {organization_id}")

    except sqlite3.Error as e:
        print(f"DATABASE ERROR saving lead for org {organization_id}, email {lead_data.get('email')}: {e}")
    except Exception as e:
         print(f"UNEXPECTED ERROR saving lead for org {organization_id}, email {lead_data.get('email')}: {e}")
    finally:
        if conn: conn.close()
    return saved_lead # Return the dict of the saved lead or None


def get_lead_by_id(lead_id: int, organization_id: int) -> Optional[Dict]:
    """Fetches a single lead by its ID, ensuring it belongs to the organization."""
    sql = "SELECT * FROM leads WHERE id = ? AND organization_id = ?"
    conn = None
    lead_data = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (lead_id, organization_id)) # Filter by BOTH id and org_id
        result = cursor.fetchone()
        if result: lead_data = dict(result)
    except sqlite3.Error as e:
        print(f"Database error getting lead ID {lead_id} for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return lead_data

def get_lead_by_email(email: str, organization_id: int) -> Optional[Dict]:
    """Fetches a single lead by its email within a specific organization (case-insensitive)."""
    sql = "SELECT * FROM leads WHERE email = ? AND organization_id = ?"
    conn = None
    lead_data = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (email, organization_id)) # Assumes COLLATE NOCASE on email column
        result = cursor.fetchone()
        if result: lead_data = dict(result)
    except sqlite3.Error as e:
        print(f"Database error getting lead by email '{email}' for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return lead_data

def get_leads_by_organization(organization_id: int, limit: int = 100, offset: int = 0) -> List[Dict]:
    """Fetches a paginated list of leads for a specific organization."""
    leads = []
    conn = None
    sql = """
        SELECT * FROM leads
        WHERE organization_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
    """
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, (organization_id, limit, offset)) # Add limit and offset
        results = cursor.fetchall()
        for row in results:
            leads.append(dict(row))
    except sqlite3.Error as e:
        print(f"DATABASE ERROR fetching leads for org {organization_id} (limit={limit}, offset={offset}): {e}")
    finally:
        if conn: conn.close()
    return leads

def update_lead_partial(lead_id: int, organization_id: int, update_data: Dict[str, Any]) -> Optional[Dict]:
    """Partially updates a lead identified by ID and organization ID."""
    if not update_data:
        print("No update data provided.")
        return get_lead_by_id(lead_id, organization_id) # Return current data if no changes

    # Filter out keys that are not actual columns or primary/foreign keys we don't want updated this way
    allowed_columns = {
        "name", "company", "title", "source", "linkedin_profile", "company_size",
        "industry", "location", "matched", "reason", "crm_status", "appointment_confirmed"
        # Exclude: id, organization_id, email (usually not updated partially), created_at
    }
    valid_updates = {k: v for k, v in update_data.items() if k in allowed_columns}

    if not valid_updates:
        print("No valid columns provided for update.")
        return get_lead_by_id(lead_id, organization_id)

    set_clause = ", ".join([f"{key} = ?" for key in valid_updates.keys()])
    sql = f"UPDATE leads SET {set_clause} WHERE id = ? AND organization_id = ?"
    params = list(valid_updates.values()) + [lead_id, organization_id]

    conn = None
    success = False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        if cursor.rowcount > 0: # Check if any row was actually updated
             print(f"Partially updated lead ID {lead_id} for org {organization_id}.")
             success = True
        else:
             print(f"Lead ID {lead_id} not found or no changes applied for org {organization_id}.")

    except sqlite3.Error as e:
        print(f"Database error partially updating lead ID {lead_id} for org {organization_id}: {e}")
    finally:
        if conn: conn.close()

    # Return the updated lead data if successful
    return get_lead_by_id(lead_id, organization_id) if success else None


def delete_lead(lead_id: int, organization_id: int) -> bool:
    """Deletes a lead by ID, ensuring it belongs to the organization."""
    sql = "DELETE FROM leads WHERE id = ? AND organization_id = ?"
    conn = None
    success = False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, (lead_id, organization_id)) # Filter by BOTH id and org_id
        conn.commit()
        if cursor.rowcount > 0: # Check if a row was actually deleted
            print(f"Deleted lead ID {lead_id} for org {organization_id}.")
            success = True
        else:
            print(f"Lead ID {lead_id} not found for org {organization_id}.")
    except sqlite3.Error as e:
        print(f"Database error deleting lead ID {lead_id} for org {organization_id}: {e}")
    finally:
        if conn: conn.close()
    return success

# --- Alias existing functions if desired for clarity ---
# get_all_leads_for_org = get_leads_by_organization
# save_or_update_lead = save_lead # 'save_lead' already does upsert
