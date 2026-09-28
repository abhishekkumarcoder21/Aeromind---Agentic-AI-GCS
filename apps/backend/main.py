"""FastAPI application — AeroMind Backend.

Main entry point: initializes all services, wires up routes and WebSockets,
and manages the simulator lifecycle.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from apps.backend.config import get_settings
from apps.backend.event_manager import EventManager
from apps.backend.execution_engine import ExecutionEngine
from apps.backend.mission_service import MissionService
from apps.backend.safety_engine import SafetyConfig, SafetyEngine
from apps.backend.ws_manager import ConnectionManager
from apps.backend.routes import missions, uavs, events, simulation, approvals, agents
from services.simulator.controller import SimulatedUAVController
from services.simulator.fleet import SimulatedFleet
from services.simulator.world import SimulatedWorld
from packages.schemas.aeromind_schemas.uav import UAVTelemetry
from packages.agent_core.orchestrator import AgentOrchestrator
from packages.agent_core.safety_agent import SafetyAgent as SafetyAgentAI

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("aeromind")

settings = get_settings()

# ── Singleton services ──
world = SimulatedWorld()
fleet = SimulatedFleet(world, count=settings.initial_uav_count)
controller = SimulatedUAVController()
safety_engine = SafetyEngine(SafetyConfig(
    min_battery_percent=settings.min_battery_percent,
    min_separation_meters=settings.min_separation_meters,
    min_gps_satellites=settings.min_gps_satellites,
    min_signal_strength=settings.min_signal_strength,
    geofence_enabled=settings.geofence_enabled,
))
event_manager = EventManager()
ws_manager = ConnectionManager()
execution_engine = ExecutionEngine(controller, safety_engine, event_manager)
mission_service = MissionService(controller, execution_engine, event_manager, world)
agent_orchestrator = AgentOrchestrator(
    llm_config={},
    safety_engine=safety_engine,
)
safety_agent_ai = SafetyAgentAI(safety_engine)


# ── Telemetry → WebSocket bridge ──
async def _on_telemetry(telemetry: UAVTelemetry) -> None:
    """Forward simulator telemetry to WebSocket clients."""
    await ws_manager.broadcast_telemetry(telemetry.model_dump(mode="json"))


# ── Event → WebSocket bridge ──
def _on_event_sync(event):  # type: ignore
    """Forward events to WebSocket (sync wrapper for async broadcast)."""
    asyncio.create_task(ws_manager.broadcast_event(event.model_dump(mode="json")))


# ── Monitoring loop ──
async def _monitoring_loop() -> None:
    """Periodically check all UAV states for safety violations."""
    while True:
        try:
            all_states = await controller.get_all_states()

            # Run deterministic safety checks
            for state in all_states:
                incidents = safety_engine.check_uav_state(state)
                for incident in incidents:
                    await event_manager.record_incident(incident)
                # Separation check
                sep_incident = safety_engine.check_separation(state.position, state.id, all_states)
                if sep_incident:
                    await event_manager.record_incident(sep_incident)

            # Run safety agent for action proposals + decision recording
            proposals, decisions = await safety_agent_ai.assess_fleet(all_states)
            for decision in decisions:
                agent_orchestrator.record_decision(decision)
            for proposal in proposals:
                await execution_engine.submit_action(proposal)

        except Exception:
            logger.exception("Monitoring loop error")
        await asyncio.sleep(2.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — start simulator and monitoring on startup."""
    logger.info("═" * 60)
    logger.info("  AeroMind — Agentic AI Ground Control System")
    logger.info("  Starting up...")
    logger.info("═" * 60)

    # Initialize fleet
    fleet.initialize()
    controller.register_fleet(fleet.uavs)
    fleet.on_telemetry(_on_telemetry)
    event_manager.on_event(_on_event_sync)

    # Start simulator
    await fleet.start_all(tick_interval=0.5)

    # Start monitoring
    monitor_task = asyncio.create_task(_monitoring_loop())

    logger.info(f"Fleet started: {len(fleet.uavs)} UAVs")
    logger.info(f"Sectors: {list(world.sectors.keys())}")
    logger.info("System ready ✓")

    yield

    # Shutdown
    monitor_task.cancel()
    await fleet.stop_all()
    logger.info("AeroMind shutdown complete")


# ── FastAPI app ──
app = FastAPI(
    title="AeroMind",
    description="Agentic AI Ground Control System for Simulated Autonomous UAV Swarms",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Dependency injection via app state ──
app.state.controller = controller
app.state.fleet = fleet
app.state.world = world
app.state.safety_engine = safety_engine
app.state.event_manager = event_manager
app.state.ws_manager = ws_manager
app.state.execution_engine = execution_engine
app.state.mission_service = mission_service
app.state.agent_orchestrator = agent_orchestrator


# ── Routes ──
app.include_router(missions.router, prefix="/api/missions", tags=["Missions"])
app.include_router(uavs.router, prefix="/api/uavs", tags=["UAVs"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(simulation.router, prefix="/api/simulation", tags=["Simulation"])
app.include_router(approvals.router, prefix="/api/approvals", tags=["Approvals"])
app.include_router(agents.router, prefix="/api/agents", tags=["Agents"])


# ── WebSocket endpoints ──

@app.websocket("/ws/telemetry")
async def ws_telemetry(websocket: WebSocket) -> None:
    """WebSocket for real-time telemetry and events."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, receive any messages
            data = await websocket.receive_text()
            # Client can send commands through WS if needed
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.websocket("/ws/mission/{mission_id}")
async def ws_mission(websocket: WebSocket, mission_id: str) -> None:
    """WebSocket for mission-specific events."""
    await ws_manager.connect_mission(websocket, mission_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Health check ──

@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "uavs": len(fleet.uavs),
        "websocket_connections": ws_manager.connection_count,
        "active_missions": len(mission_service.get_all_missions()),
    }


@app.get("/api/world")
async def get_world() -> dict:
    """Return the simulated world definition (sectors, geofence, home positions)."""
    return {
        "sectors": {
            name.value: sector.model_dump()
            for name, sector in world.sectors.items()
        },
        "geofence": world.geofence,
        "home_positions": [pos.model_dump() for pos in world.home_positions],
    }
