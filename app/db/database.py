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
