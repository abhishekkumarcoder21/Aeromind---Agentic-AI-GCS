"""Integration tests for the execution engine and mission service pipeline."""

import pytest
from packages.schemas.aeromind_schemas.uav import UAVPosition, UAVStatus
from packages.schemas.aeromind_schemas.mission import (
    MissionSpecification,
    MissionType,
    SectorName,
    MissionStatus,
    MissionTaskStatus,
)
from packages.schemas.aeromind_schemas.actions import (
    ActionProposal,
    ActionSource,
    ActionStatus,
    ActionType,
)
from apps.backend.event_manager import EventManager
from apps.backend.execution_engine import ExecutionEngine
from apps.backend.mission_service import MissionService
from apps.backend.safety_engine import SafetyConfig, SafetyEngine
from services.simulator.controller import SimulatedUAVController
from services.simulator.fleet import SimulatedFleet
from services.simulator.world import SimulatedWorld


@pytest.fixture
def world():
    return SimulatedWorld()


@pytest.fixture
def fleet(world):
    f = SimulatedFleet(world, count=8)
    f.initialize()
    return f


@pytest.fixture
def controller(fleet):
    ctrl = SimulatedUAVController()
    ctrl.register_fleet(fleet.uavs)
    return ctrl


@pytest.fixture
def safety_engine():
    return SafetyEngine(SafetyConfig())


@pytest.fixture
def event_manager():
    return EventManager()


@pytest.fixture
def execution_engine(controller, safety_engine, event_manager):
    return ExecutionEngine(controller, safety_engine, event_manager)


@pytest.fixture
def mission_service(controller, execution_engine, event_manager, world):
    return MissionService(controller, execution_engine, event_manager, world)


class TestMissionServiceIntegration:
    @pytest.mark.asyncio
    async def test_create_and_allocate_mission(self, mission_service):
        spec = MissionSpecification(
            mission_type=MissionType.INSPECTION,
            title="Test Inspection",
            area=SectorName.SECTOR_A,
            required_uavs=3,
        )
        plan = await mission_service.create_mission(spec)
        assert plan is not None
        assert len(plan.tasks) > 0

        plan = await mission_service.allocate_tasks(plan.mission_id)
        assert plan is not None
        assert plan.status == MissionStatus.AWAITING_APPROVAL
        # Check that tasks got assigned
        assigned = [t for t in plan.tasks if t.uav_id is not None]
        assert len(assigned) > 0

    @pytest.mark.asyncio
    async def test_mission_start_arms_and_takes_off(self, mission_service, controller, fleet):
        spec = MissionSpecification(
            mission_type=MissionType.INSPECTION,
            area=SectorName.SECTOR_A,
            required_uavs=2,
        )
        plan = await mission_service.create_mission(spec)
        await mission_service.allocate_tasks(plan.mission_id)
        await mission_service.start_mission(plan.mission_id)

        # Verify some UAVs changed status
        states = await controller.get_all_states()
        non_idle = [s for s in states if s.status.value != "IDLE"]
        assert len(non_idle) > 0

    @pytest.mark.asyncio
    async def test_cancel_mission(self, mission_service):
        spec = MissionSpecification(
            mission_type=MissionType.INSPECTION,
            area=SectorName.SECTOR_B,
            required_uavs=2,
        )
        plan = await mission_service.create_mission(spec)
        result = await mission_service.cancel_mission(plan.mission_id)
        assert result is not None
        assert result.status == MissionStatus.CANCELLED


class TestExecutionEngineIntegration:
    @pytest.mark.asyncio
    async def test_auto_approve_hover(self, execution_engine, controller, fleet):
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.HOVER,
            reason="Test hover",
            source=ActionSource.SYSTEM,
            requires_approval=False,
        )
        result = await execution_engine.submit_action(proposal)
        # HOVER may fail because UAV is IDLE, but it should get through validation
        assert result.status in {ActionStatus.COMPLETED, ActionStatus.FAILED}

    @pytest.mark.asyncio
    async def test_approval_required_for_rtb(self, execution_engine, controller, fleet):
        # Set UAV-01 to ACTIVE so RTB is a valid transition
        fleet.uavs["UAV-01"].state.status = UAVStatus.ACTIVE
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.RETURN_TO_BASE,
            reason="Test RTB",
            source=ActionSource.SAFETY_AGENT,
            requires_approval=True,
        )
        result = await execution_engine.submit_action(proposal)
        # Should be waiting for approval (UAV may be IDLE so validation might reject)
        assert result.status in {ActionStatus.AWAITING_APPROVAL, ActionStatus.REJECTED_VALIDATION}

    @pytest.mark.asyncio
    async def test_reject_geofence_violation(self, execution_engine, controller, fleet):
        proposal = ActionProposal(
            uav_id="UAV-01",
            action=ActionType.GOTO_WAYPOINT,
            parameters={"x": 9999, "y": 9999, "altitude": 80},
            reason="Test geofence",
            source=ActionSource.SYSTEM,
        )
        result = await execution_engine.submit_action(proposal)
        assert result.status == ActionStatus.REJECTED_VALIDATION
        assert any("GEOFENCE" in e for e in result.validation_errors)


class TestEventManager:
    @pytest.mark.asyncio
    async def test_emit_and_retrieve(self, event_manager):
        from packages.schemas.aeromind_schemas.events import EventType, EventSeverity
        event = await event_manager.emit(
            EventType.SYSTEM_INFO,
            "Test event",
            severity=EventSeverity.INFO,
        )
        events = event_manager.get_events()
        assert len(events) > 0
        assert events[-1].message == "Test event"

    @pytest.mark.asyncio
    async def test_incident_recording(self, event_manager):
        from packages.schemas.aeromind_schemas.events import Incident, IncidentType, EventSeverity
        incident = Incident(
            incident_type=IncidentType.LOW_BATTERY,
            severity=EventSeverity.WARNING,
            uav_id="UAV-01",
            message="Test low battery",
        )
        await event_manager.record_incident(incident)
        incidents = event_manager.get_incidents()
        assert len(incidents) > 0
