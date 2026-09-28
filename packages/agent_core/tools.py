"""LangGraph-compatible tool definitions for agent use.

These tools provide a structured interface for agents to query fleet status,
world state, and propose actions. All tools return structured data that
agents can reason over.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger("aeromind.tools")


# ──────────────────────────────────────────────
# Fleet & UAV Tools
# ──────────────────────────────────────────────

def create_fleet_tools(controller: Any, world: Any, safety_engine: Any) -> list:
    """Create tools bound to live system instances."""

    @tool
    async def get_fleet_status() -> dict:
        """Get the current status of all UAVs in the fleet.

        Returns a summary including each UAV's id, status, battery level,
        position, health, and availability for mission assignment.
        """
        states = await controller.get_all_states()
        return {
            "total_uavs": len(states),
            "uavs": [
                {
                    "id": s.id,
                    "status": s.status.value,
                    "battery": round(s.battery, 1),
                    "position": {"x": round(s.position.x, 1), "y": round(s.position.y, 1)},
                    "altitude": round(s.altitude, 1),
                    "velocity": round(s.velocity, 1),
                    "health": {
                        "motors_ok": s.health.motors_ok,
                        "gps_ok": s.health.gps_ok,
                        "comms_ok": s.health.comms_ok,
                        "is_healthy": s.health.is_healthy,
                    },
                    "available": s.status.value in ("IDLE", "LANDED") and s.battery > 25,
                }
                for s in states
            ],
        }

    @tool
    async def get_uav_state(uav_id: str) -> dict:
        """Get detailed state for a specific UAV by its ID (e.g., 'UAV-01').

        Returns position, status, battery, health, and telemetry data.
        """
        state = await controller.get_state(uav_id)
        if not state:
            return {"error": f"UAV {uav_id} not found"}
        return {
            "id": state.id,
            "status": state.status.value,
            "battery": round(state.battery, 1),
            "temperature": round(state.temperature, 1),
            "position": {"x": round(state.position.x, 1), "y": round(state.position.y, 1)},
            "altitude": round(state.altitude, 1),
            "velocity": round(state.velocity, 1),
            "heading": round(state.heading, 1),
            "gps_satellites": state.gps_satellites,
            "signal_strength": round(state.signal_strength, 1),
            "health": {
                "motors_ok": state.health.motors_ok,
                "gps_ok": state.health.gps_ok,
                "comms_ok": state.health.comms_ok,
                "sensors_ok": state.health.sensors_ok,
                "battery_ok": state.health.battery_ok,
                "is_healthy": state.health.is_healthy,
            },
        }

    @tool
    async def get_available_uavs() -> dict:
        """Get a list of UAVs available for mission assignment.

        Returns only UAVs that are IDLE or LANDED with sufficient battery (>25%).
        """
        states = await controller.get_all_states()
        available = [
            s for s in states
            if s.status.value in ("IDLE", "LANDED") and s.battery > 25
        ]
        return {
            "available_count": len(available),
            "uavs": [
                {
                    "id": s.id,
                    "battery": round(s.battery, 1),
                    "position": {"x": round(s.position.x, 1), "y": round(s.position.y, 1)},
                }
                for s in available
            ],
        }

    # ──────────────────────────────────────────────
    # World & Sector Tools
    # ──────────────────────────────────────────────

    @tool
    def get_sector_info(sector_name: str) -> dict:
        """Get information about a named sector (SECTOR_A, SECTOR_B, or SECTOR_C).

        Returns the sector's label, boundaries, center position, and waypoints.
        """
        from packages.schemas.aeromind_schemas.mission import SectorName
        try:
            name = SectorName(sector_name)
        except ValueError:
            return {"error": f"Unknown sector: {sector_name}. Valid: SECTOR_A, SECTOR_B, SECTOR_C"}

        sector = world.get_sector(name)
        return {
            "name": sector.name.value,
            "label": sector.label,
            "center": {"x": sector.center_x, "y": sector.center_y},
            "size": {"width": sector.width, "height": sector.height},
            "bounds": {
                "min_x": sector.min_x, "max_x": sector.max_x,
                "min_y": sector.min_y, "max_y": sector.max_y,
            },
            "waypoints": [
                {"name": wp.name, "x": wp.x, "y": wp.y, "altitude": wp.altitude, "order": wp.order}
                for wp in sector.waypoints
            ],
            "waypoint_count": len(sector.waypoints),
        }

    @tool
    def get_world_info() -> dict:
        """Get the simulated world definition: available sectors, geofence bounds, and home positions."""
        return {
            "sectors": [
                {"name": name.value, "label": sector.label}
                for name, sector in world.sectors.items()
            ],
            "geofence": world.geofence,
            "home_positions": [
                {"x": pos.x, "y": pos.y} for pos in world.home_positions
            ],
        }

    # ──────────────────────────────────────────────
    # Safety Tools
    # ──────────────────────────────────────────────

    @tool
    def check_geofence(x: float, y: float, altitude: float = 80.0) -> dict:
        """Check if a position is within the operational geofence.

        Args:
            x: X coordinate in meters
            y: Y coordinate in meters
            altitude: Altitude in meters (default 80.0)

        Returns whether the position is safe and any violations.
        """
        is_safe = safety_engine.check_geofence(x, y, altitude)
        violations = safety_engine.validate_movement("check", x, y, altitude)
        return {
            "position": {"x": x, "y": y, "altitude": altitude},
            "within_geofence": is_safe,
            "violations": violations,
        }

    @tool
    async def check_uav_safety(uav_id: str) -> dict:
        """Run all safety checks on a specific UAV.

        Returns any detected incidents (battery, GPS, signal, temperature, health).
        """
        state = await controller.get_state(uav_id)
        if not state:
            return {"error": f"UAV {uav_id} not found"}

        incidents = safety_engine.check_uav_state(state)
        return {
            "uav_id": uav_id,
            "incident_count": len(incidents),
            "incidents": [
                {
                    "type": inc.incident_type.value,
                    "severity": inc.severity.value,
                    "message": inc.message,
                }
                for inc in incidents
            ],
            "is_safe": len(incidents) == 0,
        }

    @tool
    async def check_fleet_safety() -> dict:
        """Run safety checks on the entire fleet.

        Returns a summary of all safety issues across all UAVs.
        """
        states = await controller.get_all_states()
        all_incidents = []
        for state in states:
            incidents = safety_engine.check_uav_state(state)
            for inc in incidents:
                all_incidents.append({
                    "uav_id": inc.uav_id,
                    "type": inc.incident_type.value,
                    "severity": inc.severity.value,
                    "message": inc.message,
                })

        return {
            "total_uavs": len(states),
            "total_incidents": len(all_incidents),
            "incidents": all_incidents,
            "fleet_safe": len(all_incidents) == 0,
        }

    @tool
    def calculate_distance(x1: float, y1: float, x2: float, y2: float) -> dict:
        """Calculate Euclidean distance between two points in the simulated world.

        Args:
            x1, y1: First position coordinates
            x2, y2: Second position coordinates
        """
        import math
        dist = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return {"distance_meters": round(dist, 2), "from": {"x": x1, "y": y1}, "to": {"x": x2, "y": y2}}

    return [
        get_fleet_status,
        get_uav_state,
        get_available_uavs,
        get_sector_info,
        get_world_info,
        check_geofence,
        check_uav_safety,
        check_fleet_safety,
        calculate_distance,
    ]
