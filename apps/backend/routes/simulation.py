"""Simulation control API routes — failure injection and reset."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

router = APIRouter()


class InjectFailureRequest(BaseModel):
    """Request body for failure injection."""

    failure_type: str  # LOW_BATTERY, OFFLINE, GPS_DEGRADATION, SIGNAL_LOSS, HIGH_TEMPERATURE, MOTOR_FAILURE
    value: float | None = None  # optional parameter (e.g., battery level, temperature)


@router.post("/uavs/{uav_id}/inject-failure")
async def inject_failure(request: Request, uav_id: str, body: InjectFailureRequest):
    """Inject a simulated failure into a UAV."""
    controller = request.app.state.controller

    state = await controller.get_state(uav_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"UAV {uav_id} not found")

    match body.failure_type.upper():
        case "LOW_BATTERY":
            level = body.value if body.value is not None else 18.0
            await controller.inject_battery(uav_id, level)
            return {"message": f"{uav_id} battery set to {level}%"}
        case "OFFLINE":
            await controller.inject_offline(uav_id)
            return {"message": f"{uav_id} set to OFFLINE"}
        case "GPS_DEGRADATION":
            sats = int(body.value) if body.value is not None else 2
            await controller.inject_gps_degradation(uav_id, sats)
            return {"message": f"{uav_id} GPS degraded to {sats} satellites"}
        case "SIGNAL_LOSS":
            strength = body.value if body.value is not None else -95.0
            await controller.inject_signal_loss(uav_id, strength)
            return {"message": f"{uav_id} signal set to {strength} dBm"}
        case "HIGH_TEMPERATURE":
            temp = body.value if body.value is not None else 85.0
            await controller.inject_high_temperature(uav_id, temp)
            return {"message": f"{uav_id} temperature set to {temp}°C"}
        case "MOTOR_FAILURE":
            await controller.inject_motor_failure(uav_id)
            return {"message": f"{uav_id} motor failure injected"}
        case _:
            raise HTTPException(status_code=400, detail=f"Unknown failure type: {body.failure_type}")


@router.post("/reset")
async def reset_simulation(request: Request):
    """Reset the simulation — stops all UAVs and reinitializes."""
    fleet = request.app.state.fleet
    controller = request.app.state.controller

    await fleet.stop_all()
    fleet.initialize()
    controller.register_fleet(fleet.uavs)
    await fleet.start_all(tick_interval=0.5)

    return {"message": "Simulation reset", "uav_count": len(fleet.uavs)}
