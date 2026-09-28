"""Simulated world definition — sectors, waypoints, geofences, and base positions."""

from __future__ import annotations

from packages.schemas.aeromind_schemas.mission import Sector, SectorName, Waypoint
from packages.schemas.aeromind_schemas.uav import UAVPosition


# ── Base / Home positions for UAVs ──
HOME_POSITIONS: list[UAVPosition] = [
    UAVPosition(x=0.0, y=0.0),
    UAVPosition(x=20.0, y=0.0),
    UAVPosition(x=40.0, y=0.0),
    UAVPosition(x=60.0, y=0.0),
    UAVPosition(x=80.0, y=0.0),
    UAVPosition(x=0.0, y=20.0),
    UAVPosition(x=20.0, y=20.0),
    UAVPosition(x=40.0, y=20.0),
    UAVPosition(x=60.0, y=20.0),
    UAVPosition(x=80.0, y=20.0),
]


def _generate_sector_waypoints(
    sector_name: str,
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    rows: int = 3,
    cols: int = 3,
) -> list[Waypoint]:
    """Generate a grid of waypoints within a sector for inspection missions."""
    waypoints = []
    x_step = width / (cols + 1)
    y_step = height / (rows + 1)
    start_x = center_x - width / 2
    start_y = center_y - height / 2
    idx = 0
    for r in range(1, rows + 1):
        for c in range(1, cols + 1):
            idx += 1
            waypoints.append(
                Waypoint(
                    name=f"{sector_name[len('SECTOR_'):]}{idx}",
                    x=start_x + c * x_step,
                    y=start_y + r * y_step,
                    altitude=80.0,
                    order=idx,
                )
            )
    return waypoints


# ── Sector definitions ──
SECTORS: dict[SectorName, Sector] = {
    SectorName.SECTOR_A: Sector(
        name=SectorName.SECTOR_A,
        label="Sector A — North Industrial Zone",
        center_x=300.0,
        center_y=400.0,
        width=300.0,
        height=200.0,
        waypoints=_generate_sector_waypoints("SECTOR_A", 300.0, 400.0, 300.0, 200.0, rows=3, cols=3),
    ),
    SectorName.SECTOR_B: Sector(
        name=SectorName.SECTOR_B,
        label="Sector B — East Perimeter",
        center_x=600.0,
        center_y=250.0,
        width=250.0,
        height=250.0,
        waypoints=_generate_sector_waypoints("SECTOR_B", 600.0, 250.0, 250.0, 250.0, rows=3, cols=3),
    ),
    SectorName.SECTOR_C: Sector(
        name=SectorName.SECTOR_C,
        label="Sector C — South Storage Yard",
        center_x=200.0,
        center_y=150.0,
        width=200.0,
        height=200.0,
        waypoints=_generate_sector_waypoints("SECTOR_C", 200.0, 150.0, 200.0, 200.0, rows=2, cols=3),
    ),
}


# ── Operational geofence (entire area UAVs are allowed to fly in) ──
GEOFENCE = {
    "min_x": -50.0,
    "max_x": 800.0,
    "min_y": -50.0,
    "max_y": 600.0,
    "max_altitude": 150.0,
}


class SimulatedWorld:
    """Static world definition providing sectors, waypoints, geofence, and home positions."""

    def __init__(self) -> None:
        self.sectors = SECTORS
        self.geofence = GEOFENCE
        self.home_positions = HOME_POSITIONS

    def get_sector(self, name: SectorName) -> Sector:
        return self.sectors[name]

    def is_within_geofence(self, x: float, y: float, altitude: float = 0.0) -> bool:
        """Check if a position is within the operational geofence."""
        return (
            self.geofence["min_x"] <= x <= self.geofence["max_x"]
            and self.geofence["min_y"] <= y <= self.geofence["max_y"]
            and altitude <= self.geofence["max_altitude"]
        )

    def get_home_position(self, index: int) -> UAVPosition:
        """Get a home position by index (wraps around)."""
        return self.home_positions[index % len(self.home_positions)]
