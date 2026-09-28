"""Mission Service — Business logic for mission lifecycle.

Handles mission creation, planning, task allocation, execution,
monitoring, and replanning. Acts as the coordinator between
agents, safety engine, and execution engine.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from packages.schemas.aeromind_schemas.mission import (
    MissionConstraints,
    MissionPlan,
    MissionSpecification,
    MissionStatus,
    MissionTask,
    MissionTaskStatus,
    MissionType,
    SectorName,
)
from packages.schemas.aeromind_schemas.uav import UAVState, UAVStatus
from packages.schemas.aeromind_schemas.actions import ActionProposal, ActionSource, ActionType
from packages.schemas.aeromind_schemas.events import EventSeverity, EventType
from packages.schemas.aeromind_schemas.agents import AgentDecision, AgentType
from apps.backend.event_manager import EventManager
from apps.backend.execution_engine import ExecutionEngine
from services.simulator.controller import UAVController
from services.simulator.world import SimulatedWorld

logger = logging.getLogger("aeromind.mission")


class MissionService:
    """Core mission lifecycle management.

    Coordinates planning, allocation, execution, and monitoring.
    """

    def __init__(
        self,
        controller: UAVController,
        execution_engine: ExecutionEngine,
        event_manager: EventManager,
        world: SimulatedWorld,
    ) -> None:
        self.controller = controller
        self.execution = execution_engine
        self.events = event_manager
        self.world = world
        self._missions: dict[str, MissionPlan] = {}
        self._agent_decisions: list[AgentDecision] = []

    # ──────────────────────────────────────────
    # Mission creation and planning
    # ──────────────────────────────────────────

    async def create_mission(self, spec: MissionSpecification) -> MissionPlan:
        """Create a mission plan from a specification."""
        await self.events.emit(
            EventType.MISSION_CREATED,
            f"Mission '{spec.title or spec.mission_type}' created for {spec.area}",
            mission_id=spec.id,
            component="MISSION_SERVICE",
        )

        # Get sector and its waypoints
        sector = self.world.get_sector(spec.area)
        waypoints = sector.waypoints[: max(spec.required_uavs, len(sector.waypoints))]

        # Create tasks from waypoints
        tasks = []
        for i, wp in enumerate(waypoints):
            task = MissionTask(
                mission_id=spec.id,
                waypoint=wp,
                order=i,
                description=f"Inspect waypoint {wp.name} at ({wp.x:.0f}, {wp.y:.0f})",
            )
            tasks.append(task)

        plan = MissionPlan(
            mission_id=spec.id,
            specification=spec,
            tasks=tasks,
            status=MissionStatus.PLANNED,
        )

        await self.events.emit(
            EventType.MISSION_PLANNED,
            f"Mission planned with {len(tasks)} tasks",
            mission_id=spec.id,
            component="MISSION_SERVICE",
        )

        # Record planning decision
        self._agent_decisions.append(AgentDecision(
            agent_type=AgentType.MISSION_PLANNER,
            mission_id=spec.id,
            observation=f"Mission request: {spec.natural_language_input or spec.mission_type}",
            decision=f"Created {len(tasks)} inspection tasks for {spec.area}",
            reason=f"Sector {spec.area} contains {len(waypoints)} waypoints requiring inspection",
            tools_called=["get_sector_waypoints", "create_mission_plan"],
            output_summary={"task_count": len(tasks), "sector": spec.area},
        ))

        self._missions[spec.id] = plan
        return plan

    async def allocate_tasks(self, mission_id: str) -> MissionPlan | None:
        """Allocate tasks to available UAVs using weighted scoring."""
        plan = self._missions.get(mission_id)
        if not plan:
            return None

        all_states = await self.controller.get_all_states()
        available = [s for s in all_states if s.status in {UAVStatus.IDLE, UAVStatus.LANDED} and s.battery > plan.specification.constraints.minimum_battery]

        if len(available) < plan.specification.required_uavs:
            await self.events.emit(
                EventType.SYSTEM_WARNING,
                f"Only {len(available)} UAVs available, {plan.specification.required_uavs} required",
                severity=EventSeverity.WARNING,
                mission_id=mission_id,
                component="TASK_ALLOCATOR",
            )
            # Use what we have
            if not available:
                return plan

        # Weighted scoring allocation
        unassigned_tasks = [t for t in plan.tasks if t.status == MissionTaskStatus.PENDING]
        assigned_uav_ids: set[str] = set()

        for task in unassigned_tasks:
            best_uav: UAVState | None = None
            best_score = -1.0

            for uav in available:
                if uav.id in assigned_uav_ids and len(available) > len(unassigned_tasks):
                    continue  # Prefer unique assignment when possible

                score = self._calculate_allocation_score(uav, task)
                if score > best_score:
                    best_score = score
                    best_uav = uav

            if best_uav:
                task.uav_id = best_uav.id
                task.status = MissionTaskStatus.ASSIGNED
                task.assigned_at = datetime.now(timezone.utc)
                task.assignment_reason = (
                    f"Score: {best_score:.2f} — "
                    f"distance: {self._distance(best_uav, task):.0f}m, "
                    f"battery: {best_uav.battery:.0f}%"
                )
                assigned_uav_ids.add(best_uav.id)

        plan.assigned_uav_ids = list(assigned_uav_ids)

        await self.events.emit(
            EventType.TASK_ASSIGNED,
            f"Tasks allocated to {len(assigned_uav_ids)} UAVs",
            mission_id=mission_id,
            details={"assignments": {t.waypoint.name: t.uav_id for t in unassigned_tasks if t.uav_id}},
            component="TASK_ALLOCATOR",
        )

        # Record allocation decision
        self._agent_decisions.append(AgentDecision(
            agent_type=AgentType.TASK_ALLOCATOR,
            mission_id=mission_id,
            observation=f"{len(available)} UAVs available, {len(unassigned_tasks)} tasks to assign",
            decision=f"Assigned tasks to {len(assigned_uav_ids)} UAVs using weighted scoring",
            reason="Optimized for proximity, battery level, and workload balance",
            tools_called=["get_available_uavs", "calculate_allocation_score"],
            output_summary={
                "assignments": {t.waypoint.name: t.uav_id for t in unassigned_tasks if t.uav_id}
            },
        ))

        plan.status = MissionStatus.AWAITING_APPROVAL
        return plan

    def _calculate_allocation_score(self, uav: UAVState, task: MissionTask) -> float:
        """Weighted scoring for task assignment.

        Higher score = better candidate.
        Weights are configurable (using defaults for now).
        """
        distance_weight = 0.35
        battery_weight = 0.35
        workload_weight = 0.15
        health_weight = 0.15

        # Distance score (closer = better, normalized 0-1)
        dist = self._distance(uav, task)
        max_dist = 1000.0  # normalization constant
        distance_score = max(0, 1 - dist / max_dist)

        # Battery score (higher = better)
        battery_score = uav.battery / 100.0

        # Workload score (fewer current tasks = better)
        current_mission = self._missions.get(task.mission_id)
        current_tasks = (
            sum(
                1 for t in current_mission.tasks
                if t.uav_id == uav.id and t.status in {MissionTaskStatus.ASSIGNED, MissionTaskStatus.IN_PROGRESS}
            )
            if current_mission
            else 0
        )
        workload_score = max(0, 1 - current_tasks / 5.0)

        # Health score
        health_score = 1.0 if uav.health.is_healthy else 0.3

        return (
            distance_weight * distance_score
            + battery_weight * battery_score
            + workload_weight * workload_score
            + health_weight * health_score
        )

    def _distance(self, uav: UAVState, task: MissionTask) -> float:
        """Calculate distance from UAV to task waypoint."""
        dx = uav.position.x - task.waypoint.x
        dy = uav.position.y - task.waypoint.y
        return math.sqrt(dx * dx + dy * dy)

    # ──────────────────────────────────────────
    # Mission execution
    # ──────────────────────────────────────────

    async def start_mission(self, mission_id: str) -> MissionPlan | None:
        """Start executing a mission — arms, takes off, and sends UAVs to waypoints."""
        plan = self._missions.get(mission_id)
        if not plan:
            return None

        plan.status = MissionStatus.EXECUTING
        plan.started_at = datetime.now(timezone.utc)

        await self.events.emit(
            EventType.MISSION_STARTED,
            f"Mission execution started",
            mission_id=mission_id,
            component="EXECUTION_ENGINE",
        )

        # For each assigned UAV: arm, takeoff, goto first waypoint
        uav_tasks: dict[str, list[MissionTask]] = {}
        for task in plan.tasks:
            if task.uav_id and task.status == MissionTaskStatus.ASSIGNED:
                uav_tasks.setdefault(task.uav_id, []).append(task)

        for uav_id, tasks in uav_tasks.items():
            # Arm
            arm_action = ActionProposal(
                uav_id=uav_id,
                action=ActionType.ARM,
                reason="Mission start — arming UAV",
                source=ActionSource.EXECUTION_ENGINE,
                mission_id=mission_id,
                requires_approval=False,
            )
            await self.execution.submit_action(arm_action)

            # Takeoff
            takeoff_action = ActionProposal(
                uav_id=uav_id,
                action=ActionType.TAKEOFF,
                parameters={"altitude": plan.specification.constraints.max_altitude or 80.0},
                reason="Mission start — takeoff",
                source=ActionSource.EXECUTION_ENGINE,
                mission_id=mission_id,
                requires_approval=False,
            )
            await self.execution.submit_action(takeoff_action)

            # Navigate to first task waypoint
            first_task = sorted(tasks, key=lambda t: t.order)[0]
            first_task.status = MissionTaskStatus.IN_PROGRESS
            first_task.started_at = datetime.now(timezone.utc)

            goto_action = ActionProposal(
                uav_id=uav_id,
                action=ActionType.GOTO_WAYPOINT,
                parameters={
                    "x": first_task.waypoint.x,
                    "y": first_task.waypoint.y,
                    "altitude": first_task.waypoint.altitude,
                },
                reason=f"Navigate to waypoint {first_task.waypoint.name}",
                source=ActionSource.EXECUTION_ENGINE,
                mission_id=mission_id,
                task_id=first_task.id,
                requires_approval=False,
            )
            await self.execution.submit_action(goto_action)

        return plan

    # ──────────────────────────────────────────
    # Task management
    # ──────────────────────────────────────────

    async def complete_task(self, mission_id: str, task_id: str) -> None:
        """Mark a task as completed and advance to the next one."""
        plan = self._missions.get(mission_id)
        if not plan:
            return

        task = next((t for t in plan.tasks if t.id == task_id), None)
        if not task:
            return

        task.status = MissionTaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)

        await self.events.emit(
            EventType.TASK_COMPLETED,
            f"Task {task.waypoint.name} completed by {task.uav_id}",
            mission_id=mission_id,
            uav_id=task.uav_id,
            task_id=task_id,
            component="MISSION_SERVICE",
        )

        # Update progress
        total = len(plan.tasks)
        completed = sum(1 for t in plan.tasks if t.status == MissionTaskStatus.COMPLETED)
        plan.progress_percent = (completed / total * 100) if total > 0 else 0

        # Check if mission is complete
        if completed == total:
            plan.status = MissionStatus.COMPLETED
            plan.completed_at = datetime.now(timezone.utc)
            await self.events.emit(
                EventType.MISSION_COMPLETED,
                "Mission completed successfully",
                mission_id=mission_id,
                component="MISSION_SERVICE",
            )
            # Return all UAVs to base
            for uav_id in plan.assigned_uav_ids:
                rtb = ActionProposal(
                    uav_id=uav_id,
                    action=ActionType.RETURN_TO_BASE,
                    reason="Mission completed — returning to base",
                    source=ActionSource.EXECUTION_ENGINE,
                    mission_id=mission_id,
                    requires_approval=False,
                )
                await self.execution.submit_action(rtb)
        else:
            # Find next task for the UAV
            uav_id = task.uav_id
            if uav_id:
                next_task = next(
                    (t for t in sorted(plan.tasks, key=lambda t: t.order)
                     if t.uav_id == uav_id and t.status == MissionTaskStatus.ASSIGNED),
                    None,
                )
                if next_task:
                    next_task.status = MissionTaskStatus.IN_PROGRESS
                    next_task.started_at = datetime.now(timezone.utc)
                    goto = ActionProposal(
                        uav_id=uav_id,
                        action=ActionType.GOTO_WAYPOINT,
                        parameters={
                            "x": next_task.waypoint.x,
                            "y": next_task.waypoint.y,
                            "altitude": next_task.waypoint.altitude,
                        },
                        reason=f"Navigate to next waypoint {next_task.waypoint.name}",
                        source=ActionSource.EXECUTION_ENGINE,
                        mission_id=mission_id,
                        task_id=next_task.id,
                        requires_approval=False,
                    )
                    await self.execution.submit_action(goto)

    async def reassign_task(self, mission_id: str, task_id: str, new_uav_id: str) -> MissionTask | None:
        """Reassign a task to a different UAV (replanning)."""
        plan = self._missions.get(mission_id)
        if not plan:
            return None

        task = next((t for t in plan.tasks if t.id == task_id), None)
        if not task:
            return None

        old_uav = task.uav_id
        task.uav_id = new_uav_id
        task.status = MissionTaskStatus.REASSIGNED
        task.assigned_at = datetime.now(timezone.utc)
        task.assignment_reason = f"Reassigned from {old_uav} due to failure/recovery"

        await self.events.emit(
            EventType.TASK_REASSIGNED,
            f"Task {task.waypoint.name} reassigned from {old_uav} to {new_uav_id}",
            mission_id=mission_id,
            uav_id=new_uav_id,
            task_id=task_id,
            component="REPLANNING_AGENT",
        )

        self._agent_decisions.append(AgentDecision(
            agent_type=AgentType.REPLANNING_AGENT,
            mission_id=mission_id,
            uav_id=new_uav_id,
            task_id=task_id,
            observation=f"{old_uav} is unavailable for task {task.waypoint.name}",
            decision=f"Reassigned task to {new_uav_id}",
            reason="Original UAV failed or recalled — nearest available UAV selected",
            tools_called=["get_available_uavs", "calculate_allocation_score"],
        ))

        return task

    # ──────────────────────────────────────────
    # Queries
    # ──────────────────────────────────────────

    def get_mission(self, mission_id: str) -> MissionPlan | None:
        return self._missions.get(mission_id)

    def get_all_missions(self) -> list[MissionPlan]:
        return list(self._missions.values())

    def get_agent_decisions(self, mission_id: str | None = None) -> list[AgentDecision]:
        if mission_id:
            return [d for d in self._agent_decisions if d.mission_id == mission_id]
        return self._agent_decisions

    async def cancel_mission(self, mission_id: str) -> MissionPlan | None:
        plan = self._missions.get(mission_id)
        if not plan:
            return None
        plan.status = MissionStatus.CANCELLED
        plan.completed_at = datetime.now(timezone.utc)
        for task in plan.tasks:
            if task.status in {MissionTaskStatus.ASSIGNED, MissionTaskStatus.IN_PROGRESS}:
                task.status = MissionTaskStatus.CANCELLED
        await self.events.emit(
            EventType.MISSION_CANCELLED,
            "Mission cancelled by operator",
            mission_id=mission_id,
            component="MISSION_SERVICE",
        )
        return plan
