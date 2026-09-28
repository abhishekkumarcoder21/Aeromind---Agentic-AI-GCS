"""UAV Controller abstraction and simulated implementation.

The UAVController ABC defines the interface that the core mission system
depends on. SimulatedUAVController is the default implementation backed
by the in-process simulator. This abstraction allows later replacement
with PX4/MAVLink adapters without rewriting mission logic.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from packages.schemas.aeromind_schemas.uav import UAVState, UAVTelemetry
from services.simulator.uav_sim import SimulatedUAV

logger = logging.getLogger("aeromind.controller")


class UAVController(ABC):
    """Abstract UAV controller — the interface the execution engine uses.

    The core mission system depends on this interface, NOT on the
    simulator implementation. To integrate real hardware, implement
    a new subclass (e.g., PX4UAVController).
    """

    @abstractmethod
    async def arm(self, uav_id: str) -> bool:
        ...

    @abstractmethod
    async def takeoff(self, uav_id: str, altitude: float | None = None) -> bool:
        ...

    @abstractmethod
    async def goto_waypoint(self, uav_id: str, x: float, y: float, altitude: float | None = None) -> bool:
        ...

    @abstractmethod
    async def hover(self, uav_id: str) -> bool:
        ...

    @abstractmethod
    async def land(self, uav_id: str) -> bool:
        ...

    @abstractmethod
    async def return_to_base(self, uav_id: str) -> bool:
        ...

    @abstractmethod
    async def emergency_land(self, uav_id: str) -> bool:
        ...

    @abstractmethod
    async def get_telemetry(self, uav_id: str) -> UAVTelemetry | None:
        ...

    @abstractmethod
    async def get_state(self, uav_id: str) -> UAVState | None:
        ...

    @abstractmethod
    async def get_all_states(self) -> list[UAVState]:
        ...


class SimulatedUAVController(UAVController):
    """UAVController backed by in-process simulated UAVs."""

    def __init__(self) -> None:
        self._uavs: dict[str, SimulatedUAV] = {}

    def register_uav(self, uav: SimulatedUAV) -> None:
        self._uavs[uav.id] = uav

    def register_fleet(self, uavs: dict[str, SimulatedUAV]) -> None:
        self._uavs.update(uavs)

    def _get(self, uav_id: str) -> SimulatedUAV:
        uav = self._uavs.get(uav_id)
        if not uav:
            raise ValueError(f"UAV {uav_id} not registered in controller")
        return uav

    async def arm(self, uav_id: str) -> bool:
        return await self._get(uav_id).arm()

    async def takeoff(self, uav_id: str, altitude: float | None = None) -> bool:
        return await self._get(uav_id).takeoff(altitude)

    async def goto_waypoint(self, uav_id: str, x: float, y: float, altitude: float | None = None) -> bool:
        return await self._get(uav_id).goto_waypoint(x, y, altitude)

    async def hover(self, uav_id: str) -> bool:
        return await self._get(uav_id).hover()

    async def land(self, uav_id: str) -> bool:
        return await self._get(uav_id).land()

    async def return_to_base(self, uav_id: str) -> bool:
        return await self._get(uav_id).return_to_base()

    async def emergency_land(self, uav_id: str) -> bool:
        return await self._get(uav_id).emergency_land()

    async def get_telemetry(self, uav_id: str) -> UAVTelemetry | None:
        uav = self._uavs.get(uav_id)
        return uav.get_telemetry() if uav else None

    async def get_state(self, uav_id: str) -> UAVState | None:
        uav = self._uavs.get(uav_id)
        return uav.get_state() if uav else None

    async def get_all_states(self) -> list[UAVState]:
        return [uav.get_state() for uav in self._uavs.values()]

    # ── Failure injection (simulator-only) ──

    async def inject_battery(self, uav_id: str, level: float) -> None:
        self._get(uav_id).inject_battery(level)

    async def inject_offline(self, uav_id: str) -> None:
        self._get(uav_id).inject_offline()

    async def inject_gps_degradation(self, uav_id: str, satellites: int = 2) -> None:
        self._get(uav_id).inject_gps_degradation(satellites)

    async def inject_motor_failure(self, uav_id: str) -> None:
        self._get(uav_id).inject_motor_failure()

    async def inject_high_temperature(self, uav_id: str, temp: float = 85.0) -> None:
        self._get(uav_id).inject_high_temperature(temp)

    async def inject_signal_loss(self, uav_id: str, strength: float = -95.0) -> None:
        self._get(uav_id).inject_signal_loss(strength)
