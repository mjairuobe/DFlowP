"""Event-Bus für In-Process-Kommunikation mit persistenter Speicherung."""

import asyncio
import json
from collections import defaultdict
from typing import Any, Callable, Optional

from dflowp_core.eventinterfaces.event_types import EVENT_TYPES
from dflowp_core.database.event_repository import EventRepository
from dflowp_core.utils.logger import get_component_logger

logger = get_component_logger("Eventsystem")

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
            event: Dict mit pipeline_id, plugin_worker_id, event_type, event_time, usw.
        """
        event_type = event.get("event_type")
        if not event_type:
            logger.warning("Event ohne event_type ignoriert: %s", event)
            return

        logger.info(json.dumps(event, default=str, ensure_ascii=False))

        # Persistenz
        if self._event_repository:
            async with self._lock:
                try:
                    await self._event_repository.insert(event.copy())
                except Exception as e:
                    logger.exception("Fehler beim Speichern des Events: %s", e)

        await self.dispatch_local(event)

    async def dispatch_local(self, event: dict[str, Any]) -> None:
        """
        Verteilt ein Event nur an lokale In-Memory-Subscriber.

        Diese Methode persistiert bewusst nicht und ist für DB-first Flows gedacht,
        in denen das Event bereits gespeichert wurde.
        """
        event_type = event.get("event_type")
        if not event_type:
            return

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
