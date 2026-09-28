"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import {
  fetchUAVs,
  fetchMissions,
  fetchEvents,
  fetchPendingApprovals,
  fetchWorld,
  fetchAgentDecisions,
  createMission,
  approveMission,
  cancelMission,
  submitApproval,
  injectFailure,
  createTelemetryWS,
} from "./api";
import type {
  UAVState,
  UAVTelemetry,
  MissionPlan,
  MissionEvent,
  ActionProposal,
  AgentDecision,
  WorldData,
} from "./types";

// Dynamic import for Leaflet map (SSR disabled)
const UAVMap = dynamic(() => import("./components/UAVMap"), { ssr: false });

export default function GCSDashboard() {
  // ── State ──
  const [uavs, setUavs] = useState<UAVState[]>([]);
  const [missions, setMissions] = useState<MissionPlan[]>([]);
  const [events, setEvents] = useState<MissionEvent[]>([]);
  const [approvals, setApprovals] = useState<ActionProposal[]>([]);
  const [decisions, setDecisions] = useState<AgentDecision[]>([]);
  const [world, setWorld] = useState<WorldData | null>(null);
  const [selectedUAV, setSelectedUAV] = useState<string | null>(null);
  const [wsConnected, setWsConnected] = useState(false);
  const [missionInput, setMissionInput] = useState("");
  const [activeTab, setActiveTab] = useState<"timeline" | "approvals" | "decisions">("timeline");
  const wsRef = useRef<WebSocket | null>(null);

  // ── Data loading ──
  const loadData = useCallback(async () => {
    try {
      const [uavData, missionData, eventData, approvalData, worldData, decisionData] = await Promise.all([
        fetchUAVs(),
        fetchMissions(),
        fetchEvents({ limit: 200 }),
        fetchPendingApprovals(),
        fetchWorld(),
        fetchAgentDecisions(),
      ]);
      setUavs(uavData.uavs);
      setMissions(missionData.missions);
      setEvents(eventData.events);
      setApprovals(approvalData.approvals);
      setWorld(worldData);
      setDecisions(decisionData.decisions);
    } catch (err) {
      console.error("Failed to load data:", err);
    }
  }, []);

  // ── WebSocket ──
  useEffect(() => {
    loadData();

    const ws = createTelemetryWS(
      (channel, data) => {
        if (channel === "telemetry") {
          const t = data as UAVTelemetry;
          setUavs((prev) =>
            prev.map((u) =>
              u.id === t.uav_id
                ? {
                    ...u,
                    position: t.position,
                    altitude: t.altitude,
                    velocity: t.velocity,
                    heading: t.heading,
                    battery: t.battery,
                    temperature: t.temperature,
                    gps_satellites: t.gps_satellites,
                    signal_strength: t.signal_strength,
                    status: t.status,
                  }
                : u
            )
          );
        } else if (channel === "event") {
          const evt = data as MissionEvent;
          setEvents((prev) => [...prev.slice(-199), evt]);
        } else if (channel === "approval_request") {
          loadData(); // Refresh approvals
        }
      },
      () => setWsConnected(true),
      () => {
        setWsConnected(false);
        // Reconnect after 3s
        setTimeout(() => loadData(), 3000);
      }
    );
    wsRef.current = ws;

    // Poll for fresh data every 5s as fallback
    const interval = setInterval(loadData, 5000);

    return () => {
      ws.close();
      clearInterval(interval);
    };
  }, [loadData]);

  // ── Handlers ──
  const handleCreateMission = async () => {
    if (!missionInput.trim()) return;
    try {
      // Parse simple commands
      let area = "SECTOR_A";
      let uavCount = 5;
      const input = missionInput.toLowerCase();
      if (input.includes("sector b")) area = "SECTOR_B";
      if (input.includes("sector c")) area = "SECTOR_C";
      const numMatch = input.match(/(\d+)\s*uav/i);
      if (numMatch) uavCount = parseInt(numMatch[1]);

      await createMission({
        natural_language: missionInput,
        mission_type: "INSPECTION",
        area,
        required_uavs: uavCount,
        title: missionInput.slice(0, 100),
      });
      setMissionInput("");
      loadData();
    } catch (err) {
      console.error("Failed to create mission:", err);
    }
  };

  const handleApprove = async (missionId: string) => {
    try {
      await approveMission(missionId);
      loadData();
    } catch (err) {
      console.error("Failed to approve:", err);
    }
  };

  const handleActionApproval = async (actionId: string, decision: "APPROVED" | "REJECTED") => {
    try {
      await submitApproval(actionId, decision);
      loadData();
    } catch (err) {
      console.error("Failed to submit approval:", err);
    }
  };

  const handleInjectFailure = async (uavId: string, type: string, value?: number) => {
    try {
      await injectFailure(uavId, type, value);
      loadData();
    } catch (err) {
      console.error("Failed to inject failure:", err);
    }
  };

  // ── Computed ──
  const selectedUAVData = uavs.find((u) => u.id === selectedUAV);
  const activeUavs = uavs.filter((u) => !["IDLE", "LANDED", "OFFLINE", "FAILED"].includes(u.status));
  const offlineUavs = uavs.filter((u) => ["OFFLINE", "FAILED"].includes(u.status));
  const avgBattery = uavs.length > 0 ? uavs.reduce((s, u) => s + u.battery, 0) / uavs.length : 0;
  const activeMission = missions.find((m) => m.status === "EXECUTING");
  const incidentEvents = events.filter((e) => e.severity === "WARNING" || e.severity === "ERROR" || e.severity === "CRITICAL");

  return (
    <div className="gcs-layout">
      {/* ── Header ── */}
      <header className="gcs-header">
        <div className="header-brand">
          <div>
            <h1>AeroMind</h1>
            <div className="subtitle">Agentic AI Ground Control System</div>
          </div>
        </div>
        <div className="header-status">
          <div className="status-indicator">
            <div className={`status-dot ${wsConnected ? "connected" : "disconnected"}`} />
            {wsConnected ? "Connected" : "Disconnected"}
          </div>
          {activeMission && (
            <div className="status-indicator">
              <div className="status-dot connected" />
              Mission Active — {activeMission.progress_percent.toFixed(0)}%
            </div>
          )}
          <div className="status-indicator" style={{ color: "var(--text-muted)" }}>
            {uavs.length} UAVs
          </div>
        </div>
      </header>

      {/* ── Left Sidebar: Mission list + UAV list ── */}
      <div className="gcs-sidebar-left">
        {/* Mission Input */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">New Mission</span>
          </div>
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            <input
              className="mission-input"
              placeholder="Deploy 5 UAVs to inspect Sector A..."
              value={missionInput}
              onChange={(e) => setMissionInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateMission()}
            />
          </div>
          <button
            className="btn btn-primary"
            style={{ width: "100%", marginTop: 6 }}
            onClick={handleCreateMission}
          >
            Create Mission
          </button>
        </div>

        {/* Missions */}
        {missions.length > 0 && (
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">Missions</span>
              <span style={{ fontSize: 10, color: "var(--text-muted)" }}>{missions.length}</span>
            </div>
            {missions.map((m) => (
              <div key={m.id} className="card">
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                  <span style={{ fontSize: 11, fontWeight: 600 }}>
                    {m.specification.title || m.specification.mission_type}
                  </span>
                  <span
                    style={{
                      fontSize: 9,
                      padding: "1px 6px",
                      borderRadius: 3,
                      background:
                        m.status === "EXECUTING"
                          ? "rgba(34,197,94,0.2)"
                          : m.status === "COMPLETED"
                          ? "rgba(59,130,246,0.2)"
                          : "rgba(107,114,128,0.2)",
                      color:
                        m.status === "EXECUTING"
                          ? "var(--status-active)"
                          : m.status === "COMPLETED"
                          ? "var(--accent-blue)"
                          : "var(--text-muted)",
                    }}
                  >
                    {m.status}
                  </span>
                </div>
                <div style={{ fontSize: 10, color: "var(--text-muted)" }}>
                  {m.specification.area} • {m.tasks.length} tasks • {m.progress_percent.toFixed(0)}%
                </div>
                {m.status === "AWAITING_APPROVAL" && (
                  <div style={{ marginTop: 6, display: "flex", gap: 4 }}>
                    <button className="btn btn-success" onClick={() => handleApprove(m.mission_id)}>
                      Approve & Execute
                    </button>
                    <button className="btn btn-outline" onClick={() => cancelMission(m.mission_id).then(loadData)}>
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* UAV List */}
        <div className="panel">
          <div className="panel-header">
            <span className="panel-title">Fleet</span>
            <span style={{ fontSize: 10, color: "var(--text-muted)" }}>
              {activeUavs.length} active
            </span>
          </div>
          {uavs.map((uav) => (
            <div
              key={uav.id}
              className={`uav-item ${selectedUAV === uav.id ? "active" : ""}`}
              onClick={() => setSelectedUAV(uav.id)}
              style={selectedUAV === uav.id ? { background: "var(--bg-hover)" } : {}}
            >
              <div className={`uav-status-badge ${uav.status}`} />
              <div className="uav-info">
                <div className="uav-id">{uav.id}</div>
                <div className="uav-status-text">{uav.status}</div>
              </div>
              <div
                className={`uav-battery ${
                  uav.battery > 50 ? "high" : uav.battery > 25 ? "medium" : "low"
                }`}
              >
                {uav.battery.toFixed(0)}%
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Center: Map ── */}
      <div className="gcs-main">
        {/* Stats bar */}
        <div className="stat-grid" style={{ position: "absolute", top: 0, left: 0, right: 0, zIndex: 1000 }}>
          <div className="stat-item">
            <div className="stat-value">{uavs.length}</div>
            <div className="stat-label">Total UAVs</div>
          </div>
          <div className="stat-item">
            <div className="stat-value" style={{ color: "var(--status-active)" }}>
              {activeUavs.length}
            </div>
            <div className="stat-label">Active</div>
          </div>
          <div className="stat-item">
            <div className="stat-value" style={{ color: "var(--status-error)" }}>
              {offlineUavs.length}
            </div>
            <div className="stat-label">Offline</div>
          </div>
          <div className="stat-item">
            <div className="stat-value" style={{ color: avgBattery > 50 ? "var(--status-active)" : avgBattery > 25 ? "var(--status-warning)" : "var(--status-error)" }}>
              {avgBattery.toFixed(0)}%
            </div>
            <div className="stat-label">Avg Battery</div>
          </div>
        </div>

        {/* Approval banners */}
        {approvals.length > 0 && (
          <div style={{ position: "absolute", top: 60, left: 12, right: 12, zIndex: 1000 }}>
            {approvals.map((a) => (
              <div key={a.action_id} className="approval-banner">
                <div className="message">
                  ⚠️ {a.source} recommends <strong>{a.action}</strong> for{" "}
                  <strong>{a.uav_id || "system"}</strong> — {a.reason}
                </div>
                <div className="approval-actions">
                  <button
                    className="btn btn-success"
                    onClick={() => handleActionApproval(a.action_id, "APPROVED")}
                  >
                    Approve
                  </button>
                  <button
                    className="btn btn-danger"
                    onClick={() => handleActionApproval(a.action_id, "REJECTED")}
                  >
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Map */}
        <UAVMap uavs={uavs} world={world} selectedUAV={selectedUAV} onSelectUAV={setSelectedUAV} missions={missions} />
      </div>

      {/* ── Right Sidebar: UAV Details + Failure Injection ── */}
      <div className="gcs-sidebar-right">
        {selectedUAVData ? (
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">{selectedUAVData.id} Details</span>
              <div className={`uav-status-badge ${selectedUAVData.status}`} />
            </div>

            <div style={{ padding: "0 4px" }}>
              <div className="detail-row">
                <span className="detail-label">Status</span>
                <span className="detail-value">{selectedUAVData.status}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Position</span>
                <span className="detail-value">
                  ({selectedUAVData.position.x.toFixed(1)}, {selectedUAVData.position.y.toFixed(1)})
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Altitude</span>
                <span className="detail-value">{selectedUAVData.altitude.toFixed(1)}m</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Velocity</span>
                <span className="detail-value">{selectedUAVData.velocity.toFixed(1)} m/s</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Heading</span>
                <span className="detail-value">{selectedUAVData.heading.toFixed(0)}°</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Battery</span>
                <span
                  className="detail-value"
                  style={{
                    color:
                      selectedUAVData.battery > 50
                        ? "var(--status-active)"
                        : selectedUAVData.battery > 25
                        ? "var(--status-warning)"
                        : "var(--status-error)",
                  }}
                >
                  {selectedUAVData.battery.toFixed(1)}%
                </span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Temperature</span>
                <span className="detail-value">{selectedUAVData.temperature.toFixed(1)}°C</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">GPS Sats</span>
                <span className="detail-value">{selectedUAVData.gps_satellites}</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Signal</span>
                <span className="detail-value">{selectedUAVData.signal_strength.toFixed(0)} dBm</span>
              </div>
              <div className="detail-row">
                <span className="detail-label">Health</span>
                <span
                  className="detail-value"
                  style={{
                    color: selectedUAVData.health.motors_ok &&
                      selectedUAVData.health.gps_ok &&
                      selectedUAVData.health.comms_ok
                      ? "var(--status-active)"
                      : "var(--status-error)",
                  }}
                >
                  {selectedUAVData.health.motors_ok &&
                  selectedUAVData.health.gps_ok &&
                  selectedUAVData.health.comms_ok
                    ? "HEALTHY"
                    : "DEGRADED"}
                </span>
              </div>
            </div>

            {/* Failure Injection */}
            <div className="panel-header" style={{ marginTop: 12 }}>
              <span className="panel-title" style={{ color: "var(--status-error)" }}>
                Inject Failure
              </span>
            </div>
            <div className="failure-panel">
              <button
                className="failure-btn"
                onClick={() => handleInjectFailure(selectedUAVData.id, "LOW_BATTERY", 18)}
              >
                🔋 Battery → 18%
              </button>
              <button
                className="failure-btn"
                onClick={() => handleInjectFailure(selectedUAVData.id, "OFFLINE")}
              >
                📡 Set Offline
              </button>
              <button
                className="failure-btn"
                onClick={() => handleInjectFailure(selectedUAVData.id, "GPS_DEGRADATION", 2)}
              >
                🛰️ GPS → 2 sats
              </button>
              <button
                className="failure-btn"
                onClick={() => handleInjectFailure(selectedUAVData.id, "HIGH_TEMPERATURE", 85)}
              >
                🌡️ Temp → 85°C
              </button>
              <button
                className="failure-btn"
                onClick={() => handleInjectFailure(selectedUAVData.id, "MOTOR_FAILURE")}
              >
                ⚙️ Motor Failure
              </button>
              <button
                className="failure-btn"
                onClick={() => handleInjectFailure(selectedUAVData.id, "SIGNAL_LOSS", -95)}
              >
                📶 Signal Loss
              </button>
            </div>
          </div>
        ) : (
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">UAV Details</span>
            </div>
            <div
              style={{
                padding: 20,
                textAlign: "center",
                color: "var(--text-muted)",
                fontSize: 12,
              }}
            >
              Select a UAV from the fleet list or map to view details and inject failures
            </div>
          </div>
        )}
      </div>

      {/* ── Footer: Timeline / Approvals / Decisions ── */}
      <div className="gcs-footer">
        <div style={{ display: "flex", borderBottom: "1px solid var(--border-primary)" }}>
          {(["timeline", "approvals", "decisions"] as const).map((tab) => (
            <button
              key={tab}
              className="btn btn-outline"
              style={{
                borderRadius: 0,
                borderBottom: activeTab === tab ? "2px solid var(--accent-blue)" : "2px solid transparent",
                color: activeTab === tab ? "var(--accent-blue)" : "var(--text-muted)",
                flex: 1,
              }}
              onClick={() => setActiveTab(tab)}
            >
              {tab === "timeline" ? `Timeline (${events.length})` : tab === "approvals" ? `Approvals (${approvals.length})` : `Agent Decisions (${decisions.length})`}
            </button>
          ))}
        </div>

        <div style={{ overflow: "auto", maxHeight: 180 }}>
          {activeTab === "timeline" &&
            events
              .slice()
              .reverse()
              .map((evt) => (
                <div key={evt.id} className={`event-item ${evt.severity}`}>
                  <span className="event-time">
                    {new Date(evt.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="event-message">
                    {evt.uav_id && <strong>[{evt.uav_id}] </strong>}
                    {evt.message}
                  </span>
                  <span style={{ fontSize: 9, color: "var(--text-muted)" }}>
                    {evt.component}
                  </span>
                </div>
              ))}

          {activeTab === "approvals" &&
            (approvals.length > 0 ? (
              approvals.map((a) => (
                <div key={a.action_id} className="approval-banner">
                  <div className="message">
                    <strong>{a.action}</strong> for {a.uav_id || "system"} — {a.reason}
                    <span style={{ fontSize: 10, marginLeft: 8, color: "var(--text-muted)" }}>
                      Source: {a.source}
                    </span>
                  </div>
                  <div className="approval-actions">
                    <button className="btn btn-success" onClick={() => handleActionApproval(a.action_id, "APPROVED")}>
                      Approve
                    </button>
                    <button className="btn btn-danger" onClick={() => handleActionApproval(a.action_id, "REJECTED")}>
                      Reject
                    </button>
                  </div>
                </div>
              ))
            ) : (
              <div style={{ padding: 16, textAlign: "center", color: "var(--text-muted)", fontSize: 12 }}>
                No pending approvals
              </div>
            ))}

          {activeTab === "decisions" &&
            (decisions.length > 0 ? (
              decisions
                .slice()
                .reverse()
                .map((dec) => (
                  <div key={dec.id} className="card" style={{ margin: "6px 12px", cursor: "default" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span
                        style={{
                          fontSize: 10,
                          padding: "1px 8px",
                          borderRadius: 3,
                          background:
                            dec.agent_type === "MISSION_PLANNER"
                              ? "rgba(59,130,246,0.2)"
                              : dec.agent_type === "TASK_ALLOCATOR"
                              ? "rgba(139,92,246,0.2)"
                              : dec.agent_type === "SAFETY_AGENT"
                              ? "rgba(239,68,68,0.2)"
                              : "rgba(16,185,129,0.2)",
                          color:
                            dec.agent_type === "MISSION_PLANNER"
                              ? "var(--accent-blue)"
                              : dec.agent_type === "TASK_ALLOCATOR"
                              ? "var(--accent-purple)"
                              : dec.agent_type === "SAFETY_AGENT"
                              ? "var(--status-error)"
                              : "var(--accent-emerald)",
                          fontWeight: 600,
                        }}
                      >
                        {dec.agent_type.replace("_", " ")}
                      </span>
                      <span style={{ fontSize: 9, color: "var(--text-muted)", fontFamily: "'JetBrains Mono', monospace" }}>
                        {new Date(dec.timestamp).toLocaleTimeString()}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, fontWeight: 600, marginBottom: 2 }}>
                      {dec.decision}
                    </div>
                    <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 4 }}>
                      <strong>Reasoning:</strong> {dec.reason}
                    </div>
                    {dec.tools_called.length > 0 && (
                      <div style={{ fontSize: 9, color: "var(--text-muted)" }}>
                        Tools: {dec.tools_called.join(", ")}
                      </div>
                    )}
                  </div>
                ))
            ) : (
              <div style={{ padding: 16, textAlign: "center", color: "var(--text-muted)", fontSize: 12 }}>
                No agent decisions yet. Create and approve a mission to see agent reasoning.
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
