# AeroMind Architecture

## System Overview

AeroMind is an Agentic AI Ground Control System (GCS) for simulated autonomous UAV swarms. It demonstrates how LLMs can assist in multi-UAV mission planning while maintaining deterministic safety guarantees through a layered architecture.

## Core Design Principles

### 1. LLMs Propose, Never Execute
All LLM outputs pass through:
1. **Pydantic validation** — structured output enforcement
2. **Deterministic safety engine** — battery, geofence, separation checks
3. **Human approval** — operator must approve consequential actions
4. **Execution engine** — only validated+approved actions reach UAVs

### 2. Safety-First Architecture
The Safety Engine operates independently of any LLM:
- Geofence enforcement (rectangular operational boundary)
- Collision avoidance (minimum 50m separation)
- Battery threshold monitoring (25% warning, 15% critical)
- GPS satellite count validation (minimum 6)
- Signal strength monitoring (minimum -80 dBm)
- Temperature monitoring (maximum 75°C)
- Motor/communication health checks

### 3. Human-in-the-Loop
Actions are classified into approval categories:
- **Auto-approve**: HOVER, GOTO_WAYPOINT, ASSIGN_TASK
- **Requires approval**: RETURN_TO_BASE, EMERGENCY_LAND, CANCEL_MISSION, REASSIGN_TASK

## Architecture Layers

```
┌──────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                        │
│                                                               │
│  Next.js GCS Dashboard                                        │
│  ├── Real-time Map (Leaflet CRS.Simple)                      │
│  ├── Fleet Panel (UAV status, battery, health)               │
│  ├── Mission Panel (create, approve, monitor)                │
│  ├── Timeline (events, incidents, agent decisions)           │
│  └── Approval Workflow (approve/reject action proposals)     │
│                                                               │
│  Communication: REST API + WebSocket (telemetry, events)     │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                      API LAYER                                │
│                                                               │
│  FastAPI Backend                                              │
│  ├── /api/missions    — CRUD, approve, cancel                │
│  ├── /api/uavs        — Fleet status, telemetry              │
│  ├── /api/events      — Timeline, incidents, decisions       │
│  ├── /api/approvals   — Pending action approval              │
│  ├── /api/simulation  — Failure injection, reset             │
│  ├── /api/health      — System health check                  │
│  ├── /api/world       — Sectors, geofence, home positions    │
│  ├── /ws/telemetry    — Real-time telemetry stream           │
│  └── /ws/mission/:id  — Mission-specific event stream        │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                    AGENT LAYER                                │
│                                                               │
│  Mission Planner Agent                                        │
│  ├── NLP parsing (keyword-based + optional LLM)              │
│  ├── Sector selection                                        │
│  └── Mission specification generation                        │
│                                                               │
│  Task Allocator Agent                                         │
│  ├── Weighted scoring (distance, battery, workload, health)  │
│  └── Optimal UAV-to-task assignment                          │
│                                                               │
│  Safety Agent                                                 │
│  ├── Incident detection → action proposal translation        │
│  └── Emergency action recommendations                        │
│                                                               │
│  Monitoring Agent                                             │
│  ├── Fleet health assessment                                 │
│  ├── Mission progress tracking                               │
│  └── Anomaly detection                                       │
│                                                               │
│  Agent Orchestrator                                           │
│  └── Decision recording for explainability                   │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                   EXECUTION LAYER                             │
│                                                               │
│  Safety Engine (Deterministic)                                │
│  ├── Geofence validation                                     │
│  ├── Battery threshold checks                                │
│  ├── Separation/collision detection                          │
│  ├── GPS/signal/temperature monitoring                       │
│  └── Action proposal validation                              │
│                                                               │
│  Execution Engine                                             │
│  ├── Action validation pipeline                              │
│  ├── Approval queue management                               │
│  └── UAV controller command dispatch                         │
│                                                               │
│  Mission Service                                              │
│  ├── Mission lifecycle management                            │
│  ├── Task allocation coordination                            │
│  └── Task completion and replanning                          │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│                   SIMULATION LAYER                            │
│                                                               │
│  UAVController ABC (replaceable with PX4/MAVLink)            │
│  └── SimulatedUAVController                                  │
│      └── SimulatedFleet                                      │
│          └── SimulatedUAV (per UAV)                          │
│              ├── State machine (12 states, valid transitions)│
│              ├── Physics simulation (movement, battery, etc.)│
│              ├── Telemetry generation                        │
│              └── Failure injection API                       │
│                                                               │
│  SimulatedWorld                                               │
│  ├── 3 Sectors (A: Industrial, B: Perimeter, C: Storage)    │
│  ├── Waypoint grids per sector                               │
│  ├── Geofence definition                                     │
│  └── Home positions                                          │
└──────────────────────────────────────────────────────────────┘
```

## UAV State Machine

```
IDLE ──→ ARMED ──→ TAKEOFF ──→ ACTIVE ──→ HOVERING
  ↑                              │  │        │
  │                              │  │        │
  └── LANDED ←── LANDING ←──────┘  │        │
                    ↑               │        │
                    │               ↓        ↓
              EMERGENCY ←── LOW_BATTERY  RETURNING
                    │                        │
                    └── OFFLINE ←────────────┘
                         │
                       FAILED ──→ IDLE (manual reset only)
```

All state transitions are explicitly validated. Invalid transitions are rejected.

## Data Flow

### Mission Lifecycle
1. **Create** → Operator submits NL request → Mission Planner parses → creates tasks
2. **Allocate** → Task Allocator scores UAVs → assigns to tasks → AWAITING_APPROVAL
3. **Approve** → Operator reviews plan → approves → EXECUTING
4. **Execute** → Execution Engine arms, takes off, navigates UAVs
5. **Monitor** → Safety Agent + Monitoring Agent track progress
6. **Complete** → All tasks done → UAVs return to base → COMPLETED

### Real-time Data
- Telemetry updates every ~1s via WebSocket
- Safety monitoring loop runs every 2s
- Events broadcast to all connected clients immediately

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.12, FastAPI, SQLAlchemy, asyncio |
| Agents | LangGraph, LangChain, structured outputs |
| Frontend | Next.js, TypeScript, Tailwind CSS, Leaflet |
| Database | PostgreSQL (persistent), Redis (pub/sub) |
| Infrastructure | Docker, Docker Compose, GitHub Actions |
| Testing | pytest, pytest-asyncio |
