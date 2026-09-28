"use client";

import { useEffect, useRef } from "react";
import L from "leaflet";
import type { UAVState, WorldData, MissionPlan } from "../types";

interface UAVMapProps {
  uavs: UAVState[];
  world: WorldData | null;
  selectedUAV: string | null;
  onSelectUAV: (id: string) => void;
  missions: MissionPlan[];
}

// Status → color mapping
const STATUS_COLORS: Record<string, string> = {
  IDLE: "#6b7280",
  ARMED: "#f59e0b",
  TAKEOFF: "#06b6d4",
  ACTIVE: "#22c55e",
  HOVERING: "#10b981",
  RETURNING: "#f59e0b",
  LANDING: "#8b5cf6",
  LANDED: "#6b7280",
  LOW_BATTERY: "#f59e0b",
  EMERGENCY: "#ef4444",
  OFFLINE: "#dc2626",
  FAILED: "#ef4444",
};

function createUAVIcon(uav: UAVState, isSelected: boolean): L.DivIcon {
  const color = STATUS_COLORS[uav.status] || "#6b7280";
  const size = isSelected ? 28 : 22;
  const battColor = uav.battery > 50 ? "#22c55e" : uav.battery > 25 ? "#f59e0b" : "#ef4444";

  return L.divIcon({
    className: "",
    iconSize: [size + 40, size + 16],
    iconAnchor: [(size + 40) / 2, (size + 16) / 2],
    html: `
      <div style="display:flex;flex-direction:column;align-items:center;pointer-events:auto;">
        <div style="
          width:${size}px;height:${size}px;
          background:${color};
          border:2px solid ${isSelected ? "#fff" : "rgba(255,255,255,0.3)"};
          border-radius:50%;
          display:flex;align-items:center;justify-content:center;
          font-size:8px;font-weight:700;color:white;
          box-shadow:0 0 ${isSelected ? 12 : 6}px ${color};
          transform:rotate(${uav.heading}deg);
          cursor:pointer;
          position:relative;
        ">
          <div style="transform:rotate(-${uav.heading}deg);font-size:7px;">
            ${uav.id.replace("UAV-", "")}
          </div>
          <div style="
            position:absolute;top:-2px;right:-2px;
            width:6px;height:6px;border-radius:50%;
            background:${battColor};
            border:1px solid rgba(0,0,0,0.3);
          "></div>
        </div>
        <div style="
          font-size:8px;color:#94a3b8;margin-top:1px;
          text-align:center;font-family:'JetBrains Mono',monospace;
          background:rgba(10,14,23,0.8);padding:0 3px;border-radius:2px;
        ">${uav.id}</div>
      </div>
    `,
  });
}

