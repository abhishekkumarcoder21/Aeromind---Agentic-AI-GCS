/* AeroMind API types — mirrors backend Pydantic schemas */

export interface UAVPosition {
  x: number;
  y: number;
}

export interface UAVHealth {
  motors_ok: boolean;
  gps_ok: boolean;
  comms_ok: boolean;
  sensors_ok: boolean;
  battery_ok: boolean;
}

export type UAVStatusType =
  | "IDLE" | "ARMED" | "TAKEOFF" | "ACTIVE" | "HOVERING"
  | "RETURNING" | "LANDING" | "LANDED" | "LOW_BATTERY"
  | "EMERGENCY" | "OFFLINE" | "FAILED";

export interface UAVState {
  id: string;
  position: UAVPosition;
  altitude: number;
  velocity: number;
  heading: number;
  battery: number;
  temperature: number;
  gps_satellites: number;
  signal_strength: number;
  status: UAVStatusType;
  health: UAVHealth;
  current_mission_id: string | null;
  current_task_id: string | null;
  home_position: UAVPosition;
  last_heartbeat: string;
}

export interface UAVTelemetry {
  uav_id: string;
  timestamp: string;
  position: UAVPosition;
  altitude: number;
  velocity: number;
  heading: number;
  battery: number;
  temperature: number;
  gps_satellites: number;
  signal_strength: number;
  status: UAVStatusType;
  current_task_id: string | null;
}

export interface Waypoint {
  id: string;
  name: string;
  x: number;
  y: number;
  altitude: number;
  order: number;
}

export interface Sector {
  name: string;
  label: string;
  center_x: number;
  center_y: number;
  width: number;
  height: number;
  waypoints: Waypoint[];
}

export interface MissionTask {
  id: string;
  mission_id: string;
  waypoint: Waypoint;
  uav_id: string | null;
  status: string;
  order: number;
  description: string;
  assignment_reason: string;
}

export interface MissionSpecification {
  id: string;
  mission_type: string;
  title: string;
  description: string;
  area: string;
  required_uavs: number;
  constraints: Record<string, unknown>;
  natural_language_input: string;
}

export interface MissionPlan {
  id: string;
  mission_id: string;
  specification: MissionSpecification;
  tasks: MissionTask[];
  status: string;
  assigned_uav_ids: string[];
  progress_percent: number;
  created_at: string;
  approved_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface MissionEvent {
  id: string;
  event_type: string;
  severity: string;
  message: string;
  mission_id: string | null;
  uav_id: string | null;
  task_id: string | null;
  details: Record<string, unknown>;
  timestamp: string;
  component: string;
}

export interface ActionProposal {
  action_id: string;
  uav_id: string | null;
  action: string;
  reason: string;
  source: string;
  requires_approval: boolean;
  status: string;
  created_at: string;
}

export interface AgentDecision {
  id: string;
  agent_type: string;
  mission_id: string | null;
  uav_id: string | null;
  observation: string;
  decision: string;
  reason: string;
  tools_called: string[];
  timestamp: string;
}

export interface Incident {
  id: string;
  incident_type: string;
  severity: string;
  uav_id: string;
  message: string;
  resolved: boolean;
  created_at: string;
}

export interface WorldData {
  sectors: Record<string, Sector>;
  geofence: {
    min_x: number;
    max_x: number;
    min_y: number;
    max_y: number;
    max_altitude: number;
  };
  home_positions: UAVPosition[];
}
