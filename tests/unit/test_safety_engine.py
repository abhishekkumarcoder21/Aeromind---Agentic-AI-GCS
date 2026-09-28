"""Unit tests for the deterministic Safety Engine."""

import pytest
from packages.schemas.aeromind_schemas.uav import (
    UAVHealth,
    UAVPosition,
    UAVState,
    UAVStatus,
)
from packages.schemas.aeromind_schemas.actions import (
    ActionProposal,
    ActionSource,
    ActionStatus,
    ActionType,
)
from apps.backend.safety_engine import SafetyConfig, SafetyEngine


@pytest.fixture
def engine():
    return SafetyEngine(SafetyConfig(
        min_battery_percent=25.0,
        critical_battery_percent=15.0,
        min_separation_meters=50.0,
        min_gps_satellites=6,
        min_signal_strength=-80.0,
        max_temperature=75.0,
        geofence_enabled=True,
    ))


@pytest.fixture
def healthy_uav():
    return UAVState(
        id="UAV-01",
        position=UAVPosition(x=100, y=100),
        altitude=80,
        battery=85,
        status=UAVStatus.ACTIVE,
    )


class TestBatteryChecks:
    def test_healthy_battery_no_incident(self, engine, healthy_uav):
        incident = engine.check_battery(healthy_uav)
        assert incident is None

    def test_low_battery_warning(self, engine, healthy_uav):
        healthy_uav.battery = 20.0
        incident = engine.check_battery(healthy_uav)
        assert incident is not None
        assert incident.incident_type.value == "LOW_BATTERY"

    def test_critical_battery(self, engine, healthy_uav):
        healthy_uav.battery = 10.0
        incident = engine.check_battery(healthy_uav)
        assert incident is not None
        assert incident.incident_type.value == "CRITICAL_BATTERY"
        assert incident.severity.value == "CRITICAL"


class TestGeofenceChecks:
    def test_inside_geofence(self, engine):
        assert engine.check_geofence(100, 100, 80) is True

    def test_outside_geofence_x(self, engine):
        assert engine.check_geofence(900, 100, 80) is False

    def test_outside_geofence_y(self, engine):
        assert engine.check_geofence(100, 700, 80) is False

    def test_above_altitude_limit(self, engine):
        assert engine.check_geofence(100, 100, 200) is False

    def test_geofence_disabled(self, engine):
        engine.config.geofence_enabled = False
        assert engine.check_geofence(9999, 9999, 9999) is True

    def test_validate_movement_inside(self, engine):
        violations = engine.validate_movement("UAV-01", 200, 200, 80)
        assert violations == []

    def test_validate_movement_outside(self, engine):
        violations = engine.validate_movement("UAV-01", 900, 100, 80)
        assert len(violations) == 1
        assert "GEOFENCE_VIOLATION" in violations[0]


class TestSeparationChecks:
    def test_no_collision_when_far(self, engine):
        uav_pos = UAVPosition(x=100, y=100)
        other_states = [
            UAVState(id="UAV-02", position=UAVPosition(x=300, y=300), status=UAVStatus.ACTIVE),
        ]
        incident = engine.check_separation(uav_pos, "UAV-01", other_states)
        assert incident is None

    def test_collision_risk_when_close(self, engine):
        uav_pos = UAVPosition(x=100, y=100)
        other_states = [
            UAVState(id="UAV-02", position=UAVPosition(x=120, y=110), status=UAVStatus.ACTIVE),
        ]
        incident = engine.check_separation(uav_pos, "UAV-01", other_states)
        assert incident is not None
        assert incident.incident_type.value == "COLLISION_RISK"

    def test_no_collision_with_landed_uav(self, engine):
        uav_pos = UAVPosition(x=100, y=100)
        other_states = [
            UAVState(id="UAV-02", position=UAVPosition(x=100, y=100), status=UAVStatus.LANDED),
        ]
        incident = engine.check_separation(uav_pos, "UAV-01", other_states)
        assert incident is None


class TestActionValidation:
    def test_valid_action(self, engine, healthy_uav):
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.HOVER,
            reason="Test",
            source=ActionSource.SYSTEM,
        )
        result = engine.validate_action(proposal, healthy_uav, [healthy_uav])
        assert result.status == ActionStatus.VALIDATED

    def test_reject_nonexistent_uav(self, engine):
        proposal = ActionProposal(
            uav_id="UAV-99",
            action=ActionType.TAKEOFF,
            reason="Test",
            source=ActionSource.SYSTEM,
        )
        result = engine.validate_action(proposal, None, [])
        assert result.status == ActionStatus.REJECTED_VALIDATION
        assert any("does not exist" in e for e in result.validation_errors)

    def test_reject_low_battery_for_takeoff(self, engine, healthy_uav):
        healthy_uav.battery = 10.0
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.TAKEOFF,
            reason="Test",
            source=ActionSource.SYSTEM,
        )
        result = engine.validate_action(proposal, healthy_uav, [healthy_uav])
        assert result.status == ActionStatus.REJECTED_VALIDATION

    def test_allow_rtb_on_low_battery(self, engine, healthy_uav):
        """Return-to-base should be allowed even with low battery."""
        healthy_uav.battery = 10.0
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.RETURN_TO_BASE,
            reason="Low battery",
            source=ActionSource.SAFETY_AGENT,
        )
        result = engine.validate_action(proposal, healthy_uav, [healthy_uav])
        assert result.status == ActionStatus.VALIDATED

    def test_reject_geofence_violation(self, engine, healthy_uav):
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.GOTO_WAYPOINT,
            parameters={"x": 900, "y": 100, "altitude": 80},
            reason="Test",
            source=ActionSource.SYSTEM,
        )
        result = engine.validate_action(proposal, healthy_uav, [healthy_uav])
        assert result.status == ActionStatus.REJECTED_VALIDATION
        assert any("GEOFENCE" in e for e in result.validation_errors)

    def test_reject_offline_uav_command(self, engine, healthy_uav):
        healthy_uav.status = UAVStatus.OFFLINE
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.TAKEOFF,
            reason="Test",
            source=ActionSource.SYSTEM,
        )
        result = engine.validate_action(proposal, healthy_uav, [healthy_uav])
        assert result.status == ActionStatus.REJECTED_VALIDATION


class TestHealthChecks:
    def test_motor_failure_incident(self, engine, healthy_uav):
        healthy_uav.health.motors_ok = False
        incident = engine.check_health(healthy_uav)
        assert incident is not None
        assert incident.incident_type.value == "MOTOR_FAILURE"

    def test_comms_failure_incident(self, engine, healthy_uav):
        healthy_uav.health.comms_ok = False
        incident = engine.check_health(healthy_uav)
        assert incident is not None
        assert incident.incident_type.value == "COMMUNICATION_LOSS"

    def test_high_temp_incident(self, engine, healthy_uav):
        healthy_uav.temperature = 80.0
        incident = engine.check_temperature(healthy_uav)
        assert incident is not None
        assert incident.incident_type.value == "HIGH_TEMPERATURE"

    def test_gps_degradation(self, engine, healthy_uav):
        healthy_uav.gps_satellites = 3
        incident = engine.check_gps(healthy_uav)
        assert incident is not None
        assert incident.incident_type.value == "GPS_DEGRADATION"
