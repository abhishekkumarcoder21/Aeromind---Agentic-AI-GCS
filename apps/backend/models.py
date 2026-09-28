"""SQLAlchemy ORM models for AeroMind.

Defines the persistent data model: UAVs, Missions, Tasks, Telemetry,
Events, Incidents, Agent Decisions, Action Proposals, and Approvals.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.backend.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class UAVModel(Base):
    """Persistent UAV record."""

    __tablename__ = "uavs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    uav_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    home_x: Mapped[float] = mapped_column(Float, default=0.0)
    home_y: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="IDLE")
    battery: Mapped[float] = mapped_column(Float, default=100.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    # Relationships
    tasks: Mapped[list["MissionTaskModel"]] = relationship(back_populates="uav", foreign_keys="MissionTaskModel.uav_db_id")
    telemetry_snapshots: Mapped[list["TelemetrySnapshotModel"]] = relationship(back_populates="uav")
    incidents: Mapped[list["IncidentModel"]] = relationship(back_populates="uav")


class MissionModel(Base):
    """Persistent mission record."""

    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    mission_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    area: Mapped[str] = mapped_column(String(20), nullable=False)
    required_uavs: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    natural_language_input: Mapped[str] = mapped_column(Text, default="")
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tasks: Mapped[list["MissionTaskModel"]] = relationship(back_populates="mission", cascade="all, delete-orphan")
    events: Mapped[list["MissionEventModel"]] = relationship(back_populates="mission", cascade="all, delete-orphan")
    agent_decisions: Mapped[list["AgentDecisionModel"]] = relationship(back_populates="mission")


class MissionTaskModel(Base):
    """A task within a mission."""

    __tablename__ = "mission_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    mission_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=False)
    uav_db_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("uavs.id"), nullable=True)
    uav_id_str: Mapped[str | None] = mapped_column(String(20), nullable=True)
    waypoint_name: Mapped[str] = mapped_column(String(20), default="")
    waypoint_x: Mapped[float] = mapped_column(Float, default=0.0)
    waypoint_y: Mapped[float] = mapped_column(Float, default=0.0)
    waypoint_altitude: Mapped[float] = mapped_column(Float, default=80.0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    assignment_reason: Mapped[str] = mapped_column(Text, default="")
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    mission: Mapped["MissionModel"] = relationship(back_populates="tasks")
    uav: Mapped["UAVModel | None"] = relationship(back_populates="tasks", foreign_keys=[uav_db_id])


class TelemetrySnapshotModel(Base):
    """Sampled telemetry snapshot for persistence."""

    __tablename__ = "telemetry_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    uav_db_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uavs.id"), nullable=False)
    uav_id_str: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    position_x: Mapped[float] = mapped_column(Float)
    position_y: Mapped[float] = mapped_column(Float)
    altitude: Mapped[float] = mapped_column(Float)
    velocity: Mapped[float] = mapped_column(Float)
    heading: Mapped[float] = mapped_column(Float)
    battery: Mapped[float] = mapped_column(Float)
    temperature: Mapped[float] = mapped_column(Float)
    gps_satellites: Mapped[int] = mapped_column(Integer)
    signal_strength: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))
    current_task_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    # Relationships
    uav: Mapped["UAVModel"] = relationship(back_populates="telemetry_snapshots")

    __table_args__ = (
        Index("ix_telemetry_uav_time", "uav_id_str", "timestamp"),
    )


class MissionEventModel(Base):
    """An event in the mission timeline."""

    __tablename__ = "mission_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=True)
    uav_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    component: Mapped[str] = mapped_column(String(40), default="SYSTEM")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    # Relationships
    mission: Mapped["MissionModel | None"] = relationship(back_populates="events")


class IncidentModel(Base):
    """A safety incident."""

    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    incident_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    uav_db_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("uavs.id"), nullable=False)
    uav_id_str: Mapped[str] = mapped_column(String(20), nullable=False)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    uav: Mapped["UAVModel"] = relationship(back_populates="incidents")


class AgentDecisionModel(Base):
    """Record of an agent's decision for explainability."""

    __tablename__ = "agent_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    agent_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    mission_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("missions.id"), nullable=True)
    uav_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    observation: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    tools_called: Mapped[list] = mapped_column(JSON, default=list)
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    output_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    validation_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    # Relationships
    mission: Mapped["MissionModel | None"] = relationship(back_populates="agent_decisions")


class ActionProposalModel(Base):
    """Persistent action proposal record."""

    __tablename__ = "action_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    uav_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    mission_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(30), default="PROPOSED", index=True)
    validation_errors: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(20), nullable=True)
