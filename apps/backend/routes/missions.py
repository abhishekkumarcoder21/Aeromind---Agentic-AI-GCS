"""Mission API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from packages.schemas.aeromind_schemas.mission import (
    MissionSpecification,
    MissionType,
    SectorName,
    MissionConstraints,
)

router = APIRouter()


class CreateMissionRequest(BaseModel):
    """Request body for creating a mission from natural language or structured input."""

    natural_language: str = ""
    mission_type: MissionType = MissionType.INSPECTION
    area: SectorName = SectorName.SECTOR_A
    required_uavs: int = 5
    title: str = ""
    constraints: MissionConstraints | None = None


@router.post("")
async def create_mission(request: Request, body: CreateMissionRequest):
    """Create a new mission."""
    mission_service = request.app.state.mission_service
    orchestrator = getattr(request.app.state, "agent_orchestrator", None)

    # If natural language is provided, use the planner agent for parsing
    if body.natural_language and orchestrator:
        controller = request.app.state.controller
        all_states = await controller.get_all_states()
        available_count = len([s for s in all_states if s.status.value in ("IDLE", "LANDED") and s.battery > 25])

        spec, decision = await orchestrator.planner.plan_mission(
            body.natural_language,
            available_uavs=available_count,
        )
        orchestrator.record_decision(decision)
    else:
        spec = MissionSpecification(
            mission_type=body.mission_type,
            title=body.title or f"{body.mission_type.value} — {body.area.value}",
            area=body.area,
            required_uavs=body.required_uavs,
            natural_language_input=body.natural_language,
            constraints=body.constraints or MissionConstraints(),
        )

    plan = await mission_service.create_mission(spec)
    plan = await mission_service.allocate_tasks(plan.mission_id)

    # Record allocation decision in orchestrator
    if orchestrator:
        alloc_decisions = mission_service.get_agent_decisions(plan.mission_id)
        for d in alloc_decisions:
            orchestrator.record_decision(d)

    return {"mission": plan.model_dump(mode="json") if plan else None}


@router.get("")
async def list_missions(request: Request):
    """List all missions."""
    mission_service = request.app.state.mission_service
    missions = mission_service.get_all_missions()
    return {"missions": [m.model_dump(mode="json") for m in missions]}


@router.get("/{mission_id}")
async def get_mission(request: Request, mission_id: str):
    """Get a specific mission."""
    mission_service = request.app.state.mission_service
    plan = mission_service.get_mission(mission_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Mission not found")
    return {"mission": plan.model_dump(mode="json")}


@router.post("/{mission_id}/approve")
async def approve_mission(request: Request, mission_id: str):
    """Approve a mission plan and start execution."""
    mission_service = request.app.state.mission_service
    plan = mission_service.get_mission(mission_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Mission not found")

    result = await mission_service.start_mission(mission_id)
    return {"mission": result.model_dump(mode="json") if result else None}


@router.post("/{mission_id}/cancel")
async def cancel_mission(request: Request, mission_id: str):
    """Cancel a mission."""
    mission_service = request.app.state.mission_service
    result = await mission_service.cancel_mission(mission_id)
    if not result:
        raise HTTPException(status_code=404, detail="Mission not found")
    return {"mission": result.model_dump(mode="json")}


@router.get("/{mission_id}/decisions")
async def get_mission_decisions(request: Request, mission_id: str):
    """Get agent decisions for a mission."""
    mission_service = request.app.state.mission_service
    decisions = mission_service.get_agent_decisions(mission_id)
    return {"decisions": [d.model_dump(mode="json") for d in decisions]}
