"""Event-Service - Emit und Subscribe für das Event-System."""
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from dflowp_core.eventinterfaces.event_bus import EventBus, get_event_bus
from dflowp_core.eventinterfaces.event_types import (
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_STARTED,
)


class EventService:
    """
    Zentraler Service zum Emitieren und Subscriben von Events.
    Persistierte Events nutzen ``pipeline_id``, ``plugin_worker_id``, ``plugin_worker_replica_id``.
    """

    def __init__(self, bus: Optional[EventBus] = None) -> None:
        self._bus = bus or get_event_bus()
        self._event_repository: Optional[Any] = None

    async def emit(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
        event_type: str,
        plugin_worker_replica_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        event_time: Optional[datetime] = None,
    ) -> None:
        event: dict[str, Any] = {
            "pipeline_id": pipeline_id,
            "plugin_worker_id": plugin_worker_id,
            "plugin_worker_replica_id": plugin_worker_replica_id,
            "event_type": event_type,
            "event_time": event_time or datetime.now(timezone.utc),
        }
        if payload:
            event["payload"] = payload

        event_repository = getattr(self, "_event_repository", None)
        if event_repository:
            await event_repository.insert(event)
            await self._bus.dispatch_local(event)
            return
        await self._bus.publish(event)

    async def emit_started(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
        plugin_worker_replica_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        await self.emit(
            pipeline_id=pipeline_id,
            plugin_worker_id=plugin_worker_id,
            event_type=EVENT_STARTED,
            plugin_worker_replica_id=plugin_worker_replica_id,
            payload=payload,
        )

    async def emit_completed(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
        plugin_worker_replica_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        await self.emit(
            pipeline_id=pipeline_id,
            plugin_worker_id=plugin_worker_id,
            event_type=EVENT_COMPLETED,
            plugin_worker_replica_id=plugin_worker_replica_id,
            payload=payload,
        )

    async def emit_failed(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
        plugin_worker_replica_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        p = payload or {}
        if error:
            p["error"] = error
        await self.emit(
            pipeline_id=pipeline_id,
            plugin_worker_id=plugin_worker_id,
            event_type=EVENT_FAILED,
            plugin_worker_replica_id=plugin_worker_replica_id,
            payload=p if p else None,
        )

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[dict[str, Any]], Any],
    ) -> None:
        self._bus.subscribe(event_type, handler)

    def set_event_repository(self, repository: Any) -> None:
        self._event_repository = repository


_event_service_singleton: Optional[EventService] = None


def get_event_service() -> EventService:
    """Gibt die globale EventService-Instanz (Runtime) zurück."""
    global _event_service_singleton
    if _event_service_singleton is None:
        _event_service_singleton = EventService()
    return _event_service_singleton
