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
    """Creates/updates tables: organizations, users, leads, icps, offerings."""
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
        # --- 5. NEW: Offerings Table ---
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS offerings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organization_id INTEGER NOT NULL,
            name TEXT NOT NULL,                 -- e.g., "Cloud Migration Service"
            description TEXT,                   -- Detailed explanation
            key_features TEXT,                  -- Stores JSON list: '["Scalability", "Cost Savings"]'
            target_pain_points TEXT,            -- Stores JSON list: '["High IT Costs", "Slow Deployments"]'
            call_to_action TEXT,                -- e.g., "Book a free consultation"
            is_active INTEGER DEFAULT 1,        -- Boolean flag (1=Active, 0=Inactive)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- Consider trigger later
            -- Allow multiple offerings per organization
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

 ==========================================
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
Use code with caution.
Python
Step 2: Define Schemas (app/schemas.py)
Add OfferingInput and OfferingResponse Pydantic models.
# app/schemas.py
# ... (keep existing imports: BaseModel, Field, EmailStr, Optional, List, Dict, Any, Literal, Enum, datetime) ...

# ... (Keep existing schemas: User*, Token*, ManualLeadData, Lead*, ICPDefinition, WorkflowInitiateRequest, AppointmentStatus, ICPInput, ICPResponseAPI) ...


# --- === NEW SCHEMAS FOR OFFERING MANAGEMENT API === ---

class OfferingInput(BaseModel):
    """Schema for validating data when Creating/Updating an Offering via API."""
    name: str = Field(..., min_length=1, examples=["Cloud Migration Assessment"])
    description: Optional[str] = Field(None, examples=["Detailed analysis of your current infrastructure..."])
    key_features: List[str] = Field(default_factory=list, examples=[["Cost Projection", "Security Audit"]])
    target_pain_points: List[str] = Field(default_factory=list, examples=[["High AWS Bills", "Compliance Concerns"]])
    call_to_action: Optional[str] = Field(None, examples=["Schedule a 15-min discovery call"])
    is_active: bool = Field(True, description="Whether this offering is currently active")

class OfferingResponse(BaseModel):
    """Schema for returning an Offering definition from the API."""
    id: int
    organization_id: int
    name: str
    description: Optional[str] = None
    key_features: Optional[List[str]] = None # Parsed from JSON
    target_pain_points: Optional[List[str]] = None # Parsed from JSON
    call_to_action: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # Pydantic v2

# --- === END OF NEW OFFERING SCHEMAS === ---
Use code with caution.
Python
Step 3: Create API Router (app/routers/offering.py)
Create the new file app/routers/offering.py.
Add the endpoints using the schemas and DB functions.
# app/routers/offering.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

# Import project modules
from app.schemas import OfferingInput, OfferingResponse, UserPublic
from app.db import database
from app.auth.dependencies import get_current_user

# Define Router
router = APIRouter(
    prefix="/api/v1/offerings", # Plural resource name
    tags=["Offering Management"]
)

# --- POST Endpoint to create a NEW Offering ---
@router.post("/", response_model=OfferingResponse, status_code=status.HTTP_201_CREATED)
def create_new_offering(
    offering_data: OfferingInput, # Use input schema
    current_user: UserPublic = Depends(get_current_user) # Require auth
):
    """Creates a new offering for the organization."""
    print(f"API: Creating offering '{offering_data.name}' for Org ID: {current_user.organization_id}")
    # Convert Pydantic model to dict for DB function
    offering_dict = offering_data.dict()
    created_offering = database.create_offering(
        organization_id=current_user.organization_id,
        offering_data=offering_dict
    )
    if not created_offering:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create offering.")
    return created_offering


# --- GET Endpoint to list Offerings ---
@router.get("/", response_model=List[OfferingResponse])
def list_organization_offerings(
    active_only: bool = True, # Optional query parameter to filter active
    current_user: UserPublic = Depends(get_current_user) # Require auth
):
    """Lists all offerings for the current user's organization."""
    print(f"API: Listing offerings for Org ID: {current_user.organization_id} (Active only: {active_only})")
    offerings = database.get_offerings_by_organization_id(
        organization_id=current_user.organization_id,
        active_only=active_only
        )
    return offerings # FastAPI handles validation via response_model


# --- GET Endpoint for a specific Offering ---
@router.get("/{offering_id}", response_model=OfferingResponse)
def get_single_offering(
    offering_id: int,
    current_user: UserPublic = Depends(get_current_user)
):
    """Gets a specific offering by ID, ensuring it belongs to the user's organization."""
    print(f"API: Getting offering ID {offering_id} for Org ID: {current_user.organization_id}")
    offering = database.get_offering_by_id(offering_id, current_user.organization_id)
    if not offering:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found or not owned by organization.")
    return offering


# --- PUT Endpoint to update an Offering ---
@router.put("/{offering_id}", response_model=OfferingResponse)
def update_existing_offering(
    offering_id: int,
    offering_data: OfferingInput, # Use input schema for updates too
    current_user: UserPublic = Depends(get_current_user)
):
    """Updates an existing offering by ID."""
    print(f"API: Updating offering ID {offering_id} for Org ID: {current_user.organization_id}")
    updated_offering = database.update_offering(
        offering_id=offering_id,
        organization_id=current_user.organization_id,
        offering_data=offering_data.dict(exclude_unset=True) # Exclude unset fields for partial update feel
    )
    if not updated_offering:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found or failed to update.")
    return updated_offering


# --- DELETE Endpoint for an Offering ---
@router.delete("/{offering_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_single_offering(
    offering_id: int,
    current_user: UserPublic = Depends(get_current_user)
):
    """Deletes a specific offering by ID."""
    print(f"API: Deleting offering ID {offering_id} for Org ID: {current_user.organization_id}")
    deleted = database.delete_offering(offering_id, current_user.organization_id)
    if not deleted:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offering not found.")
    return None # No content on success
