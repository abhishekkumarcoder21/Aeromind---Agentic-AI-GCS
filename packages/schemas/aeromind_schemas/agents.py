"""Agent decision schemas.

Structures for recording and inspecting agent decisions,
providing explainability and traceability.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Types of agents in the system."""

    MISSION_PLANNER = "MISSION_PLANNER"
    TASK_ALLOCATOR = "TASK_ALLOCATOR"
    SAFETY_AGENT = "SAFETY_AGENT"
    MONITORING_AGENT = "MONITORING_AGENT"
    REPLANNING_AGENT = "REPLANNING_AGENT"
    ORCHESTRATOR = "ORCHESTRATOR"


class AgentDecision(BaseModel):
    """A structured record of an agent's decision for explainability."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_type: AgentType
    mission_id: str | None = None
    uav_id: str | None = None
    task_id: str | None = None
    observation: str = Field(description="What the agent observed")
    decision: str = Field(description="What the agent decided")
    reason: str = Field(description="Why this decision was made")
    tools_called: list[str] = Field(default_factory=list)
    input_summary: dict = Field(default_factory=dict)
    output_summary: dict = Field(default_factory=dict)
    validation_result: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
