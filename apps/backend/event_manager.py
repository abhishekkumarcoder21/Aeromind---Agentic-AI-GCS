"""Event Manager — Central hub for mission events, incidents, and pub/sub.

Collects events from all components, persists them, and broadcasts
via Redis pub/sub and WebSocket connections.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable

from packages.schemas.aeromind_schemas.events import EventSeverity, EventType, MissionEvent, Incident

logger = logging.getLogger("aeromind.events")


class EventManager:
    """Centralized event handling.

    Receives events from simulator, agents, safety engine, and execution engine.
    Stores them in memory (and optionally persists to DB), and broadcasts to
    registered listeners and WebSocket connections.
    """

    def __init__(self) -> None:
        self._events: list[MissionEvent] = []
        self._incidents: list[Incident] = []
        self._listeners: list[Callable] = []
        self._incident_listeners: list[Callable] = []
        self._redis = None

    def set_redis(self, redis_client: Any) -> None:
        """Set the Redis client for pub/sub broadcasting."""
        self._redis = redis_client

    def on_event(self, callback: Callable) -> None:
        """Register an event listener."""
        self._listeners.append(callback)

    def on_incident(self, callback: Callable) -> None:
        """Register an incident listener."""
        self._incident_listeners.append(callback)

    async def emit(
        self,
        event_type: EventType,
        message: str,
        severity: EventSeverity = EventSeverity.INFO,
        mission_id: str | None = None,
        uav_id: str | None = None,
        task_id: str | None = None,
        details: dict | None = None,
        component: str = "SYSTEM",
    ) -> MissionEvent:
        """Create and broadcast a mission event."""
        event = MissionEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            mission_id=mission_id,
            uav_id=uav_id,
            task_id=task_id,
            details=details or {},
            component=component,
        )
        self._events.append(event)

        # Keep only last 10000 events in memory
        if len(self._events) > 10000:
            self._events = self._events[-5000:]

        # Notify listeners
        for listener in self._listeners:
            try:
                result = listener(event)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception("Event listener error")

        # Publish to Redis
        await self._publish_redis("aeromind:events", event.model_dump(mode="json"))

        logger.log(
            logging.WARNING if severity in {EventSeverity.WARNING, EventSeverity.ERROR, EventSeverity.CRITICAL} else logging.INFO,
            f"[{event_type.value}] {message}",
        )
        return event

    async def record_incident(self, incident: Incident) -> None:
        """Record a safety incident and broadcast it."""
        self._incidents.append(incident)

        # Keep only last 1000 incidents in memory
        if len(self._incidents) > 1000:
            self._incidents = self._incidents[-500:]

        for listener in self._incident_listeners:
            try:
                result = listener(incident)
                if hasattr(result, "__await__"):
                    await result
            except Exception:
                logger.exception("Incident listener error")

        await self._publish_redis("aeromind:incidents", incident.model_dump(mode="json"))

        await self.emit(
            event_type=EventType.SAFETY_INCIDENT,
            message=incident.message,
            severity=incident.severity,
            uav_id=incident.uav_id,
            mission_id=incident.mission_id,
            details=incident.details,
            component="SAFETY_ENGINE",
        )

    async def _publish_redis(self, channel: str, data: dict) -> None:
        """Publish data to a Redis pub/sub channel."""
        if self._redis:
            try:
                await self._redis.publish(channel, json.dumps(data, default=str))
            except Exception:
                logger.exception(f"Redis publish error on {channel}")

    def get_events(
        self,
        mission_id: str | None = None,
        uav_id: str | None = None,
        event_type: EventType | None = None,
        limit: int = 100,
    ) -> list[MissionEvent]:
        """Query in-memory events with optional filters."""
        events = self._events
        if mission_id:
            events = [e for e in events if e.mission_id == mission_id]
        if uav_id:
            events = [e for e in events if e.uav_id == uav_id]
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        return events[-limit:]

    def get_incidents(
        self,
        uav_id: str | None = None,
        resolved: bool | None = None,
        limit: int = 50,
    ) -> list[Incident]:
        """Query in-memory incidents."""
        incidents = self._incidents
        if uav_id:
            incidents = [i for i in incidents if i.uav_id == uav_id]
        if resolved is not None:
            incidents = [i for i in incidents if i.resolved == resolved]
        return incidents[-limit:]
