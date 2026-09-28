"""Unit tests for the agent_core package."""

import pytest
from packages.schemas.aeromind_schemas.uav import UAVPosition, UAVState, UAVStatus, UAVHealth
from packages.schemas.aeromind_schemas.mission import (
    MissionPlan,
    MissionSpecification,
    MissionStatus,
    MissionTask,
    MissionTaskStatus,
    MissionType,
    SectorName,
    Waypoint,
)
from packages.agent_core.planner_agent import MissionPlannerAgent
from packages.agent_core.allocator_agent import TaskAllocatorAgent
from packages.agent_core.safety_agent import SafetyAgent
from packages.agent_core.monitoring_agent import MonitoringAgent
from packages.agent_core.orchestrator import AgentOrchestrator
from apps.backend.safety_engine import SafetyConfig, SafetyEngine


class TestMissionPlannerAgent:
    @pytest.fixture
    def planner(self):
        return MissionPlannerAgent()

    @pytest.mark.asyncio
    async def test_parse_sector_a(self, planner):
        spec, decision = await planner.plan_mission("Deploy UAVs to inspect Sector A")
        assert spec.area == SectorName.SECTOR_A
        assert spec.mission_type == MissionType.INSPECTION
        assert decision.agent_type.value == "MISSION_PLANNER"

    @pytest.mark.asyncio
    async def test_parse_sector_b(self, planner):
        spec, _ = await planner.plan_mission("Surveillance of sector B perimeter")
        assert spec.area == SectorName.SECTOR_B
        assert spec.mission_type == MissionType.SURVEILLANCE

    @pytest.mark.asyncio
    async def test_parse_uav_count(self, planner):
        spec, _ = await planner.plan_mission("Send 3 UAVs to inspect sector A")
        assert spec.required_uavs == 3

    @pytest.mark.asyncio
    async def test_parse_priority(self, planner):
        spec, _ = await planner.plan_mission("Urgent inspection of sector C")
        assert spec.priority == 5

    @pytest.mark.asyncio
    async def test_default_mission_type(self, planner):
        spec, _ = await planner.plan_mission("Check sector A")
        assert spec.mission_type == MissionType.INSPECTION

    @pytest.mark.asyncio
    async def test_decision_records_input(self, planner):
        _, decision = await planner.plan_mission("Patrol sector B")
        assert "Patrol sector B" in decision.observation
        assert decision.confidence is not None


class TestTaskAllocatorAgent:
    @pytest.fixture
    def allocator(self):
        return TaskAllocatorAgent()

    @pytest.fixture
    def available_uavs(self):
        return [
            UAVState(id="UAV-01", position=UAVPosition(x=0, y=0), battery=90, status=UAVStatus.IDLE),
            UAVState(id="UAV-02", position=UAVPosition(x=100, y=100), battery=80, status=UAVStatus.IDLE),
            UAVState(id="UAV-03", position=UAVPosition(x=200, y=200), battery=60, status=UAVStatus.IDLE),
        ]

    @pytest.fixture
    def tasks(self):
        return [
            MissionTask(
                mission_id="m1",
                waypoint=Waypoint(name="WP-1", x=50, y=50, altitude=80, order=0),
                order=0,
            ),
            MissionTask(
                mission_id="m1",
                waypoint=Waypoint(name="WP-2", x=150, y=150, altitude=80, order=1),
                order=1,
            ),
        ]

    @pytest.mark.asyncio
    async def test_allocates_all_tasks(self, allocator, tasks, available_uavs):
        result_tasks, decision = await allocator.allocate(tasks, available_uavs)
        assigned = [t for t in result_tasks if t.uav_id is not None]
        assert len(assigned) == 2
        assert decision.agent_type.value == "TASK_ALLOCATOR"

    @pytest.mark.asyncio
    async def test_prefers_closer_uav(self, allocator, available_uavs):
        """UAV-01 at (0,0) should be preferred for a task near (10,10)."""
        tasks = [
            MissionTask(
                mission_id="m1",
                waypoint=Waypoint(name="WP-NEAR", x=10, y=10, altitude=80, order=0),
                order=0,
            ),
        ]
        result_tasks, _ = await allocator.allocate(tasks, available_uavs)
        assert result_tasks[0].uav_id == "UAV-01"

    @pytest.mark.asyncio
    async def test_assignment_reason_recorded(self, allocator, tasks, available_uavs):
        result_tasks, _ = await allocator.allocate(tasks, available_uavs)
        for task in result_tasks:
            if task.uav_id:
                assert "Score:" in task.assignment_reason