export default function UAVMap({ uavs, world, selectedUAV, onSelectUAV, missions }: UAVMapProps) {
  const mapRef = useRef<L.Map | null>(null);
  const markersRef = useRef<Map<string, L.Marker>>(new Map());
  const sectorsRef = useRef<L.Rectangle[]>([]);
  const geofenceRef = useRef<L.Rectangle | null>(null);
  const waypointsRef = useRef<L.CircleMarker[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  // Initialize map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    // We use a CRS.Simple since we have a simulated x,y coordinate space
    const map = L.map(containerRef.current, {
      crs: L.CRS.Simple,
      minZoom: -2,
      maxZoom: 2,
      zoomControl: true,
      attributionControl: false,
    });

    // Set initial view to cover the simulated world
    const bounds: L.LatLngBoundsExpression = [
      [-100, -100],
      [700, 900],
    ];
    map.fitBounds(bounds);

    // Grid background
    const gridGroup = L.layerGroup().addTo(map);
    for (let x = -100; x <= 900; x += 50) {
      L.polyline(
        [
          [x, -100],
          [x, 700],
        ] as L.LatLngExpression[],
        { color: "#1e3a5f", weight: 0.3, opacity: 0.5 }
      ).addTo(gridGroup);
    }
    for (let y = -100; y <= 700; y += 50) {
      L.polyline(
        [
          [-100, y],
          [900, y],
        ] as L.LatLngExpression[],
        { color: "#1e3a5f", weight: 0.3, opacity: 0.5 }
      ).addTo(gridGroup);
    }

    // Home base indicator
    L.circleMarker([0, 0] as L.LatLngExpression, {
      radius: 8,
      fillColor: "#3b82f6",
      color: "#60a5fa",
      weight: 2,
      fillOpacity: 0.5,
    }).addTo(map).bindTooltip("HOME BASE", {
      permanent: true,
      direction: "top",
      className: "uav-tooltip",
      offset: [0, -10],
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Draw sectors and geofence when world data arrives
  useEffect(() => {
    if (!mapRef.current || !world) return;
    const map = mapRef.current;

    // Clear old
    sectorsRef.current.forEach((r) => map.removeLayer(r));
    sectorsRef.current = [];
    waypointsRef.current.forEach((m) => map.removeLayer(m));
    waypointsRef.current = [];
    if (geofenceRef.current) map.removeLayer(geofenceRef.current);

    // Draw geofence
    const gf = world.geofence;
    geofenceRef.current = L.rectangle(
      [
        [gf.min_y, gf.min_x],
        [gf.max_y, gf.max_x],
      ],
      {
        color: "#dc2626",
        weight: 1.5,
        fillOpacity: 0,
        dashArray: "8,4",
      }
    ).addTo(map);

    // Draw sectors
    const sectorColors: Record<string, string> = {
      SECTOR_A: "#3b82f6",
      SECTOR_B: "#8b5cf6",
      SECTOR_C: "#10b981",
    };

    Object.values(world.sectors).forEach((sector) => {
      const color = sectorColors[sector.name] || "#6b7280";
      const rect = L.rectangle(
        [
          [sector.center_y - sector.height / 2, sector.center_x - sector.width / 2],
          [sector.center_y + sector.height / 2, sector.center_x + sector.width / 2],
        ],
        {
          color,
          weight: 1.5,
          fillColor: color,
          fillOpacity: 0.08,
          dashArray: "4,4",
        }
      ).addTo(map);
      rect.bindTooltip(sector.label, {
        permanent: true,
        direction: "center",
        className: "uav-tooltip",
      });
      sectorsRef.current.push(rect);

      // Draw waypoints
      sector.waypoints.forEach((wp) => {
        const marker = L.circleMarker([wp.y, wp.x], {
          radius: 4,
          fillColor: color,
          color: "rgba(255,255,255,0.3)",
          weight: 1,
          fillOpacity: 0.6,
        }).addTo(map);
        marker.bindTooltip(wp.name, {
          direction: "top",
          className: "uav-tooltip",
          offset: [0, -6],
        });
        waypointsRef.current.push(marker);
      });
    });
  }, [world]);

  // Update UAV markers
  useEffect(() => {
    if (!mapRef.current) return;
    const map = mapRef.current;
    const currentMarkers = markersRef.current;
    const activeIds = new Set(uavs.map((u) => u.id));

    // Remove markers for UAVs that no longer exist
    currentMarkers.forEach((marker, id) => {
      if (!activeIds.has(id)) {
        map.removeLayer(marker);
        currentMarkers.delete(id);
      }
    });

    // Update or create markers
    uavs.forEach((uav) => {
      const pos: L.LatLngExpression = [uav.position.y, uav.position.x];
      const isSelected = selectedUAV === uav.id;
      const icon = createUAVIcon(uav, isSelected);

      const existing = currentMarkers.get(uav.id);
      if (existing) {
        existing.setLatLng(pos);
        existing.setIcon(icon);
      } else {
        const marker = L.marker(pos, { icon })
          .addTo(map)
          .on("click", () => onSelectUAV(uav.id));
        currentMarkers.set(uav.id, marker);
      }
    });
  }, [uavs, selectedUAV, onSelectUAV]);

  return <div ref={containerRef} style={{ width: "100%", height: "100%" }} />;
}
