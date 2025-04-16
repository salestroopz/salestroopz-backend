from tinydb import TinyDB, Query

db = TinyDB("leads_db.json")

def save_lead_result(lead: dict):
    db.insert(lead)

def get_all_leads():
    return db.all()
