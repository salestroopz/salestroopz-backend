from fastapi import APIRouter
from app.schemas import Offering

router = APIRouter()

# In-memory store (you'll replace with a database later)
offerings = []

@router.post("/offering/")
def create_offering(offering: Offering):
    offerings.append(offering)
    return {"message": "Offering created", "offering": offering}

@router.get("/offering/")
def get_all_offerings():
    return offerings
