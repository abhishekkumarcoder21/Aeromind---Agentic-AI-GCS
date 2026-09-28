"""Simulated fleet manager — manages a collection of SimulatedUAVs."""

from __future__ import annotations

import logging
from typing import Callable

from packages.schemas.aeromind_schemas.uav import UAVState, UAVTelemetry
from services.simulator.uav_sim import SimulatedUAV
from services.simulator.world import SimulatedWorld

logger = logging.getLogger("aeromind.simulator.fleet")


class SimulatedFleet:
    """Manages a fleet of simulated UAVs.

    Handles initialization, lifecycle, telemetry callback wiring,
    and provides fleet-wide query methods.
    """

    def __init__(self, world: SimulatedWorld, count: int = 8) -> None:
        self.world = world
        self.uavs: dict[str, SimulatedUAV] = {}
        self._count = count
        self._telemetry_callbacks: list[Callable] = []
        self._event_callbacks: list[Callable] = []

    def initialize(self) -> None:
        """Create the initial fleet of UAVs."""
        for i in range(self._count):
            uav_id = f"UAV-{i + 1:02d}"
            home = self.world.get_home_position(i)
            uav = SimulatedUAV(uav_id=uav_id, home_position=home)
            # Wire up callbacks
            for cb in self._telemetry_callbacks:
                uav.on_telemetry(cb)
            for cb in self._event_callbacks:
                uav.on_event(cb)
            self.uavs[uav_id] = uav
        logger.info(f"Fleet initialized with {self._count} UAVs")

    async def start_all(self, tick_interval: float = 0.5) -> None:
        """Start simulation loops for all UAVs."""
        for uav in self.uavs.values():
            await uav.start(tick_interval=tick_interval)
        logger.info("All UAV simulations started")

    async def stop_all(self) -> None:
        """Stop all UAV simulations."""
        for uav in self.uavs.values():
            await uav.stop()
        logger.info("All UAV simulations stopped")

    def on_telemetry(self, callback: Callable) -> None:
        """Register a fleet-wide telemetry callback."""
        self._telemetry_callbacks.append(callback)
        for uav in self.uavs.values():
            uav.on_telemetry(callback)

    def on_event(self, callback: Callable) -> None:
        """Register a fleet-wide event callback."""
        self._event_callbacks.append(callback)
        for uav in self.uavs.values():
            uav.on_event(callback)

    def get_uav(self, uav_id: str) -> SimulatedUAV | None:
        return self.uavs.get(uav_id)

    def get_all_states(self) -> list[UAVState]:
        return [uav.get_state() for uav in self.uavs.values()]

    def get_available_uavs(self) -> list[SimulatedUAV]:
        return [uav for uav in self.uavs.values() if uav.is_available]

    def get_uav_ids(self) -> list[str]:
        return list(self.uavs.keys())
