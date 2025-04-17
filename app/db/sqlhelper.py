import sqlite3
from pathlib import Path

DB_PATH = str(Path(__file__).parent.parent / "salestroopz.db")

def get_connection():
    return sqlite3.connect(DB_PATH)

def save_lead_to_db(lead: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO leads (name, email, company, title, source, match_score, matched, reason, crm_pushed, appointment_confirmed)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        lead.get("name"),
        lead.get("email"),
        lead.get("company"),
        lead.get("title"),
        lead.get("source"),
        lead.get("match_result", {}).get("score", 0.0),
        lead.get("match_result", {}).get("matched", False),
        lead.get("match_result", {}).get("reason", ""),
        False,
        False
    ))
    conn.commit()
    conn.close()

def update_appointment_status(lead_email: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE leads
        SET appointment_confirmed = ?
        WHERE email = ?
    """, (True, lead_email))
    conn.commit()
    conn.close()

def mark_crm_pushed(lead_email: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE leads
        SET crm_pushed = ?
        WHERE email = ?
    """, (True, lead_email))
    conn.commit()
    conn.close()

def get_all_leads():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leads")
    rows = cursor.fetchall()
    conn.close()
    return rows
