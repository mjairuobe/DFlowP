"""Tests für den Runtime Event Listener."""

import pytest

from dflowp.worker import runtime_event_listener as rel


class _FakeEngine:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def handle_event_notification(self, event: dict) -> None:
        self.events.append(event)


class _FakeRuntime:
    def __init__(self) -> None:
        self.engine = _FakeEngine()


@pytest.mark.asyncio
async def test_runtime_listener_forwards_event_to_engine(monkeypatch) -> None:
    fake_runtime = _FakeRuntime()
    monkeypatch.setattr(rel, "_runtime", fake_runtime)

    payload = rel.RuntimeEventPayload(
        event_id="evt-1",
        process_id="proc-1",
        subprocess_id="sub-1",
        event_type="EVENT_COMPLETED",
        subprocess_instance_id=1,
        payload={"k": "v"},
    )
    await rel.receive_runtime_event(payload)

    assert len(fake_runtime.engine.events) == 1
    assert fake_runtime.engine.events[0]["event_type"] == "EVENT_COMPLETED"
    assert fake_runtime.engine.events[0]["payload"] == {"k": "v"}


class _FakeResponse:
    def __init__(self, status_code: int = 201) -> None:
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSubscribeClient:
    attempts = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def post(self, _url: str, json: dict):
        _FakeSubscribeClient.attempts += 1
        if _FakeSubscribeClient.attempts < 3:
            raise RuntimeError("temporary network error")
        return _FakeResponse(201)


@pytest.mark.asyncio
async def test_subscribe_runtime_retries_until_success(monkeypatch) -> None:
    _FakeSubscribeClient.attempts = 0
    monkeypatch.setattr(rel.httpx, "AsyncClient", lambda timeout: _FakeSubscribeClient())
    monkeypatch.setenv("DFLOWP_EVENTSYSTEM_SUBSCRIBE_RETRIES", "5")
    monkeypatch.setenv("DFLOWP_EVENTSYSTEM_SUBSCRIBE_RETRY_SLEEP", "0")

    await rel._subscribe_runtime()
    assert _FakeSubscribeClient.attempts == 3
