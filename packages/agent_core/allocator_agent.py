"""Task Allocator Agent — Assigns UAVs to mission tasks using weighted scoring.

Performs intelligent task-to-UAV matching based on proximity, battery,
health, and workload balance. Records all allocation decisions for
explainability.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from packages.schemas.aeromind_schemas.agents import AgentDecision, AgentType
from packages.schemas.aeromind_schemas.mission import MissionTask, MissionTaskStatus
from packages.schemas.aeromind_schemas.uav import UAVState, UAVStatus

logger = logging.getLogger("aeromind.agent.allocator")


class TaskAllocatorAgent:
    """Agent that assigns UAVs to mission tasks using weighted scoring.

    Scoring weights:
    - Distance (35%): Closer UAVs minimize transit time and battery consumption
    - Battery (35%): Higher battery ensures longer endurance
    - Workload (15%): Balances tasks across available UAVs
    - Health (15%): Prefers fully healthy UAVs
    """

    DISTANCE_WEIGHT = 0.35
    BATTERY_WEIGHT = 0.35
    WORKLOAD_WEIGHT = 0.15
    HEALTH_WEIGHT = 0.15
    MAX_DISTANCE_NORM = 1000.0  # normalization constant for distance scoring

    def __init__(self, llm_config: dict[str, str] | None = None) -> None:
        self.llm_config = llm_config or {}

    async def allocate(
        self,
        tasks: list[MissionTask],
        available_states: list[UAVState],
        existing_assignments: dict[str, int] | None = None,
    ) -> tuple[list[MissionTask], AgentDecision]:
        """Allocate UAVs to unassigned tasks.

        Args:
            tasks: Mission tasks to assign
            available_states: UAVs available for assignment
            existing_assignments: dict of uav_id -> current task count

        Returns:
            (updated tasks with assignments, AgentDecision record)
        """
        assignment_counts = existing_assignments or {}
        unassigned = [t for t in tasks if t.status == MissionTaskStatus.PENDING]
        assigned_map: dict[str, str] = {}  # task_id -> uav_id
        reasons: list[str] = []

        for task in unassigned:
            best_uav: UAVState | None = None
            best_score = -1.0
            best_breakdown = ""

            for uav in available_states:
                score, breakdown = self._score(uav, task, assignment_counts)
                if score > best_score:
                    best_score = score
                    best_uav = uav
                    best_breakdown = breakdown

            if best_uav:
                task.uav_id = best_uav.id
                task.status = MissionTaskStatus.ASSIGNED
                task.assigned_at = datetime.now(timezone.utc)
                task.assignment_reason = (
                    f"Score: {best_score:.3f} — {best_breakdown}"
                )
                assigned_map[task.id] = best_uav.id
                assignment_counts[best_uav.id] = assignment_counts.get(best_uav.id, 0) + 1
                reasons.append(
                    f"Task {task.waypoint.name} → {best_uav.id} "
                    f"(score={best_score:.3f}, {best_breakdown})"
                )

        decision = AgentDecision(
            agent_type=AgentType.TASK_ALLOCATOR,
            mission_id=tasks[0].mission_id if tasks else None,
            observation=(
                f"{len(available_states)} UAVs available, "
                f"{len(unassigned)} tasks to assign"
            ),
            decision=(
                f"Assigned {len(assigned_map)} tasks to "
                f"{len(set(assigned_map.values()))} unique UAVs"
            ),
            reason="\n".join(reasons) if reasons else "No tasks to assign",
            tools_called=[
                "get_available_uavs", "calculate_allocation_score", "calculate_distance"
            ],
            input_summary={
                "available_uavs": len(available_states),
                "unassigned_tasks": len(unassigned),
            },
            output_summary={
                "assignments": assigned_map,
                "total_assigned": len(assigned_map),
            },
            confidence=0.9,
        )

        return tasks, decision

    def _score(
        self,
        uav: UAVState,
        task: MissionTask,
        assignment_counts: dict[str, int],
    ) -> tuple[float, str]:
        """Calculate weighted allocation score.

        Returns (score, human-readable breakdown string).
        """
        # Distance score (closer = better)
        dx = uav.position.x - task.waypoint.x
        dy = uav.position.y - task.waypoint.y
        dist = math.sqrt(dx * dx + dy * dy)
        distance_score = max(0.0, 1.0 - dist / self.MAX_DISTANCE_NORM)

        # Battery score (higher = better)
        battery_score = uav.battery / 100.0

        # Workload score (fewer tasks = better)
        current_tasks = assignment_counts.get(uav.id, 0)
        workload_score = max(0.0, 1.0 - current_tasks / 5.0)

        # Health score
        health_score = 1.0 if uav.health.is_healthy else 0.3

        total = (
            self.DISTANCE_WEIGHT * distance_score
            + self.BATTERY_WEIGHT * battery_score
            + self.WORKLOAD_WEIGHT * workload_score
            + self.HEALTH_WEIGHT * health_score
        )

        breakdown = (
            f"dist={dist:.0f}m({distance_score:.2f}), "
            f"batt={uav.battery:.0f}%({battery_score:.2f}), "
            f"load={current_tasks}({workload_score:.2f}), "
            f"health={'OK' if uav.health.is_healthy else 'DEGRADED'}({health_score:.2f})"
        )

        return total, breakdown
