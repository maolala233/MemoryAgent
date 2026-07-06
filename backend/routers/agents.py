"""Agents router: list, detail, test."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..models.schemas import AgentInfo, AgentTestRequest, AgentTestResponse
from ..services.agent_service import agent_service

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
def list_agents() -> list[AgentInfo]:
    return [AgentInfo(**a) for a in agent_service.list_agents()]


@router.get("/{agent_id}", response_model=AgentInfo)
def get_agent(agent_id: str) -> AgentInfo:
    agents = {a.get("id"): a for a in agent_service.list_agents()}
    if agent_id not in agents:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return AgentInfo(**agents[agent_id])


@router.post("/{agent_id}/test", response_model=AgentTestResponse)
async def test_agent(agent_id: str, req: AgentTestRequest) -> AgentTestResponse:
    result = await agent_service.test_agent(agent_id, req.test_prompt)
    return AgentTestResponse(
        response=result["response"],
        latency_ms=result["latency_ms"],
        status=result["status"],
    )
