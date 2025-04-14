from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()

class Offering(BaseModel):
    title: str
    description: str
    benefits: List[str]
    price: float

offerings: List[Offering] = []

@router.post("/offerings/")
def create_offering(offering: Offering):
    offerings.append(offering)
    return {"message": "Offering created", "data": offering.model_dump()}

@router.get("/offerings/")
def get_offerings():
    return [o.model_dump() for o in offerings]

