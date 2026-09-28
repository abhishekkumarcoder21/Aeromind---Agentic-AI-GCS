"""Action and approval schemas.

Defines the structures for action proposals, approval requests,
and the human-in-the-loop approval workflow.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Types of actions that can be proposed."""

    ARM = "ARM"
    TAKEOFF = "TAKEOFF"
    GOTO_WAYPOINT = "GOTO_WAYPOINT"
    HOVER = "HOVER"
    LAND = "LAND"
    RETURN_TO_BASE = "RETURN_TO_BASE"
    EMERGENCY_LAND = "EMERGENCY_LAND"
    ASSIGN_TASK = "ASSIGN_TASK"
    REASSIGN_TASK = "REASSIGN_TASK"
    CANCEL_TASK = "CANCEL_TASK"
    CANCEL_MISSION = "CANCEL_MISSION"
    MODIFY_GEOFENCE = "MODIFY_GEOFENCE"
    START_MISSION = "START_MISSION"


class ActionSource(str, Enum):
    """Source of an action proposal."""

    MISSION_PLANNER = "MISSION_PLANNER"
    TASK_ALLOCATOR = "TASK_ALLOCATOR"
    SAFETY_AGENT = "SAFETY_AGENT"
    MONITORING_AGENT = "MONITORING_AGENT"
    REPLANNING_AGENT = "REPLANNING_AGENT"
    HUMAN_OPERATOR = "HUMAN_OPERATOR"
    EXECUTION_ENGINE = "EXECUTION_ENGINE"
    SYSTEM = "SYSTEM"


class ActionStatus(str, Enum):
    """Status of an action proposal."""

    PROPOSED = "PROPOSED"
    VALIDATED = "VALIDATED"
    REJECTED_VALIDATION = "REJECTED_VALIDATION"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ── Actions requiring human approval ──
ACTIONS_REQUIRING_APPROVAL: set[ActionType] = {
    ActionType.RETURN_TO_BASE,
    ActionType.EMERGENCY_LAND,
    ActionType.CANCEL_MISSION,
    ActionType.REASSIGN_TASK,
    ActionType.MODIFY_GEOFENCE,
}

# ── Low-risk actions that can auto-approve ──
AUTO_APPROVE_ACTIONS: set[ActionType] = {
    ActionType.HOVER,
    ActionType.GOTO_WAYPOINT,
    ActionType.ASSIGN_TASK,
}


class ActionProposal(BaseModel):
    """An action proposed by an agent, subject to validation and approval."""

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    uav_id: str | None = None
    action: ActionType
    parameters: dict = Field(default_factory=dict)
    reason: str
    source: ActionSource
    mission_id: str | None = None
    task_id: str | None = None
    requires_approval: bool = True
    status: ActionStatus = ActionStatus.PROPOSED
    validation_errors: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApprovalDecision(str, Enum):
    """Human operator's decision on an approval request."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalRequest(BaseModel):
    """Request sent to the human operator for approval."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action_proposal: ActionProposal
    message: str
    details: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: datetime | None = None
    decision: ApprovalDecision | None = None
    decided_by: str | None = None
