"""Agent Orchestrator — Coordinates multi-agent pipeline for AeroMind.

Wires together the Mission Planner, Task Allocator, Safety Agent,
and Monitoring Agent into a cohesive workflow. Manages the agent
lifecycle and decision recording.
"""

from __future__ import annotations

import logging
from typing import Any

from packages.agent_core.allocator_agent import TaskAllocatorAgent
from packages.agent_core.monitoring_agent import MonitoringAgent
from packages.agent_core.planner_agent import MissionPlannerAgent
from packages.agent_core.safety_agent import SafetyAgent
from packages.schemas.aeromind_schemas.agents import AgentDecision

logger = logging.getLogger("aeromind.agent.orchestrator")


class AgentOrchestrator:
    """Coordinates all agents in the AeroMind system.

    Provides a unified interface for the backend to interact with
    the agent subsystem. Manages agent initialization, tool binding,
    and decision recording.
    """

    def __init__(
        self,
        llm_config: dict[str, str] | None = None,
        safety_engine: Any = None,
    ) -> None:
        self.planner = MissionPlannerAgent(llm_config)
        self.allocator = TaskAllocatorAgent(llm_config)
        self.safety = SafetyAgent(safety_engine) if safety_engine else None
        self.monitor = MonitoringAgent()
        self._decisions: list[AgentDecision] = []

    def record_decision(self, decision: AgentDecision) -> None:
        """Record an agent decision for explainability."""
        self._decisions.append(decision)
        # Keep last 500 decisions
        if len(self._decisions) > 500:
            self._decisions = self._decisions[-250:]

    def get_decisions(
        self,
        mission_id: str | None = None,
        agent_type: str | None = None,
        limit: int = 50,
    ) -> list[AgentDecision]:
        """Query recorded agent decisions."""
        decisions = self._decisions
        if mission_id:
            decisions = [d for d in decisions if d.mission_id == mission_id]
        if agent_type:
            decisions = [d for d in decisions if d.agent_type.value == agent_type]
        return decisions[-limit:]

    @property
    def all_decisions(self) -> list[AgentDecision]:
        return self._decisions
