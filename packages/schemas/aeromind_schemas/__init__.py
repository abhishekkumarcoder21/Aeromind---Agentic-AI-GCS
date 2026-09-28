"""AeroMind Shared Schemas — Pydantic models used across all services."""

from packages.schemas.aeromind_schemas.uav import (
    UAVCommand,
    UAVCommandType,
    UAVHealth,
    UAVPosition,
    UAVState,
    UAVStatus,
    UAVTelemetry,
)
from packages.schemas.aeromind_schemas.mission import (
    MissionConstraints,
    MissionPhase,
    MissionPlan,
    MissionSpecification,
    MissionStatus,
    MissionTask,
    MissionTaskStatus,
    MissionType,
    Sector,
    SectorName,
    Waypoint,
)
from packages.schemas.aeromind_schemas.actions import (
    ActionProposal,
    ActionSource,
    ActionStatus,
    ActionType,
    ApprovalDecision,
    ApprovalRequest,
)
from packages.schemas.aeromind_schemas.events import (
    EventSeverity,
    EventType,
    MissionEvent,
    IncidentType,
    Incident,
)
from packages.schemas.aeromind_schemas.agents import (
    AgentDecision,
    AgentType,
)

__all__ = [
    "UAVState", "UAVStatus", "UAVPosition", "UAVHealth", "UAVTelemetry",
    "UAVCommand", "UAVCommandType",
    "MissionType", "MissionStatus", "MissionPhase", "MissionPlan", "MissionSpecification",
    "MissionConstraints", "MissionTask", "MissionTaskStatus",
    "Sector", "SectorName", "Waypoint",
    "ActionType", "ActionSource", "ActionStatus", "ActionProposal",
    "ApprovalRequest", "ApprovalDecision",
    "EventType", "EventSeverity", "MissionEvent", "IncidentType", "Incident",
    "AgentType", "AgentDecision",
]
