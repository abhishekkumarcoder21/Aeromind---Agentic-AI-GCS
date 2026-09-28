"""Event and incident API routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("")
async def list_events(request: Request, mission_id: str | None = None, uav_id: str | None = None, limit: int = 100):
    """List mission events with optional filters."""
    event_manager = request.app.state.event_manager
    events = event_manager.get_events(mission_id=mission_id, uav_id=uav_id, limit=limit)
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.get("/incidents")
async def list_incidents(request: Request, uav_id: str | None = None, resolved: bool | None = None, limit: int = 50):
    """List safety incidents."""
    event_manager = request.app.state.event_manager
    incidents = event_manager.get_incidents(uav_id=uav_id, resolved=resolved, limit=limit)
    return {"incidents": [i.model_dump(mode="json") for i in incidents]}


@router.get("/agent-decisions")
async def list_agent_decisions(request: Request, mission_id: str | None = None):
    """List agent decisions for explainability."""
    mission_service = request.app.state.mission_service
    decisions = list(mission_service.get_agent_decisions(mission_id))

    # Also pull from agent orchestrator (safety agent decisions, etc.)
    orchestrator = getattr(request.app.state, "agent_orchestrator", None)
    if orchestrator:
        orch_decisions = orchestrator.get_decisions(mission_id=mission_id)
        decisions.extend(orch_decisions)

    # Sort by timestamp
    decisions.sort(key=lambda d: d.timestamp)

    return {"decisions": [d.model_dump(mode="json") for d in decisions]}

