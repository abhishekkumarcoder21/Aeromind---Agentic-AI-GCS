/* AeroMind API client */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const error = await res.text();
    throw new Error(`API error ${res.status}: ${error}`);
  }
  return res.json();
}

// ── UAVs ──
export async function fetchUAVs() {
  return fetchAPI<{ uavs: import("./types").UAVState[] }>("/api/uavs");
}

export async function fetchUAV(uavId: string) {
  return fetchAPI<{ uav: import("./types").UAVState }>(`/api/uavs/${uavId}`);
}

// ── Missions ──
export async function fetchMissions() {
  return fetchAPI<{ missions: import("./types").MissionPlan[] }>("/api/missions");
}

export async function createMission(data: {
  natural_language?: string;
  mission_type?: string;
  area?: string;
  required_uavs?: number;
  title?: string;
}) {
  return fetchAPI<{ mission: import("./types").MissionPlan }>("/api/missions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function approveMission(missionId: string) {
  return fetchAPI<{ mission: import("./types").MissionPlan }>(
    `/api/missions/${missionId}/approve`,
    { method: "POST" }
  );
}

export async function cancelMission(missionId: string) {
  return fetchAPI<{ mission: import("./types").MissionPlan }>(
    `/api/missions/${missionId}/cancel`,
    { method: "POST" }
  );
}

export async function fetchMissionDecisions(missionId: string) {
  return fetchAPI<{ decisions: import("./types").AgentDecision[] }>(
    `/api/missions/${missionId}/decisions`
  );
}

// ── Events ──
export async function fetchEvents(params?: { mission_id?: string; uav_id?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.mission_id) query.set("mission_id", params.mission_id);
  if (params?.uav_id) query.set("uav_id", params.uav_id);
  if (params?.limit) query.set("limit", String(params.limit));
  return fetchAPI<{ events: import("./types").MissionEvent[] }>(`/api/events?${query}`);
}

export async function fetchIncidents() {
  return fetchAPI<{ incidents: import("./types").Incident[] }>("/api/events/incidents");
}

export async function fetchAgentDecisions() {
  return fetchAPI<{ decisions: import("./types").AgentDecision[] }>("/api/events/agent-decisions");
}

// ── Approvals ──
export async function fetchPendingApprovals() {
  return fetchAPI<{ approvals: import("./types").ActionProposal[] }>("/api/approvals");
}

export async function submitApproval(actionId: string, decision: "APPROVED" | "REJECTED", reason = "") {
  return fetchAPI<{ action: import("./types").ActionProposal }>(`/api/approvals/${actionId}`, {
    method: "POST",
    body: JSON.stringify({ decision, reason }),
  });
}

// ── Simulation ──
export async function injectFailure(uavId: string, failureType: string, value?: number) {
  return fetchAPI<{ message: string }>(`/api/simulation/uavs/${uavId}/inject-failure`, {
    method: "POST",
    body: JSON.stringify({ failure_type: failureType, value }),
  });
}

export async function resetSimulation() {
  return fetchAPI<{ message: string }>("/api/simulation/reset", { method: "POST" });
}

// ── World ──
export async function fetchWorld() {
  return fetchAPI<import("./types").WorldData>("/api/world");
}

// ── Health ──
export async function fetchHealth() {
  return fetchAPI<{ status: string; uavs: number; websocket_connections: number; active_missions: number }>(
    "/api/health"
  );
}

// ── WebSocket ──
export function createTelemetryWS(
  onMessage: (channel: string, data: unknown) => void,
  onOpen?: () => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(`${WS_URL}/ws/telemetry`);
  ws.onopen = () => onOpen?.();
  ws.onclose = () => onClose?.();
  ws.onerror = () => onClose?.();
  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      onMessage(msg.channel, msg.data);
    } catch {
      // ignore parse errors
    }
  };
  return ws;
}
