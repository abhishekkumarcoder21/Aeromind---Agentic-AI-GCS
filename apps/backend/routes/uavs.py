"""UAV API routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


@router.get("")
async def list_uavs(request: Request):
    """Get status of all UAVs."""
    controller = request.app.state.controller
    states = await controller.get_all_states()
    return {"uavs": [s.model_dump(mode="json") for s in states]}


@router.get("/{uav_id}")
async def get_uav(request: Request, uav_id: str):
    """Get status of a specific UAV."""
    controller = request.app.state.controller
    state = await controller.get_state(uav_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"UAV {uav_id} not found")
    return {"uav": state.model_dump(mode="json")}


@router.get("/{uav_id}/telemetry")
async def get_uav_telemetry(request: Request, uav_id: str):
    """Get current telemetry for a UAV."""
    controller = request.app.state.controller
    telemetry = await controller.get_telemetry(uav_id)
    if not telemetry:
        raise HTTPException(status_code=404, detail=f"UAV {uav_id} not found")
    return {"telemetry": telemetry.model_dump(mode="json")}
