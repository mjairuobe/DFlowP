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
    Persistierte Events nutzen ``pipeline_id`` und ``plugin_worker_id``.
    """

    def __init__(self) -> None:
        self._bus = get_event_bus()
        self._event_repository: Optional[Any] = None

    async def emit(
        self,
        pipeline_id: str,
        plugin_worker_id: str,
        event_type: str,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        event_time: Optional[datetime] = None,
    ) -> None:
        event: dict[str, Any] = {
            "pipeline_id": pipeline_id,
            "plugin_worker_id": plugin_worker_id,
            "subprocess_instance_id": subprocess_instance_id,
            "event_type": event_type,
            "event_time": event_time or datetime.now(timezone.utc),
            "process_id": pipeline_id,
            "subprocess_id": plugin_worker_id,
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
        pipeline_id: str | None = None,
        plugin_worker_id: str | None = None,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        *,
        process_id: str | None = None,
        subprocess_id: str | None = None,
    ) -> None:
        pid = pipeline_id or process_id
        wid = plugin_worker_id or subprocess_id
        if not pid or not wid:
            raise ValueError("pipeline_id/process_id und plugin_worker_id/subprocess_id erforderlich")
        await self.emit(
            pipeline_id=pid,
            plugin_worker_id=wid,
            event_type=EVENT_STARTED,
            subprocess_instance_id=subprocess_instance_id,
            payload=payload,
        )

    async def emit_completed(
        self,
        pipeline_id: str | None = None,
        plugin_worker_id: str | None = None,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        *,
        process_id: str | None = None,
        subprocess_id: str | None = None,
    ) -> None:
        pid = pipeline_id or process_id
        wid = plugin_worker_id or subprocess_id
        if not pid or not wid:
            raise ValueError("pipeline_id/process_id und plugin_worker_id/subprocess_id erforderlich")
        await self.emit(
            pipeline_id=pid,
            plugin_worker_id=wid,
            event_type=EVENT_COMPLETED,
            subprocess_instance_id=subprocess_instance_id,
            payload=payload,
        )

    async def emit_failed(
        self,
        pipeline_id: str | None = None,
        plugin_worker_id: str | None = None,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
        *,
        process_id: str | None = None,
        subprocess_id: str | None = None,
    ) -> None:
        pid = pipeline_id or process_id
        wid = plugin_worker_id or subprocess_id
        if not pid or not wid:
            raise ValueError("pipeline_id/process_id und plugin_worker_id/subprocess_id erforderlich")
        p = payload or {}
        if error:
            p["error"] = error
        await self.emit(
            pipeline_id=pid,
            plugin_worker_id=wid,
            event_type=EVENT_FAILED,
            subprocess_instance_id=subprocess_instance_id,
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


def get_event_service() -> EventService:
    return EventService()
