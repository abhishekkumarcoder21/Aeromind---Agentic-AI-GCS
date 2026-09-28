"""Unit tests for UAV state machine and simulator."""

import asyncio
import pytest
from packages.schemas.aeromind_schemas.uav import (
    UAVPosition,
    UAVState,
    UAVStatus,
    is_valid_transition,
    VALID_STATE_TRANSITIONS,
)
from services.simulator.uav_sim import SimulatedUAV


class TestUAVStateMachine:
    """Tests for the deterministic UAV state machine."""

    def test_valid_transitions(self):
        """All declared transitions should be valid."""
        for from_status, to_set in VALID_STATE_TRANSITIONS.items():
            for to_status in to_set:
                assert is_valid_transition(from_status, to_status), (
                    f"Expected {from_status} -> {to_status} to be valid"
                )

    def test_invalid_transitions(self):
        """LANDED -> ACTIVE should not be allowed (must go through TAKEOFF)."""
        assert not is_valid_transition(UAVStatus.LANDED, UAVStatus.ACTIVE)

    def test_idle_to_active_invalid(self):
        """IDLE -> ACTIVE should not be allowed without ARMED first."""
        assert not is_valid_transition(UAVStatus.IDLE, UAVStatus.ACTIVE)

    def test_self_transition_valid(self):
        """Same-state transitions should be valid (no-op)."""
        for status in UAVStatus:
            assert is_valid_transition(status, status)

    def test_failed_only_resets_to_idle(self):
        """FAILED state should only transition to IDLE (manual reset)."""
        allowed = VALID_STATE_TRANSITIONS[UAVStatus.FAILED]
        assert allowed == {UAVStatus.IDLE}


class TestUAVPosition:
    """Tests for UAV position calculations."""

    def test_distance_to_same(self):
        p = UAVPosition(x=10, y=20)
        assert p.distance_to(p) == 0.0

    def test_distance_to_other(self):
        p1 = UAVPosition(x=0, y=0)
        p2 = UAVPosition(x=3, y=4)
        assert p1.distance_to(p2) == pytest.approx(5.0)

    def test_distance_symmetric(self):
        p1 = UAVPosition(x=10, y=20)
        p2 = UAVPosition(x=30, y=50)
        assert p1.distance_to(p2) == pytest.approx(p2.distance_to(p1))


class TestSimulatedUAV:
    """Tests for the SimulatedUAV behavior."""

    @pytest.fixture
    def uav(self):
        return SimulatedUAV("UAV-01", UAVPosition(x=0, y=0))

    @pytest.mark.asyncio
    async def test_arm(self, uav):
        result = await uav.arm()
        assert result is True
        assert uav.status == UAVStatus.ARMED

    @pytest.mark.asyncio
    async def test_takeoff_requires_armed(self, uav):
        """Cannot takeoff from IDLE — must arm first."""
        result = await uav.takeoff()
        assert result is False
        assert uav.status == UAVStatus.IDLE

    @pytest.mark.asyncio
    async def test_arm_then_takeoff(self, uav):
        await uav.arm()
        result = await uav.takeoff(altitude=50.0)
        assert result is True
        assert uav.status == UAVStatus.TAKEOFF

    @pytest.mark.asyncio
    async def test_inject_battery(self, uav):
        uav.inject_battery(18.0)
        assert uav.battery == 18.0

    @pytest.mark.asyncio
    async def test_inject_offline(self, uav):
        uav.inject_offline()
        assert uav.status == UAVStatus.OFFLINE
        assert uav.state.health.comms_ok is False

    @pytest.mark.asyncio
    async def test_inject_motor_failure(self, uav):
        uav.inject_motor_failure()
        assert uav.status == UAVStatus.FAILED
        assert uav.state.health.motors_ok is False

    @pytest.mark.asyncio
    async def test_return_to_base_from_active(self, uav):
        await uav.arm()
        await uav.takeoff()
        uav.state.status = UAVStatus.ACTIVE  # simulate takeoff completion
        result = await uav.return_to_base()
        assert result is True
        assert uav.status == UAVStatus.RETURNING

    def test_is_available_when_idle(self, uav):
        assert uav.is_available is True

    def test_not_available_when_active(self, uav):
        uav.state.status = UAVStatus.ACTIVE
        assert uav.is_available is False

    def test_not_available_when_low_battery(self, uav):
        uav.inject_battery(20.0)
        assert uav.is_available is False
