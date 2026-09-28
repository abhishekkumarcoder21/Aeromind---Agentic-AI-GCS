"""Safety Agent — Monitors fleet for safety violations and recommends corrective actions.

Operates independently of LLM — all safety decisions are deterministic.
The agent wraps the SafetyEngine checks and translates incidents into
action proposals (return-to-base, emergency land, etc.).
"""

from __future__ import annotations

import logging
from typing import Any

from packages.schemas.aeromind_schemas.actions import (
    ActionProposal,
    ActionSource,
    ActionType,
)
from packages.schemas.aeromind_schemas.agents import AgentDecision, AgentType
from packages.schemas.aeromind_schemas.events import EventSeverity, Incident, IncidentType
from packages.schemas.aeromind_schemas.uav import UAVState, UAVStatus

logger = logging.getLogger("aeromind.agent.safety")


class SafetyAgent:
    """Agent that monitors UAV fleet for safety violations.

    All safety decisions are deterministic — no LLM involvement.
    This agent translates detected safety incidents into actionable
    proposals that flow through the standard approval pipeline.
    """

    def __init__(self, safety_engine: Any) -> None:
        self.safety = safety_engine

    async def assess_fleet(
        self, all_states: list[UAVState]
    ) -> tuple[list[ActionProposal], list[AgentDecision]]:
        """Assess the entire fleet and generate safety action proposals.

        Returns (list of action proposals, list of agent decisions).
        """
        proposals: list[ActionProposal] = []
        decisions: list[AgentDecision] = []

        for state in all_states:
            # Skip UAVs already in safe states
            if state.status in {
                UAVStatus.IDLE, UAVStatus.LANDED, UAVStatus.OFFLINE, UAVStatus.FAILED
            }:
                continue

            incidents = self.safety.check_uav_state(state)
            for incident in incidents:
                proposal, decision = self._incident_to_proposal(state, incident)
                if proposal:
                    proposals.append(proposal)
                    decisions.append(decision)

        # Check separation between all active UAVs
        for state in all_states:
            if state.status in {
                UAVStatus.IDLE, UAVStatus.LANDED, UAVStatus.OFFLINE, UAVStatus.FAILED
            }:
                continue
            sep_incident = self.safety.check_separation(
                state.position, state.id, all_states
            )
            if sep_incident:
                proposal = ActionProposal(
                    uav_id=state.id,
                    action=ActionType.HOVER,
                    parameters={},
                    reason=f"Collision risk: {sep_incident.message}",
                    source=ActionSource.SAFETY_AGENT,
                    requires_approval=False,
                )
                proposals.append(proposal)
                decisions.append(AgentDecision(
                    agent_type=AgentType.SAFETY_AGENT,
                    uav_id=state.id,
                    observation=sep_incident.message,
                    decision=f"HOVER {state.id} to avoid collision",
                    reason="Minimum separation violated — halting movement",
                    tools_called=["check_separation"],
                    confidence=1.0,
                ))

        return proposals, decisions

    def _incident_to_proposal(
        self, state: UAVState, incident: Incident
    ) -> tuple[ActionProposal | None, AgentDecision]:
        """Convert a safety incident into an action proposal."""

        action: ActionType | None = None
        reason = incident.message
        requires_approval = True

        match incident.incident_type:
            case IncidentType.CRITICAL_BATTERY:
                action = ActionType.EMERGENCY_LAND
                reason = f"CRITICAL: {state.id} battery at {state.battery:.1f}% — emergency landing"
                requires_approval = True

            case IncidentType.LOW_BATTERY:
                action = ActionType.RETURN_TO_BASE
                reason = f"{state.id} battery low at {state.battery:.1f}% — returning to base"
                requires_approval = True

            case IncidentType.MOTOR_FAILURE:
                action = ActionType.EMERGENCY_LAND
                reason = f"CRITICAL: {state.id} motor failure — emergency landing"
                requires_approval = False  # Safety override

            case IncidentType.COMMUNICATION_LOSS:
                action = ActionType.RETURN_TO_BASE
                reason = f"{state.id} communication degraded — returning to base"
                requires_approval = True

            case IncidentType.GPS_DEGRADATION:
                # Warning only — no immediate action needed unless severe
                if state.gps_satellites < 4:
                    action = ActionType.HOVER
                    reason = f"{state.id} severe GPS degradation ({state.gps_satellites} sats) — hovering"
                    requires_approval = False

            case IncidentType.HIGH_TEMPERATURE:
                if state.temperature > 85.0:
                    action = ActionType.RETURN_TO_BASE
                    reason = f"{state.id} temperature critical at {state.temperature:.1f}°C — returning"
                    requires_approval = True

            case _:
                pass

        decision = AgentDecision(
            agent_type=AgentType.SAFETY_AGENT,
            uav_id=state.id,
            observation=f"Detected {incident.incident_type.value}: {incident.message}",
            decision=(
                f"Recommend {action.value if action else 'MONITORING'} for {state.id}"
            ),
            reason=reason,
            tools_called=["check_uav_state", "check_battery", "check_health"],
            input_summary={
                "uav_id": state.id,
                "status": state.status.value,
                "battery": round(state.battery, 1),
                "incident_type": incident.incident_type.value,
            },
            output_summary={
                "action": action.value if action else "NONE",
                "severity": incident.severity.value,
                "requires_approval": requires_approval,
            },
            confidence=1.0,  # Safety decisions are always deterministic
        )

        if action:
            proposal = ActionProposal(
                uav_id=state.id,
                action=action,
                parameters={},
                reason=reason,
                source=ActionSource.SAFETY_AGENT,
                mission_id=state.current_mission_id,
                task_id=state.current_task_id,
                requires_approval=requires_approval,
            )
            return proposal, decision

        return None, decision
