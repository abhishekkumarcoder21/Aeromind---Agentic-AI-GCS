"""Mission-related Pydantic schemas.

Defines mission types, specifications, tasks, sectors, waypoints,
and all the structures needed for mission planning and execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class MissionType(str, Enum):
    """Types of missions the system supports."""

    INSPECTION = "INSPECTION"
    SURVEILLANCE = "SURVEILLANCE"
    SEARCH_AND_RESCUE = "SEARCH_AND_RESCUE"
    DELIVERY = "DELIVERY"
    MAPPING = "MAPPING"
    PATROL = "PATROL"
    CUSTOM = "CUSTOM"


class MissionStatus(str, Enum):
    """Lifecycle status of a mission."""

    DRAFT = "DRAFT"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    PAUSED = "PAUSED"
    REPLANNING = "REPLANNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MissionPhase(str, Enum):
    """Phases within mission execution."""

    INITIALIZATION = "INITIALIZATION"
    ARMING = "ARMING"
    TAKEOFF = "TAKEOFF"
    TRANSIT = "TRANSIT"
    EXECUTION = "EXECUTION"
    RETURN = "RETURN"
    LANDING = "LANDING"
    COMPLETE = "COMPLETE"


class MissionTaskStatus(str, Enum):
    """Status of an individual task within a mission."""

    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INTERRUPTED = "INTERRUPTED"
    REASSIGNED = "REASSIGNED"
    CANCELLED = "CANCELLED"


class SectorName(str, Enum):
    """Named sectors in the simulated environment."""

    SECTOR_A = "SECTOR_A"
    SECTOR_B = "SECTOR_B"
    SECTOR_C = "SECTOR_C"


class Waypoint(BaseModel):
    """A waypoint in a mission plan."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    x: float
    y: float
    altitude: float = 80.0
    order: int = 0


class Sector(BaseModel):
    """A named region in the simulated environment with boundary and waypoints."""

    name: SectorName
    label: str
    center_x: float
    center_y: float
    width: float
    height: float
    waypoints: list[Waypoint] = Field(default_factory=list)

    @property
    def min_x(self) -> float:
        return self.center_x - self.width / 2

    @property
    def max_x(self) -> float:
        return self.center_x + self.width / 2

    @property
    def min_y(self) -> float:
        return self.center_y - self.height / 2

    @property
    def max_y(self) -> float:
        return self.center_y + self.height / 2

    def contains(self, x: float, y: float) -> bool:
        """Check if a point is inside this sector."""
        return self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y


class MissionConstraints(BaseModel):
    """Safety and operational constraints for a mission."""

    minimum_battery: float = Field(default=25.0, ge=0, le=100)
    minimum_gps_satellites: int = Field(default=6, ge=0)
    minimum_signal_strength: float = Field(default=-80.0, le=0)
    minimum_separation_meters: float = Field(default=50.0, ge=0)
    max_altitude: float = Field(default=120.0, ge=0)
    max_speed: float = Field(default=20.0, ge=0)
    geofence_enabled: bool = True


class MissionSpecification(BaseModel):
    """Structured mission specification produced by the Mission Planner Agent."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mission_type: MissionType
    title: str = ""
    description: str = ""
    area: SectorName
    required_uavs: int = Field(ge=1, le=20)
    constraints: MissionConstraints = Field(default_factory=MissionConstraints)
    priority: int = Field(default=1, ge=1, le=5)
    natural_language_input: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MissionTask(BaseModel):
    """A single task within a mission, assigned to a UAV."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str
    waypoint: Waypoint
    uav_id: str | None = None
    status: MissionTaskStatus = MissionTaskStatus.PENDING
    order: int = 0
    description: str = ""
    assigned_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    assignment_reason: str = ""


class MissionPlan(BaseModel):
    """A complete mission plan with tasks, assignments, and approval status."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    mission_id: str
    specification: MissionSpecification
    tasks: list[MissionTask] = Field(default_factory=list)
    status: MissionStatus = MissionStatus.PLANNED
    assigned_uav_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress_percent: float = 0.0
