# AeroMind API Reference

## Base URL
```
http://localhost:8000
```

## Authentication
No authentication is required for the local development environment.

---

## UAVs

### GET /api/uavs
List all UAVs and their current state.

**Response:**
```json
{
  "uavs": [
    {
      "id": "UAV-01",
      "position": {"x": 0.0, "y": 0.0},
      "altitude": 0.0,
      "velocity": 0.0,
      "heading": 0.0,
      "battery": 100.0,
      "temperature": 25.0,
      "gps_satellites": 12,
      "signal_strength": -50.0,
      "status": "IDLE",
      "health": {"motors_ok": true, "gps_ok": true, "comms_ok": true, "sensors_ok": true, "battery_ok": true},
      "home_position": {"x": 0.0, "y": 0.0}
    }
  ]
}
```

### GET /api/uavs/{uav_id}
Get state of a specific UAV.

### GET /api/uavs/{uav_id}/telemetry
Get current telemetry for a UAV.

---

## Missions

### POST /api/missions
Create a new mission.

**Request Body:**
```json
{
  "natural_language": "Deploy 5 UAVs to inspect Sector A",
  "mission_type": "INSPECTION",
  "area": "SECTOR_A",
  "required_uavs": 5,
  "title": "North Zone Inspection"
}
```

**Mission Types:** `INSPECTION`, `SURVEILLANCE`, `SEARCH_AND_RESCUE`, `DELIVERY`, `MAPPING`, `PATROL`, `CUSTOM`

**Sectors:** `SECTOR_A`, `SECTOR_B`, `SECTOR_C`

### GET /api/missions
List all missions.

### GET /api/missions/{mission_id}
Get details of a specific mission.

### POST /api/missions/{mission_id}/approve
Approve a planned mission and start execution.

### POST /api/missions/{mission_id}/cancel
Cancel a mission.

### GET /api/missions/{mission_id}/decisions
Get agent decisions associated with a mission.

---

## Events

### GET /api/events
List events with optional filters.

**Query Parameters:**
- `mission_id` (optional): Filter by mission
- `uav_id` (optional): Filter by UAV
- `limit` (optional, default 100): Maximum results

### GET /api/events/incidents
List safety incidents.

**Query Parameters:**
- `uav_id` (optional): Filter by UAV
- `resolved` (optional): Filter by resolution status
- `limit` (optional, default 50): Maximum results

### GET /api/events/agent-decisions
List all agent decisions for explainability.

---

## Approvals

### GET /api/approvals
List pending approval requests.

### POST /api/approvals/{action_id}
Approve or reject an action.

**Request Body:**
```json
{
  "decision": "APPROVED",
  "reason": "Operator approves return to base"
}
```

---

## Simulation

### POST /api/simulation/uavs/{uav_id}/inject-failure
Inject a simulated failure into a UAV.

**Request Body:**
```json
{
  "failure_type": "LOW_BATTERY",
  "value": 18.0
}
```

**Failure Types:** `LOW_BATTERY`, `OFFLINE`, `GPS_DEGRADATION`, `SIGNAL_LOSS`, `HIGH_TEMPERATURE`, `MOTOR_FAILURE`

### POST /api/simulation/reset
Reset the entire simulation.

---

## World

### GET /api/world
Get the simulated world definition (sectors, geofence, home positions).

---

## Health

### GET /api/health
System health check.

**Response:**
```json
{
  "status": "ok",
  "uavs": 8,
  "websocket_connections": 1,
  "active_missions": 0
}
```

---

## WebSocket Endpoints

### WS /ws/telemetry
Real-time telemetry and event stream.

**Message format:**
```json
{
  "channel": "telemetry",
  "data": {
    "uav_id": "UAV-01",
    "position": {"x": 150.0, "y": 200.0},
    "battery": 85.3,
    "status": "ACTIVE"
  }
}
```

**Channels:** `telemetry`, `event`, `approval_request`

### WS /ws/mission/{mission_id}
Mission-specific event stream.
