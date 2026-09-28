"""Monitoring Agent — Continuously assesses fleet health and mission progress.

Detects anomalies, tracks task completion, and identifies trends
that could lead to safety issues.
"""

from __future__ import annotations

import logging
from typing import Any

from packages.schemas.aeromind_schemas.agents import AgentDecision, AgentType
from packages.schemas.aeromind_schemas.mission import (
    MissionPlan,
    MissionStatus,
    MissionTaskStatus,
)
from packages.schemas.aeromind_schemas.uav import UAVState, UAVStatus

logger = logging.getLogger("aeromind.agent.monitor")


class MonitoringAgent:
    """Agent that monitors fleet health and mission progress.

    Provides structured fleet assessments including:
    - Individual UAV health summaries
    - Fleet-wide statistics
    - Mission progress tracking
    - Anomaly detection
    """

    def assess_fleet(self, all_states: list[UAVState]) -> tuple[dict, AgentDecision]:
        """Generate a comprehensive fleet health assessment.

        Returns (assessment dict, AgentDecision record).
        """
        total = len(all_states)
        active = [s for s in all_states if s.status in {
            UAVStatus.ACTIVE, UAVStatus.TAKEOFF, UAVStatus.HOVERING, UAVStatus.RETURNING
        }]
        idle = [s for s in all_states if s.status in {UAVStatus.IDLE, UAVStatus.LANDED}]
        offline = [s for s in all_states if s.status in {UAVStatus.OFFLINE, UAVStatus.FAILED}]
        low_battery = [s for s in all_states if s.battery < 25]
        unhealthy = [s for s in all_states if not s.health.is_healthy]

        avg_battery = sum(s.battery for s in all_states) / total if total > 0 else 0
        min_battery = min((s.battery for s in all_states), default=0)

        # Anomaly detection
        anomalies = []
        for state in all_states:
            if state.battery < 15 and state.status not in {
                UAVStatus.IDLE, UAVStatus.LANDED, UAVStatus.OFFLINE, UAVStatus.FAILED
            }:
                anomalies.append({
                    "uav_id": state.id,
                    "type": "CRITICAL_BATTERY",
                    "message": f"{state.id} critically low battery ({state.battery:.1f}%) while {state.status.value}",
                })
            if state.temperature > 75 and state.status not in {UAVStatus.IDLE, UAVStatus.LANDED}:
                anomalies.append({
                    "uav_id": state.id,
                    "type": "HIGH_TEMPERATURE",
                    "message": f"{state.id} high temperature ({state.temperature:.1f}°C)",
                })
            if state.gps_satellites < 4 and state.health.gps_ok:
                anomalies.append({
                    "uav_id": state.id,
                    "type": "GPS_WARNING",
                    "message": f"{state.id} low GPS satellite count ({state.gps_satellites})",
                })

        assessment = {
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "fleet_summary": {
                "total": total,
                "active": len(active),
                "idle": len(idle),
                "offline": len(offline),
                "low_battery": len(low_battery),
                "unhealthy": len(unhealthy),
            },
            "battery_stats": {
                "average": round(avg_battery, 1),
                "minimum": round(min_battery, 1),
                "low_battery_uavs": [s.id for s in low_battery],
            },
            "health_status": {
                "all_healthy": len(unhealthy) == 0,
                "unhealthy_uavs": [
                    {
                        "id": s.id,
                        "motors_ok": s.health.motors_ok,
                        "gps_ok": s.health.gps_ok,
                        "comms_ok": s.health.comms_ok,
                    }
                    for s in unhealthy
                ],
            },
            "anomalies": anomalies,
            "fleet_readiness": f"{len(idle)}/{total} UAVs available",
        }

        decision = AgentDecision(
            agent_type=AgentType.MONITORING_AGENT,
            observation=f"Fleet scan: {total} UAVs, {len(active)} active, {len(anomalies)} anomalies",
            decision=(
                f"Fleet status: {len(idle)} available, {len(offline)} offline, "
                f"avg battery {avg_battery:.0f}%"
            ),
            reason=(
                f"Routine fleet assessment. "
                f"{'No anomalies detected.' if not anomalies else f'{len(anomalies)} anomalies require attention.'}"
            ),
            tools_called=["get_fleet_status", "check_fleet_safety"],
            output_summary=assessment["fleet_summary"],
            confidence=1.0,
        )

        return assessment, decision

    def assess_mission_progress(
        self, mission: MissionPlan
    ) -> tuple[dict, AgentDecision]:
        """Generate a mission progress assessment.

        Returns (progress dict, AgentDecision record).
        """
        total_tasks = len(mission.tasks)
        completed = sum(1 for t in mission.tasks if t.status == MissionTaskStatus.COMPLETED)
        in_progress = sum(1 for t in mission.tasks if t.status == MissionTaskStatus.IN_PROGRESS)
        failed = sum(1 for t in mission.tasks if t.status in {
            MissionTaskStatus.FAILED, MissionTaskStatus.INTERRUPTED
        })
        pending = sum(1 for t in mission.tasks if t.status == MissionTaskStatus.PENDING)
        assigned = sum(1 for t in mission.tasks if t.status == MissionTaskStatus.ASSIGNED)

        progress = {
            "mission_id": mission.mission_id,
            "status": mission.status.value,
            "progress_percent": round(mission.progress_percent, 1),
            "tasks": {
                "total": total_tasks,
                "completed": completed,
                "in_progress": in_progress,
                "assigned": assigned,
                "pending": pending,
                "failed": failed,
            },
            "assigned_uavs": mission.assigned_uav_ids,
            "needs_attention": failed > 0 or mission.status == MissionStatus.FAILED,
        }

        decision = AgentDecision(
            agent_type=AgentType.MONITORING_AGENT,
            mission_id=mission.mission_id,
            observation=(
                f"Mission progress: {completed}/{total_tasks} tasks complete "
                f"({mission.progress_percent:.0f}%)"
            ),
            decision=(
                f"Mission {'ON TRACK' if failed == 0 else 'NEEDS ATTENTION'}: "
                f"{completed} complete, {in_progress} in progress, {failed} failed"
            ),
            reason=(
                f"{'All tasks progressing normally.' if failed == 0 else f'{failed} task(s) failed — may require replanning.'}"
            ),
            tools_called=["get_mission_status"],
            output_summary=progress["tasks"],
            confidence=1.0,
        )

        return progress, decision
