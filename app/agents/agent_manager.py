# app/agents/agent_manager.py

from typing import List, Dict
from pydantic import BaseModel

class Agent(BaseModel):
    id: int
    name: str
    industry: str
    company_size: str
    title_keywords: List[str]

class AgentManager:
    def __init__(self):
        self.agents: Dict[int, Agent] = {}
        self.counter = 1

    def create_agent(self, name: str, industry: str, company_size: str, title_keywords: List[str]) -> Agent:
        agent = Agent(
            id=self.counter,
            name=name,
            industry=industry,
            company_size=company_size,
            title_keywords=title_keywords
        )
        self.agents[self.counter] = agent
        self.counter += 1
        return agent

    def list_agents(self) -> List[Agent]:
        return list(self.agents.values())

    def get_agent(self, agent_id: int) -> Agent:
        return self.agents.get(agent_id)

agent_manager = AgentManager()
