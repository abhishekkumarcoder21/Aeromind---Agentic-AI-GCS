"""UAV-related Pydantic schemas.

Defines the core data structures for UAV state, telemetry, commands,
and health — shared across backend, simulator, and frontend.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class UAVStatus(str, Enum):
    """Explicit UAV state machine states."""

    IDLE = "IDLE"
    ARMED = "ARMED"
    TAKEOFF = "TAKEOFF"
    ACTIVE = "ACTIVE"
    HOVERING = "HOVERING"
    RETURNING = "RETURNING"
    LANDING = "LANDING"
    LANDED = "LANDED"
    LOW_BATTERY = "LOW_BATTERY"
    EMERGENCY = "EMERGENCY"
    OFFLINE = "OFFLINE"
    FAILED = "FAILED"


# ── Valid state transitions ──
# Only these transitions are allowed. Any other is rejected.
VALID_STATE_TRANSITIONS: dict[UAVStatus, set[UAVStatus]] = {
    UAVStatus.IDLE: {UAVStatus.ARMED, UAVStatus.OFFLINE, UAVStatus.FAILED},
    UAVStatus.ARMED: {UAVStatus.TAKEOFF, UAVStatus.IDLE, UAVStatus.EMERGENCY, UAVStatus.OFFLINE, UAVStatus.FAILED},
    UAVStatus.TAKEOFF: {UAVStatus.ACTIVE, UAVStatus.HOVERING, UAVStatus.EMERGENCY, UAVStatus.OFFLINE, UAVStatus.FAILED},
    UAVStatus.ACTIVE: {
        UAVStatus.HOVERING,
        UAVStatus.RETURNING,
        UAVStatus.LOW_BATTERY,
        UAVStatus.EMERGENCY,
        UAVStatus.OFFLINE,
        UAVStatus.FAILED,
    },
    UAVStatus.HOVERING: {
        UAVStatus.ACTIVE,
        UAVStatus.RETURNING,
        UAVStatus.LANDING,
        UAVStatus.LOW_BATTERY,
        UAVStatus.EMERGENCY,
        UAVStatus.OFFLINE,
        UAVStatus.FAILED,
    },
    UAVStatus.RETURNING: {
        UAVStatus.HOVERING,
        UAVStatus.LANDING,
        UAVStatus.EMERGENCY,
        UAVStatus.OFFLINE,
        UAVStatus.FAILED,
    },
    UAVStatus.LANDING: {UAVStatus.LANDED, UAVStatus.EMERGENCY, UAVStatus.OFFLINE, UAVStatus.FAILED},
    UAVStatus.LANDED: {UAVStatus.IDLE, UAVStatus.OFFLINE, UAVStatus.FAILED},
    UAVStatus.LOW_BATTERY: {UAVStatus.RETURNING, UAVStatus.EMERGENCY, UAVStatus.LANDING, UAVStatus.OFFLINE, UAVStatus.FAILED},
    UAVStatus.EMERGENCY: {UAVStatus.LANDING, UAVStatus.OFFLINE, UAVStatus.FAILED},
    UAVStatus.OFFLINE: {UAVStatus.IDLE, UAVStatus.FAILED},
    UAVStatus.FAILED: {UAVStatus.IDLE},  # only manual reset
}


def is_valid_transition(from_status: UAVStatus, to_status: UAVStatus) -> bool:
    """Check if a state transition is allowed."""
    if from_status == to_status:
        return True
    return to_status in VALID_STATE_TRANSITIONS.get(from_status, set())


class UAVPosition(BaseModel):
    """2D position on the simulated map (meters from origin)."""

    x: float = Field(default=0.0, description="X coordinate in meters")
    y: float = Field(default=0.0, description="Y coordinate in meters")

    def distance_to(self, other: UAVPosition) -> float:
        """Euclidean distance to another position."""
        return ((self.x - other.x) ** 2 + (self.y - other.y) ** 2) ** 0.5


class UAVHealth(BaseModel):
    """Health indicators for a UAV."""

    motors_ok: bool = True
    gps_ok: bool = True
    comms_ok: bool = True
    sensors_ok: bool = True
    battery_ok: bool = True

    @property
    def is_healthy(self) -> bool:
        return all([self.motors_ok, self.gps_ok, self.comms_ok, self.sensors_ok, self.battery_ok])


class UAVCommandType(str, Enum):
    """Commands that can be issued to a UAV."""

    ARM = "ARM"
    TAKEOFF = "TAKEOFF"
    GOTO_WAYPOINT = "GOTO_WAYPOINT"
    HOVER = "HOVER"
    LAND = "LAND"
    RETURN_TO_BASE = "RETURN_TO_BASE"
    EMERGENCY_LAND = "EMERGENCY_LAND"
    SET_SPEED = "SET_SPEED"
    EXECUTE_TASK = "EXECUTE_TASK"


class UAVCommand(BaseModel):
    """A command to be sent to a UAV through the execution engine."""

    command_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uav_id: str
    command: UAVCommandType
    parameters: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "SYSTEM"
    mission_id: str | None = None
    task_id: str | None = None


class UAVState(BaseModel):
    """Complete snapshot of a UAV's state at a moment in time."""

    id: str
    position: UAVPosition = Field(default_factory=UAVPosition)
    altitude: float = Field(default=0.0, ge=0, description="Altitude in meters")
    velocity: float = Field(default=0.0, ge=0, description="Speed in m/s")
    heading: float = Field(default=0.0, ge=0, le=360, description="Heading in degrees")
    battery: float = Field(default=100.0, ge=0, le=100, description="Battery percentage")
    temperature: float = Field(default=25.0, description="Temp in Celsius")
    gps_satellites: int = Field(default=12, ge=0, description="Visible GPS satellites")
    signal_strength: float = Field(default=-50.0, le=0, description="Signal strength in dBm")
    status: UAVStatus = UAVStatus.IDLE
    health: UAVHealth = Field(default_factory=UAVHealth)
    current_mission_id: str | None = None
    current_task_id: str | None = None
    home_position: UAVPosition = Field(default_factory=UAVPosition)
    last_heartbeat: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UAVTelemetry(BaseModel):
    """Telemetry packet transmitted from UAV to GCS."""

    uav_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    position: UAVPosition
    altitude: float
    velocity: float
    heading: float
    battery: float
    temperature: float
    gps_satellites: int
    signal_strength: float
    status: UAVStatus
    current_task_id: str | None = None

    @classmethod
    def from_state(cls, state: UAVState) -> UAVTelemetry:
        """Create a telemetry packet from a UAV state snapshot."""
        return cls(
            uav_id=state.id,
            position=state.position.model_copy(),
            altitude=state.altitude,
            velocity=state.velocity,
            heading=state.heading,
            battery=state.battery,
            temperature=state.temperature,
            gps_satellites=state.gps_satellites,
            signal_strength=state.signal_strength,
            status=state.status,
            current_task_id=state.current_task_id,
        )
