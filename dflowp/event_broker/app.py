"""Event-Broker Service: liest undelivered Events aus DB und liefert per HTTP aus."""

import asyncio
import os
from datetime import datetime, timezone

import httpx

from dflowp_core.database.event_repository import EventRepository
from dflowp_core.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    resolve_mongodb_uri,
)
from dflowp_core.utils.logger import get_component_logger

logger = get_component_logger("EventBroker")


class EventBroker:
    """At-least-once Event-Broker auf Basis MongoDB + HTTP Forwarding."""

    def __init__(
        self,
        *,
        eventsystem_url: str,
        event_repository: EventRepository | None = None,
        poll_interval_seconds: float = 1.0,
        batch_size: int = 100,
        request_timeout_seconds: float = 10.0,
    ) -> None:
        self._eventsystem_url = eventsystem_url.rstrip("/")
        self._poll_interval_seconds = poll_interval_seconds
        self._batch_size = batch_size
        self._request_timeout_seconds = request_timeout_seconds
        self._event_repo: EventRepository | None = event_repository

    async def start(self) -> None:
        if self._event_repo is not None:
            logger.info("EventBroker gestartet (extern injiziertes EventRepository).")
            return
        uri = resolve_mongodb_uri()
        database_name = os.environ.get("MONGODB_DATABASE", "dflowp")
        await connect_to_mongodb(uri=uri, database_name=database_name)
        self._event_repo = EventRepository()
        await self._event_repo.create_indexes()
        logger.info(
            "EventBroker gestartet (eventsystem_url=%s, poll=%.2fs, batch=%d)",
            self._eventsystem_url,
            self._poll_interval_seconds,
            self._batch_size,
        )

    async def stop(self) -> None:
        await close_mongodb_connection()
        logger.info("EventBroker gestoppt.")

    async def run_forever(self) -> None:
        if self._event_repo is None:
            raise RuntimeError("EventBroker nicht gestartet. Rufe zuerst start() auf.")
        try:
            while True:
                delivered = await self.run_once()
                if delivered == 0:
                    await asyncio.sleep(self._poll_interval_seconds)
        except asyncio.CancelledError:
            logger.info("EventBroker beendet (cancelled).")
            raise

    async def run_once(self) -> int:
        if self._event_repo is None:
            raise RuntimeError("EventBroker nicht gestartet. Rufe zuerst start() auf.")

        events = await self._event_repo.list_undelivered_events(limit=self._batch_size)
        if not events:
            return 0

        delivered_count = 0
        async with httpx.AsyncClient(timeout=self._request_timeout_seconds) as client:
            for event in events:
                event_id = event.get("_id")
                if not event_id:
                    continue

                payload = {
                    "event_id": event_id,
                    "process_id": event.get("process_id"),
                    "subprocess_id": event.get("subprocess_id"),
                    "subprocess_instance_id": event.get("subprocess_instance_id", 1),
                    "event_type": event.get("event_type"),
                    "event_time": _serialize_event_time(event.get("event_time")),
                    "payload": event.get("payload"),
                    "timestamp_ms": event.get("timestamp_ms"),
                }

                try:
                    response = await client.post(
                        f"{self._eventsystem_url}/internal/events",
                        json=payload,
                    )
                    if 200 <= response.status_code < 300:
                        await self._event_repo.mark_delivered(event_id)
                        delivered_count += 1
                        continue

                    await self._event_repo.mark_delivery_failed(
                        event_id,
                        f"HTTP {response.status_code}: {response.text[:300]}",
                    )
                except Exception as exc:
                    await self._event_repo.mark_delivery_failed(event_id, str(exc))

        if delivered_count:
            logger.info("EventBroker ausgeliefert: %d Events", delivered_count)
        return delivered_count


def _serialize_event_time(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(value)


async def _main_async() -> None:
    broker = EventBroker(
        eventsystem_url=os.environ.get("DFLOWP_EVENTSYSTEM_URL", "http://eventsystem:8001"),
        poll_interval_seconds=float(os.environ.get("DFLOWP_EVENT_BROKER_POLL_SECONDS", "1.0")),
        batch_size=int(os.environ.get("DFLOWP_EVENT_BROKER_BATCH_SIZE", "100")),
        request_timeout_seconds=float(os.environ.get("DFLOWP_EVENT_BROKER_HTTP_TIMEOUT", "10.0")),
    )
    await broker.start()
    try:
        await broker.run_forever()
    finally:
        await broker.stop()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
