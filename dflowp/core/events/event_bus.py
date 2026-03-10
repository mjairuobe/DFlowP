"""Event-Bus für In-Process-Kommunikation mit persistenter Speicherung."""

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Optional

from dflowp.core.events.event_types import EVENT_TYPES
from dflowp.infrastructure.database.event_repository import EventRepository
from dflowp.utils.logger import get_logger

logger = get_logger(__name__)

# Typ für Event-Handler (async callable)
EventEventHandler = Callable[[dict[str, Any]], Any]


class EventBus:
    """
    Event-Bus für DFlowP.
    Kombiniert In-Memory Publish/Subscribe mit persistenter Speicherung in MongoDB.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[EventEventHandler]] = defaultdict(list)
        self._event_repository: Optional[EventRepository] = None
        self._lock = asyncio.Lock()

    def set_event_repository(self, repository: EventRepository) -> None:
        """Setzt das Event-Repository für persistente Speicherung."""
        self._event_repository = repository

    def subscribe(
        self,
        event_type: str,
        handler: EventEventHandler,
    ) -> None:
        """
        Registriert einen Handler für einen Event-Typ.

        Args:
            event_type: Z.B. EVENT_STARTED, EVENT_COMPLETED, EVENT_FAILED
            handler: Async-Funktion, die (event: dict) empfängt
        """
        if event_type not in EVENT_TYPES:
            logger.warning("Unbekannter Event-Typ: %s", event_type)
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: EventEventHandler) -> bool:
        """Entfernt einen Handler."""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            return True
        return False

    async def publish(self, event: dict[str, Any]) -> None:
        """
        Veröffentlicht ein Event:
        1. Speichert es in MongoDB (falls Repository gesetzt)
        2. Ruft alle registrierten Handler auf

        Args:
            event: Dict mit process_id, subprocess_id, event_type, event_time, etc.
        """
        event_type = event.get("event_type")
        if not event_type:
            logger.warning("Event ohne event_type ignoriert: %s", event)
            return

        # Persistenz
        if self._event_repository:
            async with self._lock:
                try:
                    await self._event_repository.insert(event.copy())
                except Exception as e:
                    logger.exception("Fehler beim Speichern des Events: %s", e)

        # In-Memory Publish
        handlers = self._subscribers.get(event_type, []) + self._subscribers.get("*", [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.exception("Fehler im Event-Handler für %s: %s", event_type, e)


# Singleton für den gesamten Event-Bus
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Gibt die globale Event-Bus-Instanz zurück."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus
