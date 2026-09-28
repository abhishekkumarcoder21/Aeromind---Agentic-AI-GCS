"""Unit tests for mission schemas and world definition."""

import pytest
from packages.schemas.aeromind_schemas.mission import (
    MissionConstraints,
    MissionSpecification,
    MissionTask,
    MissionType,
    SectorName,
    Waypoint,
)
from services.simulator.world import SimulatedWorld, SECTORS


class TestSectors:
    def test_all_sectors_defined(self):
        assert SectorName.SECTOR_A in SECTORS
        assert SectorName.SECTOR_B in SECTORS
        assert SectorName.SECTOR_C in SECTORS

    def test_sector_has_waypoints(self):
        sector = SECTORS[SectorName.SECTOR_A]
        assert len(sector.waypoints) > 0

    def test_sector_contains_own_waypoints(self):
        for sector in SECTORS.values():
            for wp in sector.waypoints:
                assert sector.contains(wp.x, wp.y), (
                    f"Waypoint {wp.name} at ({wp.x}, {wp.y}) outside sector {sector.name}"
                )

    def test_sector_boundary_check(self):
        sector = SECTORS[SectorName.SECTOR_A]
        # Center should be inside
        assert sector.contains(sector.center_x, sector.center_y)
        # Far away should be outside
        assert not sector.contains(9999, 9999)


class TestSimulatedWorld:
    @pytest.fixture
    def world(self):
        return SimulatedWorld()

    def test_geofence_inside(self, world):
        assert world.is_within_geofence(100, 100, 80) is True

    def test_geofence_outside(self, world):
        assert world.is_within_geofence(9999, 9999, 80) is False

    def test_home_positions(self, world):
        assert len(world.home_positions) > 0

    def test_home_position_wrapping(self, world):
        """Index larger than home_positions list should wrap."""
        pos = world.get_home_position(100)
        assert pos is not None


class TestMissionSpecification:
    def test_valid_spec(self):
        spec = MissionSpecification(
            mission_type=MissionType.INSPECTION,
            area=SectorName.SECTOR_A,
            required_uavs=5,
        )
        assert spec.required_uavs == 5
        assert spec.constraints.minimum_battery == 25.0

    def test_constraints_defaults(self):
        constraints = MissionConstraints()
        assert constraints.minimum_battery == 25.0
        assert constraints.minimum_separation_meters == 50.0
        assert constraints.geofence_enabled is True

    def test_invalid_required_uavs(self):
        with pytest.raises(Exception):
            MissionSpecification(
                mission_type=MissionType.INSPECTION,
                area=SectorName.SECTOR_A,
                required_uavs=0,  # must be >= 1
            )
