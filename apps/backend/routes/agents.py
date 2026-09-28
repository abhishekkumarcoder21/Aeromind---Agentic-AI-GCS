"""Agent API routes for querying multi-agent status, decisions, and triggering agent reasoning."""

from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()


class AgentPlanRequest(BaseModel):
    natural_language: str = Field(..., description="Natural language mission prompt")
    available_uavs: int = Field(5, description="Number of available UAVs")


@router.get("")
async def get_agent_status(request: Request):
    """Return status and configuration of all agents in the orchestrator."""
    orchestrator = getattr(request.app.state, "agent_orchestrator", None)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Agent orchestrator not initialized")

    return {
        "status": "ready",
        "agents": [
            {
                "name": "Mission Planner Agent",
                "type": "MISSION_PLANNER",
                "framework": "LangGraph / LangChain",
                "active": True,
            },
            {
                "name": "Task Allocator Agent",
                "type": "TASK_ALLOCATOR",
                "framework": "LangGraph / LangChain",
                "active": True,
            },
            {
                "name": "Safety Agent",
                "type": "SAFETY_AGENT",
                "framework": "LangGraph / Deterministic Rule Engine",
                "active": orchestrator.safety is not None,
            },
            {
                "name": "Monitoring Agent",
                "type": "MONITORING_AGENT",
                "framework": "Deterministic Anomaly Evaluator",
                "active": True,
            },
        ],
        "total_decisions_recorded": len(orchestrator.all_decisions),
    }


@router.get("/decisions")
async def list_agent_decisions(
    request: Request,
    mission_id: str | None = None,
    agent_type: str | None = None,
    limit: int = 50,
):
    """List agent decisions recorded by the orchestrator."""
    orchestrator = getattr(request.app.state, "agent_orchestrator", None)
    if not orchestrator:
        return {"decisions": []}

    decisions = orchestrator.get_decisions(mission_id=mission_id, agent_type=agent_type, limit=limit)
    return {"decisions": [d.model_dump(mode="json") for d in decisions]}


@router.post("/plan")
async def plan_mission_with_agent(request: Request, body: AgentPlanRequest):
    """Directly test or invoke the Mission Planner agent with natural language."""
    orchestrator = getattr(request.app.state, "agent_orchestrator", None)
    if not orchestrator:
        raise HTTPException(status_code=503, detail="Agent orchestrator not initialized")

    spec, decision = await orchestrator.planner.plan_mission(
        natural_language=body.natural_language,
        available_uavs=body.available_uavs,
    )
    orchestrator.record_decision(decision)

    return {
        "specification": spec.model_dump(mode="json"),
        "decision": decision.model_dump(mode="json"),
    }


@router.post("/assess")
async def assess_fleet_safety(request: Request):
    """Trigger a manual assessment of the fleet by the Safety Agent."""
    orchestrator = getattr(request.app.state, "agent_orchestrator", None)
    controller = request.app.state.controller
    if not orchestrator or not orchestrator.safety:
        raise HTTPException(status_code=503, detail="Safety agent not available")

    states = await controller.get_all_states()
    proposals, decisions = await orchestrator.safety.assess_fleet(states)
    for dec in decisions:
        orchestrator.record_decision(dec)

    return {
        "proposals": [p.model_dump(mode="json") for p in proposals],
        "decisions": [d.model_dump(mode="json") for d in decisions],
    }
