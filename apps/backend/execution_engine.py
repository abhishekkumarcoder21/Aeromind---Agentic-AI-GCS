"""Execution Engine — The ONLY component that can command UAV simulators.

Receives validated, approved actions and translates them into
UAV controller commands. Enforces the safety boundary:
LLM -> Validation -> Approval -> Execution Engine -> UAV Controller.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from packages.schemas.aeromind_schemas.actions import (
    ACTIONS_REQUIRING_APPROVAL,
    AUTO_APPROVE_ACTIONS,
    ActionProposal,
    ActionStatus,
    ActionType,
)
from packages.schemas.aeromind_schemas.events import EventSeverity, EventType
from apps.backend.event_manager import EventManager
from apps.backend.safety_engine import SafetyEngine
from services.simulator.controller import UAVController

logger = logging.getLogger("aeromind.execution")


class ExecutionEngine:
    """Translates approved actions into UAV controller commands.

    This is the single point through which all UAV commands flow.
    It enforces the invariant that only validated+approved actions execute.
    """

    def __init__(
        self,
        controller: UAVController,
        safety_engine: SafetyEngine,
        event_manager: EventManager,
    ) -> None:
        self.controller = controller
        self.safety = safety_engine
        self.events = event_manager
        self._pending_approvals: dict[str, ActionProposal] = {}

    async def submit_action(self, proposal: ActionProposal) -> ActionProposal:
        """Submit an action through the full pipeline:
        validate -> check approval -> execute or queue for approval.
        """
        # 1. Validate
        all_states = await self.controller.get_all_states()
        uav_state = None
        if proposal.uav_id:
            uav_state = await self.controller.get_state(proposal.uav_id)

        proposal = self.safety.validate_action(proposal, uav_state, all_states)

        if proposal.status == ActionStatus.REJECTED_VALIDATION:
            await self.events.emit(
                EventType.SYSTEM_WARNING,
                f"Action {proposal.action} rejected: {proposal.validation_errors}",
                severity=EventSeverity.WARNING,
                uav_id=proposal.uav_id,
                mission_id=proposal.mission_id,
                component="EXECUTION_ENGINE",
            )
            return proposal

        # 2. Check if approval is needed
        needs_approval = (
            proposal.requires_approval
            and proposal.action in ACTIONS_REQUIRING_APPROVAL
            and proposal.action not in AUTO_APPROVE_ACTIONS
        )

        if needs_approval:
            proposal.status = ActionStatus.AWAITING_APPROVAL
            self._pending_approvals[proposal.action_id] = proposal
            await self.events.emit(
                EventType.APPROVAL_REQUESTED,
                f"Approval requested: {proposal.action} for {proposal.uav_id or 'system'} — {proposal.reason}",
                severity=EventSeverity.WARNING,
                uav_id=proposal.uav_id,
                mission_id=proposal.mission_id,
                details={
                    "action_id": proposal.action_id,
                    "action": proposal.action,
                    "reason": proposal.reason,
                    "source": proposal.source,
                },
                component="EXECUTION_ENGINE",
            )
            return proposal

        # 3. Auto-approved — execute immediately
        proposal.status = ActionStatus.APPROVED
        return await self._execute(proposal)

    async def approve_action(self, action_id: str) -> ActionProposal | None:
        """Approve a pending action and execute it."""
        proposal = self._pending_approvals.pop(action_id, None)
        if not proposal:
            logger.warning(f"Action {action_id} not found in pending approvals")
            return None

        proposal.status = ActionStatus.APPROVED
        await self.events.emit(
            EventType.APPROVAL_GRANTED,
            f"Action {proposal.action} for {proposal.uav_id or 'system'} approved",
            severity=EventSeverity.INFO,
            uav_id=proposal.uav_id,
            mission_id=proposal.mission_id,
            component="EXECUTION_ENGINE",
        )
        return await self._execute(proposal)

    async def reject_action(self, action_id: str, reason: str = "") -> ActionProposal | None:
        """Reject a pending action."""
        proposal = self._pending_approvals.pop(action_id, None)
        if not proposal:
            return None

        proposal.status = ActionStatus.REJECTED
        proposal.validation_errors.append(f"Rejected by operator: {reason}")
        await self.events.emit(
            EventType.APPROVAL_REJECTED,
            f"Action {proposal.action} for {proposal.uav_id or 'system'} rejected: {reason}",
            severity=EventSeverity.INFO,
            uav_id=proposal.uav_id,
            mission_id=proposal.mission_id,
            component="EXECUTION_ENGINE",
        )
        return proposal

    def get_pending_approvals(self) -> list[ActionProposal]:
        """Return all pending approval requests."""
        return list(self._pending_approvals.values())

    async def _execute(self, proposal: ActionProposal) -> ActionProposal:
        """Execute a validated and approved action against the UAV controller."""
        proposal.status = ActionStatus.EXECUTING
        try:
            success = await self._dispatch(proposal)
            proposal.status = ActionStatus.COMPLETED if success else ActionStatus.FAILED
            if success:
                await self.events.emit(
                    EventType.SYSTEM_INFO,
                    f"Action {proposal.action} executed for {proposal.uav_id or 'system'}",
                    severity=EventSeverity.INFO,
                    uav_id=proposal.uav_id,
                    mission_id=proposal.mission_id,
                    component="EXECUTION_ENGINE",
                )
            else:
                await self.events.emit(
                    EventType.SYSTEM_ERROR,
                    f"Action {proposal.action} failed for {proposal.uav_id or 'system'}",
                    severity=EventSeverity.ERROR,
                    uav_id=proposal.uav_id,
                    mission_id=proposal.mission_id,
                    component="EXECUTION_ENGINE",
                )
        except Exception as e:
            proposal.status = ActionStatus.FAILED
            proposal.validation_errors.append(str(e))
            logger.exception(f"Execution error for {proposal.action_id}")
        return proposal

    async def _dispatch(self, proposal: ActionProposal) -> bool:
        """Dispatch a specific action to the UAV controller."""
        uav_id = proposal.uav_id
        if not uav_id and proposal.action not in {ActionType.CANCEL_MISSION, ActionType.START_MISSION}:
            return False

        match proposal.action:
            case ActionType.ARM:
                return await self.controller.arm(uav_id)
            case ActionType.TAKEOFF:
                alt = proposal.parameters.get("altitude")
                return await self.controller.takeoff(uav_id, alt)
            case ActionType.GOTO_WAYPOINT:
                x = proposal.parameters["x"]
                y = proposal.parameters["y"]
                alt = proposal.parameters.get("altitude")
                return await self.controller.goto_waypoint(uav_id, x, y, alt)
            case ActionType.HOVER:
                return await self.controller.hover(uav_id)
            case ActionType.LAND:
                return await self.controller.land(uav_id)
            case ActionType.RETURN_TO_BASE:
                return await self.controller.return_to_base(uav_id)
            case ActionType.EMERGENCY_LAND:
                return await self.controller.emergency_land(uav_id)
            case _:
                logger.warning(f"Unhandled action type: {proposal.action}")
                return True  # Non-UAV actions (task management) are handled at a higher level
