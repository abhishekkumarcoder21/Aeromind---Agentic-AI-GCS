"""Event and incident schemas.

Defines mission events, safety incidents, and the structures
for the mission timeline and incident tracking.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of events in the mission timeline."""

    MISSION_CREATED = "MISSION_CREATED"
    MISSION_PLANNED = "MISSION_PLANNED"
    MISSION_APPROVED = "MISSION_APPROVED"
    MISSION_STARTED = "MISSION_STARTED"
    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_FAILED = "MISSION_FAILED"
    MISSION_CANCELLED = "MISSION_CANCELLED"
    MISSION_PAUSED = "MISSION_PAUSED"
    MISSION_RESUMED = "MISSION_RESUMED"

    TASK_ASSIGNED = "TASK_ASSIGNED"
    TASK_STARTED = "TASK_STARTED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_REASSIGNED = "TASK_REASSIGNED"
    TASK_INTERRUPTED = "TASK_INTERRUPTED"

    UAV_ARMED = "UAV_ARMED"
    UAV_TAKEOFF = "UAV_TAKEOFF"
    UAV_ACTIVE = "UAV_ACTIVE"
    UAV_RETURNING = "UAV_RETURNING"
    UAV_LANDED = "UAV_LANDED"
    UAV_OFFLINE = "UAV_OFFLINE"
    UAV_FAILED = "UAV_FAILED"

    SAFETY_INCIDENT = "SAFETY_INCIDENT"
    APPROVAL_REQUESTED = "APPROVAL_REQUESTED"
    APPROVAL_GRANTED = "APPROVAL_GRANTED"
    APPROVAL_REJECTED = "APPROVAL_REJECTED"

    AGENT_DECISION = "AGENT_DECISION"
    REPLANNING_STARTED = "REPLANNING_STARTED"
    REPLANNING_COMPLETED = "REPLANNING_COMPLETED"

    SYSTEM_INFO = "SYSTEM_INFO"
    SYSTEM_WARNING = "SYSTEM_WARNING"
    SYSTEM_ERROR = "SYSTEM_ERROR"


class EventSeverity(str, Enum):
    """Severity levels for events."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class MissionEvent(BaseModel):
    """An event in the mission timeline."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType
    severity: EventSeverity = EventSeverity.INFO
    message: str
    mission_id: str | None = None
    uav_id: str | None = None
    task_id: str | None = None
    details: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    component: str = "SYSTEM"


class IncidentType(str, Enum):
    """Types of safety incidents."""

    LOW_BATTERY = "LOW_BATTERY"
    CRITICAL_BATTERY = "CRITICAL_BATTERY"
    UAV_OFFLINE = "UAV_OFFLINE"
    GPS_DEGRADATION = "GPS_DEGRADATION"
    COMMUNICATION_LOSS = "COMMUNICATION_LOSS"
    HIGH_TEMPERATURE = "HIGH_TEMPERATURE"
    MOTOR_FAILURE = "MOTOR_FAILURE"
    GEOFENCE_VIOLATION = "GEOFENCE_VIOLATION"
    COLLISION_RISK = "COLLISION_RISK"
    HEARTBEAT_TIMEOUT = "HEARTBEAT_TIMEOUT"
    SENSOR_FAILURE = "SENSOR_FAILURE"


class Incident(BaseModel):
    """A safety incident requiring attention or action."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_type: IncidentType
    severity: EventSeverity
    uav_id: str
    mission_id: str | None = None
    task_id: str | None = None
    message: str
    details: dict = Field(default_factory=dict)
    resolved: bool = False
    resolution: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = None
