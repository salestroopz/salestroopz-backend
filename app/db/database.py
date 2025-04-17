import sqlite3
from pathlib import Path

# Define the path to the database file relative to this script's location
DB_PATH = Path(__file__).parent / "salestroopz.db"

def get_connection():
    """Establishes and returns a connection to the SQLite database."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def initialize_db():
    """Creates the 'leads' table if it doesn't already exist."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            company TEXT,
            title TEXT,
            source TEXT,
            matched INTEGER DEFAULT 0,
            reason TEXT,
            crm_status TEXT DEFAULT 'pending',
            appointment_confirmed INTEGER DEFAULT 0
        )
        """)
        conn.commit()
        print("Database initialized successfully.")
    except sqlite3.Error as e:
        print(f"Database error during initialization: {e}")
    finally:
        if conn:
            conn.close()

def save_lead_result(lead: dict):
    """Saves or updates a lead result in the database."""
    conn = None
    required_fields = ["name", "email"]
    if not all(lead.get(field) for field in required_fields):
        print(f"Skipping lead due to missing required fields: {lead.get('email') or lead.get('name')}")
        return

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
        match_result_dict = lead.get("match_result", {})
        cursor.execute(sql_upsert, (
            lead.get("name", ""),
            lead.get("email", ""),
            lead.get("company", ""),
            lead.get("title", ""),
            lead.get("source", "unknown"),
            int(match_result_dict.get("matched", False)),
            match_result_dict.get("reason", ""),
            lead.get("crm_status", "pending"),
            int(lead.get("appointment_confirmed", False))
        ))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error saving lead {lead.get('email', 'N/A')}: {e}")
    except Exception as e:
         print(f"An unexpected error occurred saving lead {lead.get('email', 'N/A')}: {e}")
    finally:
        if conn:
            conn.close()

# --- ADD THIS FUNCTION ---
def get_all_leads() -> list[dict]:
    leads = []
    conn = None
    try:
        conn = get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM leads ORDER BY id DESC")
        results = cursor.fetchall()
        for row in results:
            leads.append(dict(row))
    except sqlite3.Error as e:
        print(f"Database error fetching leads: {e}")
    finally:
        # Correct indent: One level deeper than 'finally'
        if conn: # Line 111 (or wherever it is now)
            # Correct indent: One level deeper than 'if'
            conn.close()
    return leads
