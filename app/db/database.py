import sqlite3
from pathlib import Path

# Define the path to the database file relative to this script's location
DB_PATH = Path(__file__).parent / "salestroopz.db"

def get_connection():
    """Establishes and returns a connection to the SQLite database."""
    # Use check_same_thread=False if accessed from different threads (like in a web app)
    # For simple scripts, it might not be necessary, but good practice for web apps.
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def initialize_db():
    """Creates the 'leads' table if it doesn't already exist."""
    conn = None  # Initialize conn to None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Use TEXT for boolean-like values if storing text 'True'/'False'
        # Use INTEGER (0 or 1) if storing integer representation of boolean
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE, -- Added UNIQUE constraint to email
            company TEXT,
            title TEXT,
            source TEXT,
            matched INTEGER DEFAULT 0, -- Store as 0 (False) or 1 (True)
            reason TEXT,
            crm_status TEXT DEFAULT 'pending',
            appointment_confirmed INTEGER DEFAULT 0 -- Store as 0 (False) or 1 (True)
        )
        """)
        # Indentation fixed: commit belongs inside the function block
        conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        # Indentation fixed: close belongs inside the function block
        # Make sure connection exists before closing
        if conn:
            conn.close()

def save_lead_result(lead: dict):
    """Saves or updates a lead result in the database."""
    conn = None # Initialize conn to None
    required_fields = ["name", "email"] # Example required fields
    if not all(lead.get(field) for field in required_fields):
        print(f"Skipping lead due to missing required fields: {lead.get('email') or lead.get('name')}")
        return # Don't proceed if essential info is missing

    sql_upsert = """
        INSERT INTO leads (name, email, company, title, source, matched, reason, crm_status, appointment_confirmed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            name=excluded.name,
            company=excluded.company,
            title=excluded.title,
            source=excluded.source,
            matched=excluded.matched,
            reason=excluded.reason,
            crm_status=excluded.crm_status,
            appointment_confirmed=excluded.appointment_confirmed;
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Prepare data, ensuring defaults and correct types
        name = lead.get("name", "")
        email = lead.get("email", "")
        company = lead.get("company", "")
        title = lead.get("title", "")
        source = lead.get("source", "unknown")
        # Safely access nested dictionary 'match_result'
        match_result_dict = lead.get("match_result", {}) # Default to empty dict if 'match_result' is missing
        matched = int(match_result_dict.get("matched", False)) # Default to False if 'matched' is missing
        reason = match_result_dict.get("reason", "") # Default to empty string if 'reason' is missing
        crm_status = lead.get("crm_status", "pending")
        appointment_confirmed = int(lead.get("appointment_confirmed", False))

        cursor.execute(sql_upsert, (
            name,
            email,
            company,
            title,
            source,
            matched,
            reason,
            crm_status,
            appointment_confirmed
        ))

        # Indentation fixed: commit belongs inside the function block
        conn.commit()
        # print(f"Successfully saved/updated lead: {email}") # Optional: for logging

    except sqlite3.Error as e:
        print(f"Database error saving lead {lead.get('email', 'N/A')}: {e}")
        # Consider rolling back if necessary, although commit handles transactions
        # if conn:
        #     conn.rollback()
    except Exception as e:
        # Catch other potential errors (like accessing dict keys)
         print(f"An unexpected error occurred saving lead {lead.get('email', 'N/A')}: {e}")
    finally:
        # Indentation fixed: close belongs inside the function block
        # Make sure connection exists before closing
        if conn:
            conn.close()
