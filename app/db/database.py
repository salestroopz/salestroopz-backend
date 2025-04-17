import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "salestroopz.db"

def get_connection():
    return sqlite3.connect(DB_PATH)

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        company TEXT,
        title TEXT,
        source TEXT,
        matched INTEGER,
        reason TEXT,
        crm_status TEXT,
        appointment_confirmed INTEGER DEFAULT 0
    )
    """)
 conn.commit()
    conn.close()

    
    def save_lead_result(lead: dict):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO leads (name, email, company, title, source, matched, reason, crm_status, appointment_confirmed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead.get("name"),
        lead.get("email"),
        lead.get("company"),
        lead.get("title"),
        lead.get("source"),
        int(lead.get("match_result", {}).get("matched", False)),
        lead.get("match_result", {}).get("reason", ""),
        lead.get("crm_status", "pending"),
        int(lead.get("appointment_confirmed", False))
    ))

   
    conn.commit()
    conn.close()
