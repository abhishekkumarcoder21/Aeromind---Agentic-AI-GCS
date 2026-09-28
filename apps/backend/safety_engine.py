"""Deterministic Safety Engine.

All geometric safety checks (collision avoidance, geofence, battery thresholds)
are implemented here deterministically — the LLM is NEVER used for these calculations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from packages.schemas.aeromind_schemas.uav import UAVPosition, UAVState, UAVStatus
from packages.schemas.aeromind_schemas.events import EventSeverity, IncidentType, Incident
from packages.schemas.aeromind_schemas.actions import (
    ActionProposal,
    ActionSource,
    ActionStatus,
    ActionType,
)
from services.simulator.world import GEOFENCE

logger = logging.getLogger("aeromind.safety")


@dataclass
class SafetyConfig:
    """Safety thresholds — loaded from settings."""

    min_battery_percent: float = 25.0
    critical_battery_percent: float = 15.0
    min_separation_meters: float = 50.0
    min_gps_satellites: int = 6
    min_signal_strength: float = -80.0
    max_temperature: float = 75.0
    geofence_enabled: bool = True


class SafetyEngine:
    """Deterministic safety checks.

    This engine does NOT use an LLM. It performs rule-based validation
    on UAV states, proposed movements, and mission constraints.
    """

    def __init__(self, config: SafetyConfig | None = None) -> None:
        self.config = config or SafetyConfig()

    # ──────────────────────────────────────────
    # Battery checks
    # ──────────────────────────────────────────

    def check_battery(self, state: UAVState) -> Incident | None:
        """Check if a UAV's battery is below thresholds."""
        if state.battery < self.config.critical_battery_percent:
            return Incident(
                incident_type=IncidentType.CRITICAL_BATTERY,
                severity=EventSeverity.CRITICAL,
                uav_id=state.id,
                message=f"{state.id} battery critically low at {state.battery:.1f}%",
                details={"battery": state.battery, "threshold": self.config.critical_battery_percent},
            )
        if state.battery < self.config.min_battery_percent:
            return Incident(
                incident_type=IncidentType.LOW_BATTERY,
                severity=EventSeverity.WARNING,
                uav_id=state.id,
                message=f"{state.id} battery low at {state.battery:.1f}%",
                details={"battery": state.battery, "threshold": self.config.min_battery_percent},
            )
        return None

    # ──────────────────────────────────────────
    # GPS / Signal checks
    # ──────────────────────────────────────────

    def check_gps(self, state: UAVState) -> Incident | None:
        if state.gps_satellites < self.config.min_gps_satellites:
            return Incident(
                incident_type=IncidentType.GPS_DEGRADATION,
                severity=EventSeverity.WARNING,
                uav_id=state.id,
                message=f"{state.id} GPS degraded — {state.gps_satellites} satellites",
                details={"satellites": state.gps_satellites, "min_required": self.config.min_gps_satellites},
            )
        return None

    def check_signal(self, state: UAVState) -> Incident | None:
        if state.signal_strength < self.config.min_signal_strength:
            return Incident(
                incident_type=IncidentType.COMMUNICATION_LOSS,
                severity=EventSeverity.ERROR,
                uav_id=state.id,
                message=f"{state.id} signal weak at {state.signal_strength:.0f} dBm",
                details={"signal": state.signal_strength, "min_required": self.config.min_signal_strength},
            )
        return None

    def check_temperature(self, state: UAVState) -> Incident | None:
        if state.temperature > self.config.max_temperature:
            return Incident(
                incident_type=IncidentType.HIGH_TEMPERATURE,
                severity=EventSeverity.WARNING,
                uav_id=state.id,
                message=f"{state.id} temperature high at {state.temperature:.1f}°C",
                details={"temperature": state.temperature, "max": self.config.max_temperature},
            )
        return None

    def check_health(self, state: UAVState) -> Incident | None:
        if not state.health.motors_ok:
            return Incident(
                incident_type=IncidentType.MOTOR_FAILURE,
                severity=EventSeverity.CRITICAL,
                uav_id=state.id,
                message=f"{state.id} motor failure detected",
            )
        if not state.health.comms_ok:
            return Incident(
                incident_type=IncidentType.COMMUNICATION_LOSS,
                severity=EventSeverity.ERROR,
                uav_id=state.id,
                message=f"{state.id} communication system failure",
            )
        return None

    # ──────────────────────────────────────────
    # Geofence
    # ──────────────────────────────────────────

    def check_geofence(self, x: float, y: float, altitude: float = 0.0) -> bool:
        """Returns True if position is within the geofence."""
        if not self.config.geofence_enabled:
            return True
        return (
            GEOFENCE["min_x"] <= x <= GEOFENCE["max_x"]
            and GEOFENCE["min_y"] <= y <= GEOFENCE["max_y"]
            and altitude <= GEOFENCE["max_altitude"]
        )

    def validate_movement(self, uav_id: str, target_x: float, target_y: float, altitude: float = 80.0) -> list[str]:
        """Validate a proposed movement. Returns list of violation descriptions."""
        violations = []
        if not self.check_geofence(target_x, target_y, altitude):
            violations.append(
                f"GEOFENCE_VIOLATION: Target ({target_x:.1f}, {target_y:.1f}, alt={altitude:.1f}) "
                f"is outside operational boundary"
            )
        return violations

    # ──────────────────────────────────────────
    # Collision / separation check
    # ──────────────────────────────────────────

    def check_separation(
        self,
        uav_position: UAVPosition,
        uav_id: str,
        all_states: list[UAVState],
    ) -> Incident | None:
        """Check if any other active UAV is too close."""
        for other in all_states:
            if other.id == uav_id:
                continue
            if other.status in {UAVStatus.IDLE, UAVStatus.LANDED, UAVStatus.OFFLINE, UAVStatus.FAILED}:
                continue
            dist = uav_position.distance_to(other.position)
            if dist < self.config.min_separation_meters:
                return Incident(
                    incident_type=IncidentType.COLLISION_RISK,
                    severity=EventSeverity.CRITICAL,
                    uav_id=uav_id,
                    message=f"Collision risk: {uav_id} is {dist:.1f}m from {other.id} (min: {self.config.min_separation_meters}m)",
                    details={
                        "other_uav": other.id,
                        "distance": dist,
                        "min_separation": self.config.min_separation_meters,
                    },
                )
        return None

    def check_projected_separation(
        self,
        uav_id: str,
        target: UAVPosition,
        all_states: list[UAVState],
    ) -> list[str]:
        """Check if moving to a target would violate separation with other active UAVs."""
        violations = []
        for other in all_states:
            if other.id == uav_id:
                continue
            if other.status in {UAVStatus.IDLE, UAVStatus.LANDED, UAVStatus.OFFLINE, UAVStatus.FAILED}:
                continue
            dist = target.distance_to(other.position)
            if dist < self.config.min_separation_meters:
                violations.append(
                    f"SEPARATION_VIOLATION: {uav_id} would be {dist:.1f}m from {other.id} at "
                    f"({target.x:.1f}, {target.y:.1f})"
                )
        return violations

    # ──────────────────────────────────────────
    # Full UAV state check
    # ──────────────────────────────────────────

    def check_uav_state(self, state: UAVState) -> list[Incident]:
        """Run all safety checks on a UAV state. Returns list of incidents."""
        incidents = []
        for check in [
            self.check_battery,
            self.check_gps,
            self.check_signal,
            self.check_temperature,
            self.check_health,
        ]:
            result = check(state)
            if result:
                incidents.append(result)
        return incidents

    # ──────────────────────────────────────────
    # Action validation
    # ──────────────────────────────────────────

    def validate_action(
        self,
        proposal: ActionProposal,
        uav_state: UAVState | None,
        all_states: list[UAVState],
    ) -> ActionProposal:
        """Validate an action proposal. Sets status and validation_errors."""
        errors = []

        # Check UAV exists
        if proposal.uav_id and not uav_state:
            errors.append(f"UAV {proposal.uav_id} does not exist")

        if uav_state:
            # Check battery for non-emergency actions
            if proposal.action not in {ActionType.EMERGENCY_LAND, ActionType.RETURN_TO_BASE, ActionType.LAND}:
                if uav_state.battery < self.config.min_battery_percent:
                    errors.append(f"UAV {uav_state.id} battery too low ({uav_state.battery:.1f}%) for {proposal.action}")

            # Check UAV status compatibility
            if uav_state.status in {UAVStatus.FAILED, UAVStatus.OFFLINE}:
                if proposal.action not in {ActionType.CANCEL_TASK, ActionType.CANCEL_MISSION}:
                    errors.append(f"UAV {uav_state.id} is {uav_state.status} — cannot execute {proposal.action}")

            # Check geofence for waypoint movements
            if proposal.action == ActionType.GOTO_WAYPOINT:
                target_x = proposal.parameters.get("x", 0)
                target_y = proposal.parameters.get("y", 0)
                altitude = proposal.parameters.get("altitude", 80.0)
                geo_violations = self.validate_movement(uav_state.id, target_x, target_y, altitude)
                errors.extend(geo_violations)
                sep_violations = self.check_projected_separation(
                    uav_state.id,
                    UAVPosition(x=target_x, y=target_y),
                    all_states,
                )
                errors.extend(sep_violations)

        if errors:
            proposal.status = ActionStatus.REJECTED_VALIDATION
            proposal.validation_errors = errors
            logger.warning(f"Action {proposal.action_id} rejected: {errors}")
        else:
            proposal.status = ActionStatus.VALIDATED
            logger.info(f"Action {proposal.action_id} validated")

        return proposal
