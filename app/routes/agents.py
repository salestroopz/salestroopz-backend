from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from uuid import uuid4

router = APIRouter()

# In-memory DB simulation
agents_db = {}

# Pydantic model
class Agent(BaseModel):
    id: str = None
    name: str
    industry: str
    company_size: str
    title_keywords: List[str]

# Routes

@router.get("/agents", response_model=List[Agent])
def list_agents():
    return list(agents_db.values())

@router.post("/agents", response_model=Agent)
def create_agent(agent: Agent):
    agent.id = str(uuid4())
    agents_db[agent.id] = agent
    return agent

@router.get("/agents/{agent_id}", response_model=Agent)
def get_agent(agent_id: str):
    agent = agents_db.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent

@router.put("/agents/{agent_id}", response_model=Agent)
def update_agent(agent_id: str, updated_agent: Agent):
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    updated_agent.id = agent_id
    agents_db[agent_id] = updated_agent
    return updated_agent

@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str):
    if agent_id not in agents_db:
        raise HTTPException(status_code=404, detail="Agent not found")
    del agents_db[agent_id]
    return {"detail": "Agent deleted successfully"}
