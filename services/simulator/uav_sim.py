"""Individual simulated UAV with state machine, physics, and telemetry.

Each SimulatedUAV runs its own async update loop, simulating:
- Position movement toward waypoints
- Battery drain
- Temperature fluctuation
- GPS/signal variation
- State machine transitions
- Heartbeat generation
- Telemetry snapshots
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
from datetime import datetime, timezone

from packages.schemas.aeromind_schemas.uav import (
    UAVHealth,
    UAVPosition,
    UAVState,
    UAVStatus,
    UAVTelemetry,
    is_valid_transition,
)

logger = logging.getLogger("aeromind.simulator")


class SimulatedUAV:
    """A single simulated UAV with realistic behaviour."""

    # ── Physics constants ──
    DEFAULT_SPEED = 12.0         # m/s cruise
    TAKEOFF_SPEED = 3.0          # m/s vertical
    LANDING_SPEED = 2.0          # m/s vertical
    CRUISE_ALTITUDE = 80.0       # meters
    BATTERY_DRAIN_RATE = 0.03    # % per second while active
    IDLE_DRAIN_RATE = 0.002      # % per second while idle
    WAYPOINT_THRESHOLD = 5.0     # meters — "arrived" distance

    def __init__(self, uav_id: str, home_position: UAVPosition) -> None:
        self.state = UAVState(
            id=uav_id,
            position=home_position.model_copy(),
            home_position=home_position.model_copy(),
            status=UAVStatus.IDLE,
        )
        self._target_waypoint: UAVPosition | None = None
        self._target_altitude: float = 0.0
        self._on_arrival: asyncio.Event = asyncio.Event()
        self._running = False
        self._task: asyncio.Task | None = None  # type: ignore
        self._telemetry_callbacks: list = []
        self._event_callbacks: list = []

    # ──────────────────────────────────────────
    # Properties
    # ──────────────────────────────────────────

    @property
    def id(self) -> str:
        return self.state.id

    @property
    def status(self) -> UAVStatus:
        return self.state.status

    @property
    def position(self) -> UAVPosition:
        return self.state.position

    @property
    def battery(self) -> float:
        return self.state.battery

    @property
    def is_available(self) -> bool:
        """Can this UAV accept a new mission?"""
        return self.state.status in {UAVStatus.IDLE, UAVStatus.LANDED} and self.state.battery > 30

    # ──────────────────────────────────────────
    # Callback registration
    # ──────────────────────────────────────────

    def on_telemetry(self, callback) -> None:  # type: ignore
        """Register a callback for telemetry updates: callback(UAVTelemetry)."""
        self._telemetry_callbacks.append(callback)

    def on_event(self, callback) -> None:  # type: ignore
        """Register a callback for events: callback(str, dict)."""
        self._event_callbacks.append(callback)

    async def _emit_telemetry(self) -> None:
        telemetry = UAVTelemetry.from_state(self.state)
        for cb in self._telemetry_callbacks:
            try:
                result = cb(telemetry)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(f"Telemetry callback error for {self.id}")

    async def _emit_event(self, event_type: str, details: dict | None = None) -> None:
        for cb in self._event_callbacks:
            try:
                result = cb(event_type, self.id, details or {})
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.exception(f"Event callback error for {self.id}")

    # ──────────────────────────────────────────
    # State machine
    # ──────────────────────────────────────────

    def _transition(self, new_status: UAVStatus) -> bool:
        """Attempt a state transition. Returns True if valid."""
        if not is_valid_transition(self.state.status, new_status):
            logger.warning(
                f"{self.id}: Invalid transition {self.state.status} -> {new_status}"
            )
            return False
        old = self.state.status
        self.state.status = new_status
        logger.info(f"{self.id}: {old} -> {new_status}")
        return True

    # ──────────────────────────────────────────
    # Commands
    # ──────────────────────────────────────────

    async def arm(self) -> bool:
        if self._transition(UAVStatus.ARMED):
            await self._emit_event("UAV_ARMED")
            return True
        return False

    async def takeoff(self, altitude: float | None = None) -> bool:
        target_alt = altitude or self.CRUISE_ALTITUDE
        if not self._transition(UAVStatus.TAKEOFF):
            return False
        self._target_altitude = target_alt
        await self._emit_event("UAV_TAKEOFF", {"target_altitude": target_alt})
        return True

    async def goto_waypoint(self, x: float, y: float, altitude: float | None = None) -> bool:
        if self.state.status not in {UAVStatus.ACTIVE, UAVStatus.HOVERING, UAVStatus.TAKEOFF}:
            if not self._transition(UAVStatus.ACTIVE):
                return False
        else:
            self._transition(UAVStatus.ACTIVE)
        self._target_waypoint = UAVPosition(x=x, y=y)
        if altitude is not None:
            self._target_altitude = altitude
        self._on_arrival.clear()
        return True

    async def hover(self) -> bool:
        return self._transition(UAVStatus.HOVERING)

    async def land(self) -> bool:
        if not self._transition(UAVStatus.LANDING):
            return False
        self._target_altitude = 0.0
        self._target_waypoint = None
        await self._emit_event("UAV_LANDING")
        return True

    async def return_to_base(self) -> bool:
        if not self._transition(UAVStatus.RETURNING):
            return False
        self._target_waypoint = self.state.home_position.model_copy()
        self._target_altitude = self.CRUISE_ALTITUDE
        await self._emit_event("UAV_RETURNING")
        return True

    async def emergency_land(self) -> bool:
        if not self._transition(UAVStatus.EMERGENCY):
            return False
        self._target_altitude = 0.0
        self._target_waypoint = None
        await self._emit_event("UAV_EMERGENCY", {"reason": "Emergency landing initiated"})
        return True

    # ──────────────────────────────────────────
    # Failure injection
    # ──────────────────────────────────────────

    def inject_battery(self, level: float) -> None:
        """Set battery to a specific level (for failure simulation)."""
        self.state.battery = max(0.0, min(100.0, level))
        logger.info(f"{self.id}: Battery injected to {self.state.battery}%")

    def inject_offline(self) -> None:
        """Force UAV offline (simulates communication loss)."""
        self._transition(UAVStatus.OFFLINE)
        self.state.health.comms_ok = False

    def inject_gps_degradation(self, satellites: int = 2) -> None:
        self.state.gps_satellites = satellites
        self.state.health.gps_ok = satellites >= 4

    def inject_motor_failure(self) -> None:
        self.state.health.motors_ok = False
        self._transition(UAVStatus.FAILED)

    def inject_high_temperature(self, temp: float = 85.0) -> None:
        self.state.temperature = temp

    def inject_signal_loss(self, strength: float = -95.0) -> None:
        self.state.signal_strength = strength
        self.state.health.comms_ok = strength > -90

    # ──────────────────────────────────────────
    # Simulation loop
    # ──────────────────────────────────────────

    async def start(self, tick_interval: float = 0.5) -> None:
        """Start the UAV simulation loop."""
        self._running = True
        self._task = asyncio.create_task(self._run_loop(tick_interval))

    async def stop(self) -> None:
        """Stop the simulation loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self, tick_interval: float) -> None:
        """Main simulation loop — updates physics and emits telemetry."""
        telemetry_counter = 0
        while self._running:
            try:
                await self._physics_tick(tick_interval)
                telemetry_counter += 1
                # Emit telemetry every 2 ticks (~1s at 0.5s tick)
                if telemetry_counter >= 2:
                    await self._emit_telemetry()
                    telemetry_counter = 0
                # Update heartbeat
                self.state.last_heartbeat = datetime.now(timezone.utc)
                await asyncio.sleep(tick_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(f"{self.id}: Simulation loop error")
                await asyncio.sleep(tick_interval)

    async def _physics_tick(self, dt: float) -> None:
        """Update UAV physics for one time step."""
        status = self.state.status

        # ── Battery drain ──
        if status in {UAVStatus.ACTIVE, UAVStatus.TAKEOFF, UAVStatus.RETURNING, UAVStatus.HOVERING}:
            self.state.battery -= self.BATTERY_DRAIN_RATE * dt * 100
        elif status in {UAVStatus.IDLE, UAVStatus.ARMED, UAVStatus.LANDED}:
            self.state.battery -= self.IDLE_DRAIN_RATE * dt * 100
        self.state.battery = max(0.0, self.state.battery)

        # ── Low battery detection ──
        if self.state.battery < 15 and status not in {
            UAVStatus.LANDING, UAVStatus.LANDED, UAVStatus.RETURNING,
            UAVStatus.EMERGENCY, UAVStatus.OFFLINE, UAVStatus.FAILED,
        }:
            self._transition(UAVStatus.LOW_BATTERY)

        # ── Temperature fluctuation ──
        if status in {UAVStatus.ACTIVE, UAVStatus.TAKEOFF, UAVStatus.RETURNING}:
            self.state.temperature += random.uniform(-0.1, 0.3) * dt
        else:
            self.state.temperature += random.uniform(-0.2, 0.05) * dt
        self.state.temperature = max(15.0, min(95.0, self.state.temperature))

        # ── GPS satellite jitter ──
        if self.state.health.gps_ok:
            self.state.gps_satellites = max(4, min(14, self.state.gps_satellites + random.randint(-1, 1)))

        # ── Signal strength jitter ──
        if self.state.health.comms_ok:
            self.state.signal_strength += random.uniform(-2, 2)
            self.state.signal_strength = max(-90.0, min(-30.0, self.state.signal_strength))

        # ── Takeoff ──
        if status == UAVStatus.TAKEOFF:
            self.state.altitude += self.TAKEOFF_SPEED * dt
            if self.state.altitude >= self._target_altitude:
                self.state.altitude = self._target_altitude
                self._transition(UAVStatus.ACTIVE)
                await self._emit_event("UAV_ACTIVE")

        # ── Landing ──
        elif status in {UAVStatus.LANDING, UAVStatus.EMERGENCY}:
            self.state.altitude -= self.LANDING_SPEED * dt
            if self.state.altitude <= 0:
                self.state.altitude = 0.0
                self.state.velocity = 0.0
                self._transition(UAVStatus.LANDED)
                await self._emit_event("UAV_LANDED")

        # ── Horizontal movement ──
        elif status in {UAVStatus.ACTIVE, UAVStatus.RETURNING} and self._target_waypoint:
            dx = self._target_waypoint.x - self.state.position.x
            dy = self._target_waypoint.y - self.state.position.y
            dist = math.sqrt(dx * dx + dy * dy)

            if dist < self.WAYPOINT_THRESHOLD:
                # Arrived at waypoint
                self.state.position.x = self._target_waypoint.x
                self.state.position.y = self._target_waypoint.y
                self.state.velocity = 0.0
                self._on_arrival.set()

                if status == UAVStatus.RETURNING:
                    # At home — land
                    await self.land()
                else:
                    self._transition(UAVStatus.HOVERING)
                    await self._emit_event("WAYPOINT_REACHED", {
                        "x": self.state.position.x,
                        "y": self.state.position.y,
                    })
                self._target_waypoint = None
            else:
                # Move toward target
                speed = min(self.DEFAULT_SPEED, dist / dt)
                self.state.velocity = speed
                move_dist = speed * dt
                ratio = move_dist / dist
                self.state.position.x += dx * ratio
                self.state.position.y += dy * ratio
                # Update heading
                self.state.heading = (math.degrees(math.atan2(dy, dx)) + 360) % 360

        # ── Hovering ──
        elif status == UAVStatus.HOVERING:
            self.state.velocity = 0.0

    async def wait_arrival(self, timeout: float = 120.0) -> bool:
        """Wait for the UAV to arrive at its current target waypoint."""
        try:
            await asyncio.wait_for(self._on_arrival.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def get_state(self) -> UAVState:
        """Return a copy of the current state."""
        return self.state.model_copy(deep=True)

    def get_telemetry(self) -> UAVTelemetry:
        """Return current telemetry snapshot."""
        return UAVTelemetry.from_state(self.state)
