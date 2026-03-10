"""Tests für das DFlowP Event-System."""

import asyncio
from datetime import datetime, timezone

import pytest

from dflowp.core.events.event_bus import EventBus
from dflowp.core.events.event_service import EventService, get_event_service
from dflowp.core.events.event_types import (
    EVENT_COMPLETED,
    EVENT_FAILED,
    EVENT_STARTED,
)


@pytest.mark.asyncio
async def test_event_bus_publish_subscribe(event_bus_fresh):
    """Testet Publish und Subscribe ohne Persistenz."""
    bus = event_bus_fresh
    received: list[dict] = []

    async def handler(evt: dict):
        received.append(evt)

    bus.subscribe(EVENT_STARTED, handler)
    await bus.publish({
        "process_id": "p1",
        "subprocess_id": "s1",
        "event_type": EVENT_STARTED,
        "event_time": datetime.now(timezone.utc),
    })

    assert len(received) == 1
    assert received[0]["process_id"] == "p1"
    assert received[0]["subprocess_id"] == "s1"
    assert received[0]["event_type"] == EVENT_STARTED


@pytest.mark.asyncio
async def test_event_bus_multiple_handlers(event_bus_fresh):
    """Testet ob mehrere Handler für denselben Event-Typ aufgerufen werden."""
    bus = event_bus_fresh
    r1: list[dict] = []
    r2: list[dict] = []

    async def h1(evt: dict):
        r1.append(evt)

    async def h2(evt: dict):
        r2.append(evt)

    bus.subscribe(EVENT_COMPLETED, h1)
    bus.subscribe(EVENT_COMPLETED, h2)

    await bus.publish({
        "process_id": "p2",
        "subprocess_id": "s2",
        "event_type": EVENT_COMPLETED,
        "event_time": datetime.now(timezone.utc),
    })

    assert len(r1) == 1
    assert len(r2) == 1
    assert r1[0]["event_type"] == EVENT_COMPLETED
    assert r2[0]["event_type"] == EVENT_COMPLETED


@pytest.mark.asyncio
async def test_event_bus_wildcard_subscribe(event_bus_fresh):
    """Testet Wildcard-Subscribe (*) für alle Event-Typen."""
    bus = event_bus_fresh
    received: list[dict] = []

    async def handler(evt: dict):
        received.append(evt)

    bus.subscribe("*", handler)
    await bus.publish({
        "process_id": "p3",
        "subprocess_id": "s3",
        "event_type": EVENT_FAILED,
        "event_time": datetime.now(timezone.utc),
    })

    assert len(received) == 1
    assert received[0]["event_type"] == EVENT_FAILED


@pytest.mark.asyncio
async def test_event_service_emit_started():
    """Testet EventService.emit_started."""
    svc = get_event_service()
    received: list[dict] = []

    def handler(evt: dict):
        received.append(evt)

    svc.subscribe(EVENT_STARTED, handler)

    await svc.emit_started(
        process_id="proc_svc_1",
        subprocess_id="sub_svc_1",
        payload={"extra": "data"},
    )

    assert len(received) == 1
    assert received[0]["process_id"] == "proc_svc_1"
    assert received[0]["subprocess_id"] == "sub_svc_1"
    assert received[0]["event_type"] == EVENT_STARTED
    assert received[0].get("payload", {}).get("extra") == "data"
    assert "event_time" in received[0]


@pytest.mark.asyncio
async def test_event_service_emit_completed():
    """Testet EventService.emit_completed."""
    svc = get_event_service()
    received: list[dict] = []

    svc.subscribe(EVENT_COMPLETED, lambda e: received.append(e))

    await svc.emit_completed(
        process_id="proc_svc_2",
        subprocess_id="sub_svc_2",
    )

    assert len(received) == 1
    assert received[0]["event_type"] == EVENT_COMPLETED


@pytest.mark.asyncio
async def test_event_service_emit_failed():
    """Testet EventService.emit_failed mit Fehlermeldung."""
    svc = get_event_service()
    received: list[dict] = []

    svc.subscribe(EVENT_FAILED, lambda e: received.append(e))

    await svc.emit_failed(
        process_id="proc_svc_3",
        subprocess_id="sub_svc_3",
        error="Test-Fehler",
    )

    assert len(received) == 1
    assert received[0]["event_type"] == EVENT_FAILED
    assert received[0].get("payload", {}).get("error") == "Test-Fehler"


@pytest.mark.asyncio
async def test_event_bus_with_persistence(mongodb_connection):
    """Testet Event-Bus mit persistenter Speicherung in MongoDB."""
    from dflowp.infrastructure.database.event_repository import EventRepository

    bus = EventBus()  # Frischer Bus für isolierten Test
    repo = EventRepository()
    bus.set_event_repository(repo)
    await repo.create_indexes()

    received: list[dict] = []
    bus.subscribe(EVENT_STARTED, lambda e: received.append(e))

    await bus.publish({
        "process_id": "proc_persist_1",
        "subprocess_id": "sub_persist_1",
        "event_type": EVENT_STARTED,
        "subprocess_instance_id": 1,
    })

    assert len(received) == 1

    # Prüfen ob in DB gespeichert
    count = await repo.count_by_process("proc_persist_1")
    assert count >= 1

    events_from_db = []
    async for e in repo.find_by_process_id("proc_persist_1"):
        events_from_db.append(e)
    assert len(events_from_db) >= 1
    assert events_from_db[0]["event_type"] == EVENT_STARTED