class TestSafetyAgentIntegration:
    @pytest.fixture
    def safety_engine(self):
        return SafetyEngine(SafetyConfig())

    @pytest.fixture
    def safety_agent(self, safety_engine):
        return SafetyAgent(safety_engine)

    @pytest.mark.asyncio
    async def test_no_proposals_for_healthy_fleet(self, safety_agent):
        states = [
            UAVState(id="UAV-01", position=UAVPosition(x=100, y=100), battery=90, status=UAVStatus.ACTIVE),
            UAVState(id="UAV-02", position=UAVPosition(x=300, y=300), battery=85, status=UAVStatus.ACTIVE),
        ]
        proposals, decisions = await safety_agent.assess_fleet(states)
        assert len(proposals) == 0

    @pytest.mark.asyncio
    async def test_low_battery_triggers_rtb(self, safety_agent):
        states = [
            UAVState(id="UAV-01", position=UAVPosition(x=100, y=100), battery=18, status=UAVStatus.ACTIVE),
        ]
        proposals, decisions = await safety_agent.assess_fleet(states)
        assert len(proposals) > 0
        assert any(p.action.value in ("RETURN_TO_BASE", "EMERGENCY_LAND") for p in proposals)

    @pytest.mark.asyncio
    async def test_motor_failure_triggers_emergency(self, safety_agent):
        states = [
            UAVState(
                id="UAV-01",
                position=UAVPosition(x=100, y=100),
                battery=90,
                status=UAVStatus.ACTIVE,
                health=UAVHealth(motors_ok=False),
            ),
        ]
        proposals, decisions = await safety_agent.assess_fleet(states)
        assert len(proposals) > 0
        assert any(p.action.value == "EMERGENCY_LAND" for p in proposals)

    @pytest.mark.asyncio
    async def test_skips_idle_uavs(self, safety_agent):
        """Idle UAVs should not generate safety proposals."""
        states = [
            UAVState(id="UAV-01", position=UAVPosition(x=0, y=0), battery=10, status=UAVStatus.IDLE),
        ]
        proposals, _ = await safety_agent.assess_fleet(states)
        assert len(proposals) == 0


class TestMonitoringAgent:
    @pytest.fixture
    def monitor(self):
        return MonitoringAgent()

    def test_fleet_assessment_healthy(self, monitor):
        states = [
            UAVState(id="UAV-01", position=UAVPosition(x=0, y=0), battery=90, status=UAVStatus.IDLE),
            UAVState(id="UAV-02", position=UAVPosition(x=0, y=0), battery=85, status=UAVStatus.ACTIVE),
        ]
        assessment, decision = monitor.assess_fleet(states)
        assert assessment["fleet_summary"]["total"] == 2
        assert assessment["fleet_summary"]["active"] == 1
        assert assessment["fleet_summary"]["idle"] == 1
        assert decision.agent_type.value == "MONITORING_AGENT"

    def test_anomaly_detection(self, monitor):
        states = [
            UAVState(id="UAV-01", position=UAVPosition(x=0, y=0), battery=10, status=UAVStatus.ACTIVE),
        ]
        assessment, _ = monitor.assess_fleet(states)
        assert len(assessment["anomalies"]) > 0
        assert assessment["anomalies"][0]["type"] == "CRITICAL_BATTERY"

    def test_mission_progress(self, monitor):
        spec = MissionSpecification(
            mission_type=MissionType.INSPECTION,
            area=SectorName.SECTOR_A,
            required_uavs=2,
        )
        plan = MissionPlan(
            mission_id=spec.id,
            specification=spec,
            tasks=[
                MissionTask(
                    mission_id=spec.id,
                    waypoint=Waypoint(name="WP-1", x=0, y=0, altitude=80),
                    status=MissionTaskStatus.COMPLETED,
                ),
                MissionTask(
                    mission_id=spec.id,
                    waypoint=Waypoint(name="WP-2", x=100, y=100, altitude=80),
                    status=MissionTaskStatus.IN_PROGRESS,
                ),
            ],
            status=MissionStatus.EXECUTING,
            progress_percent=50.0,
        )
        progress, decision = monitor.assess_mission_progress(plan)
        assert progress["tasks"]["completed"] == 1
        assert progress["tasks"]["in_progress"] == 1
        assert decision.agent_type.value == "MONITORING_AGENT"


class TestAgentOrchestrator:
    def test_decision_recording(self):
        orchestrator = AgentOrchestrator()
        from packages.schemas.aeromind_schemas.agents import AgentDecision, AgentType
        dec = AgentDecision(
            agent_type=AgentType.MISSION_PLANNER,
            mission_id="m1",
            observation="test",
            decision="test decision",
            reason="test reason",
        )
        orchestrator.record_decision(dec)
        assert len(orchestrator.get_decisions()) == 1

    def test_decision_filtering(self):
        orchestrator = AgentOrchestrator()
        from packages.schemas.aeromind_schemas.agents import AgentDecision, AgentType
        dec1 = AgentDecision(
            agent_type=AgentType.MISSION_PLANNER,
            mission_id="m1",
            observation="test",
            decision="test",
            reason="test",
        )
        dec2 = AgentDecision(
            agent_type=AgentType.SAFETY_AGENT,
            mission_id="m2",
            observation="test",
            decision="test",
            reason="test",
        )
        orchestrator.record_decision(dec1)
        orchestrator.record_decision(dec2)

        assert len(orchestrator.get_decisions(mission_id="m1")) == 1
        assert len(orchestrator.get_decisions(agent_type="SAFETY_AGENT")) == 1
