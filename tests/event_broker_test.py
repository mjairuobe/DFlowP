"""Tests für den Event-Broker."""

from datetime import datetime, timezone

import pytest

from dflowp.event_broker.app import EventBroker


class _FakeEventRepository:
    def __init__(self) -> None:
        self.failed: list[tuple[str, str]] = []
        self.delivered: list[str] = []

    async def list_undelivered_events(self, *, limit: int = 100) -> list[dict]:
        return [
            {
                "_id": "evt_001",
                "pipeline_id": "proc_1",
                "plugin_worker_id": "sub_1",
                "event_type": "EVENT_COMPLETED",
                "event_time": datetime.now(timezone.utc),
            }
        ]

    async def mark_delivered(self, event_id: str) -> bool:
        self.delivered.append(event_id)
        return True

    async def mark_delivery_failed(self, event_id: str, error: str) -> bool:
        self.failed.append((event_id, error))
        return True


class _FakeClient:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, _url: str, json: dict) -> object:
        class _Resp:
            def __init__(self, code: int) -> None:
                self.status_code = code
                self.text = "err"

        return _Resp(self.status_code)


@pytest.mark.asyncio
async def test_broker_marks_delivered_on_2xx(monkeypatch) -> None:
    repo = _FakeEventRepository()
    broker = EventBroker(
        eventsystem_url="http://eventsystem:8001",
        event_repository=repo,
    )

    monkeypatch.setattr("dflowp.event_broker.app.httpx.AsyncClient", lambda timeout: _FakeClient(204))

    delivered = await broker.run_once()
    assert delivered == 1
    assert repo.delivered == ["evt_001"]
    assert repo.failed == []


@pytest.mark.asyncio
async def test_broker_marks_failed_on_non_2xx(monkeypatch) -> None:
    repo = _FakeEventRepository()
    broker = EventBroker(
        eventsystem_url="http://eventsystem:8001",
        event_repository=repo,
    )

    monkeypatch.setattr("dflowp.event_broker.app.httpx.AsyncClient", lambda timeout: _FakeClient(500))

    delivered = await broker.run_once()
    assert delivered == 0
    assert repo.delivered == []
    assert len(repo.failed) == 1
