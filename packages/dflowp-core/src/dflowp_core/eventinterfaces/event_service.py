"""Event-Service - Emit und Subscribe für das Event-System."""

from datetime import datetime, timezone
from typing import Any, Callable, Optional

from dflowp_core.eventinterfaces.event_bus import get_event_bus
from dflowp_core.eventinterfaces.event_types import (
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_STARTED,
)


class EventService:
    """
    Zentraler Service zum Emitieren und Subscriben von Events.
    Nutzt den Event-Bus und stellt eine einfache API bereit.
    """

    def __init__(self) -> None:
        self._bus = get_event_bus()

    async def emit(
        self,
        process_id: str,
        subprocess_id: str,
        event_type: str,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        event_time: Optional[datetime] = None,
    ) -> None:
        """
        Sendet ein Event über den Event-Bus.

        Args:
            process_id: Eindeutige Prozess-ID
            subprocess_id: Eindeutige Teilprozess-ID
            event_type: EVENT_STARTED, EVENT_COMPLETED oder EVENT_FAILED
            subprocess_instance_id: Standardmäßig 1 (für spätere Parallelisierung)
            payload: Zusätzliche Event-Daten
            event_time: Zeitpunkt des Events (Default: jetzt)
        """
        event: dict[str, Any] = {
            "process_id": process_id,
            "subprocess_id": subprocess_id,
            "subprocess_instance_id": subprocess_instance_id,
            "event_type": event_type,
            "event_time": event_time or datetime.now(timezone.utc),
        }
        if payload:
            event["payload"] = payload

        await self._bus.publish(event)

    async def emit_started(
        self,
        process_id: str,
        subprocess_id: str,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emittiert EVENT_STARTED."""
        await self.emit(
            process_id=process_id,
            subprocess_id=subprocess_id,
            event_type=EVENT_STARTED,
            subprocess_instance_id=subprocess_instance_id,
            payload=payload,
        )

    async def emit_completed(
        self,
        process_id: str,
        subprocess_id: str,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        """Emittiert EVENT_COMPLETED."""
        await self.emit(
            process_id=process_id,
            subprocess_id=subprocess_id,
            event_type=EVENT_COMPLETED,
            subprocess_instance_id=subprocess_instance_id,
            payload=payload,
        )

    async def emit_failed(
        self,
        process_id: str,
        subprocess_id: str,
        subprocess_instance_id: int = 1,
        payload: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Emittiert EVENT_FAILED."""
        p = payload or {}
        if error:
            p["error"] = error
        await self.emit(
            process_id=process_id,
            subprocess_id=subprocess_id,
            event_type=EVENT_FAILED,
            subprocess_instance_id=subprocess_instance_id,
            payload=p if p else None,
        )

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[dict[str, Any]], Any],
    ) -> None:
        """
        Registriert einen Handler für einen Event-Typ.

        Args:
            event_type: EVENT_STARTED, EVENT_COMPLETED, EVENT_FAILED oder "*" für alle
            handler: Async-Funktion(event: dict)
        """
        self._bus.subscribe(event_type, handler)

    def set_event_repository(self, repository: Any) -> None:
        """Aktiviert die persistente Speicherung von Events."""
        self._bus.set_event_repository(repository)


def get_event_service() -> EventService:
    """Gibt eine Event-Service-Instanz zurück."""
    return EventService()
