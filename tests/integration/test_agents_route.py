"""Integration tests for the agents API router."""

import pytest
import httpx
from apps.backend.main import app


@pytest.mark.asyncio
async def test_get_agents_status():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agents")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert len(data["agents"]) == 4
        agent_types = [a["type"] for a in data["agents"]]
        assert "MISSION_PLANNER" in agent_types
        assert "TASK_ALLOCATOR" in agent_types
        assert "SAFETY_AGENT" in agent_types
        assert "MONITORING_AGENT" in agent_types


@pytest.mark.asyncio
async def test_agent_plan_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        payload = {
            "natural_language": "Deploy 3 UAVs to survey Sector B perimeter",
            "available_uavs": 4,
        }
        res = await client.post("/api/agents/plan", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert "specification" in data
        assert "decision" in data
        assert data["specification"]["area"] in ("SECTOR_B", "Sector B")
        assert data["specification"]["required_uavs"] == 3
        assert data["decision"]["agent_type"] == "MISSION_PLANNER"


@pytest.mark.asyncio
async def test_agent_decisions_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/api/agents/decisions")
        assert res.status_code == 200
        data = res.json()
        assert "decisions" in data
        assert isinstance(data["decisions"], list)


@pytest.mark.asyncio
async def test_agent_assess_fleet_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/api/agents/assess")
        assert res.status_code == 200
        data = res.json()
        assert "proposals" in data
        assert "decisions" in data
        assert isinstance(data["proposals"], list)
        assert isinstance(data["decisions"], list)
