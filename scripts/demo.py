#!/usr/bin/env python3
"""Demo script — Runs through a complete mission lifecycle.

Usage:
    python -m scripts.demo

This script demonstrates:
1. Creating a mission from natural language
2. Viewing the planned mission
3. Approving and executing it
4. Monitoring UAV telemetry
5. Injecting a failure and seeing safety response
"""

import asyncio
import json
import sys

import httpx

API = "http://localhost:8000"


async def main() -> None:
    async with httpx.AsyncClient(base_url=API, timeout=30) as client:
        print("=" * 60)
        print("  AeroMind — Demo Script")
        print("=" * 60)

        # 1. Health check
        print("\n📡 Checking system health...")
        resp = await client.get("/api/health")
        health = resp.json()
        print(f"   Status: {health['status']}")
        print(f"   UAVs: {health['uavs']}")
        print(f"   Active missions: {health['active_missions']}")

        # 2. Show fleet status
        print("\n🛸 Fleet Status:")
        resp = await client.get("/api/uavs")
        uavs = resp.json()["uavs"]
        for uav in uavs[:5]:
            print(f"   {uav['id']}: {uav['status']} | Battery: {uav['battery']:.0f}% | Pos: ({uav['position']['x']:.0f}, {uav['position']['y']:.0f})")
        if len(uavs) > 5:
            print(f"   ... and {len(uavs) - 5} more")

        # 3. Create mission
        print("\n📋 Creating inspection mission for Sector A...")
        resp = await client.post("/api/missions", json={
            "natural_language": "Deploy 5 UAVs to inspect Sector A for structural damage",
            "mission_type": "INSPECTION",
            "area": "SECTOR_A",
            "required_uavs": 5,
            "title": "Sector A Structural Inspection",
        })
        mission = resp.json()["mission"]
        mission_id = mission["mission_id"]
        print(f"   Mission ID: {mission_id}")
        print(f"   Status: {mission['status']}")
        print(f"   Tasks: {len(mission['tasks'])}")
        for task in mission["tasks"]:
            print(f"   • {task['waypoint']['name']} → {task.get('uav_id', 'Unassigned')}")

        # 4. Approve mission
        if mission["status"] == "AWAITING_APPROVAL":
            print("\n✅ Approving mission...")
            resp = await client.post(f"/api/missions/{mission_id}/approve")
            approved = resp.json()["mission"]
            print(f"   Status: {approved['status']}")

        # 5. Wait and check progress
        print("\n⏳ Monitoring mission progress (10 seconds)...")
        for i in range(5):
            await asyncio.sleep(2)
            resp = await client.get(f"/api/missions/{mission_id}")
            m = resp.json()["mission"]
            print(f"   [{i*2+2}s] Status: {m['status']} | Progress: {m['progress_percent']:.0f}%")

        # 6. Show events
        print("\n📜 Recent Events:")
        resp = await client.get("/api/events?limit=10")
        events = resp.json()["events"]
        for evt in events[-5:]:
            prefix = "⚠️" if evt["severity"] in ("WARNING", "ERROR", "CRITICAL") else "ℹ️"
            print(f"   {prefix} [{evt['event_type']}] {evt['message']}")

        # 7. Inject a failure
        print("\n💥 Injecting battery failure into UAV-01...")
        resp = await client.post("/api/simulation/uavs/UAV-01/inject-failure", json={
            "failure_type": "LOW_BATTERY",
            "value": 18.0,
        })
        print(f"   {resp.json()['message']}")

        # 8. Wait for safety detection
        await asyncio.sleep(3)

        # 9. Show incidents
        print("\n🚨 Safety Incidents:")
        resp = await client.get("/api/events/incidents?limit=5")
        incidents = resp.json()["incidents"]
        if incidents:
            for inc in incidents[-3:]:
                print(f"   [{inc['incident_type']}] {inc['message']} (severity: {inc['severity']})")
        else:
            print("   No incidents (monitoring interval may not have triggered yet)")

        # 10. Check agent decisions
        print("\n🧠 Agent Decisions:")
        resp = await client.get("/api/events/agent-decisions")
        decisions = resp.json()["decisions"]
        for dec in decisions[-3:]:
            print(f"   [{dec['agent_type']}] {dec['decision']}")
            print(f"      Reason: {dec['reason']}")

        print("\n" + "=" * 60)
        print("  Demo Complete ✓")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
