"""Einfaches Eventsystem zum Entgegennehmen und Verteilen weitergeleiteter Events."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import FastAPI, status
from pydantic import AnyHttpUrl, BaseModel, Field

from dflowp_core.utils.logger import get_component_logger

logger = get_component_logger("EventSystem")
app = FastAPI(title="DFlowP EventSystem", version="1.0.0")

_SUBSCRIBERS: dict[str, str] = {}


def _event_time_human(event: dict[str, Any]) -> str:
    raw = event.get("event_time")
    if isinstance(raw, datetime):
        dt = raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z").replace("UTC", "UTC")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    ts_ms = event.get("timestamp_ms")
    if ts_ms is not None:
        try:
            dt = datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except (TypeError, ValueError, OSError):
            pass
    return "?"


def _plugin_type_from_event(event: dict[str, Any]) -> str:
    payload = event.get("payload")
    if isinstance(payload, dict):
        st = payload.get("plugin_type")
        if st is not None:
            return str(st)
    return "-"


def _event_context_line(prefix: str, event: dict[str, Any], *, event_id: Optional[Any] = None) -> str:
    eid = event_id if event_id is not None else event.get("event_id", "?")
    return (
        f"{prefix} "
        f"pipeline_id={event.get('pipeline_id')!r} "
        f"plugin_worker_id={event.get('plugin_worker_id')!r} "
        f"plugin_type={_plugin_type_from_event(event)!r} "
        f"event_type={event.get('event_type')!r} "
        f"event_time={_event_time_human(event)!r} "
        f"event_id={eid!r}"
    )


class SubscriberRegistration(BaseModel):
    subscriber_id: str = Field(..., description="Stabile Subscriber-ID (z. B. runtime-1)")
    callback_url: AnyHttpUrl = Field(..., description="Callback-URL für Event-Notifications")


@app.post("/internal/subscriptions", status_code=status.HTTP_201_CREATED)
async def register_subscriber(registration: SubscriberRegistration) -> dict[str, Any]:
    callback_url = str(registration.callback_url).rstrip("/")
    _SUBSCRIBERS[registration.subscriber_id] = callback_url
    logger.info(
        "Subscribed subscriber_id=%r callback_url=%r (total=%d)",
        registration.subscriber_id,
        callback_url,
        len(_SUBSCRIBERS),
    )
    return {"status": "registered", "subscriber_count": len(_SUBSCRIBERS)}


@app.get("/internal/subscriptions", status_code=status.HTTP_200_OK)
async def list_subscribers() -> dict[str, Any]:
    subscribers = [
        {"subscriber_id": subscriber_id, "callback_url": callback_url}
        for subscriber_id, callback_url in sorted(_SUBSCRIBERS.items())
    ]
    return {"subscribers": subscribers, "subscriber_count": len(_SUBSCRIBERS)}


@app.post("/internal/events", status_code=status.HTTP_204_NO_CONTENT)
async def receive_event(event: dict) -> None:
    """
    Nimmt vom Event-Broker weitergeleitete Events entgegen und broadcastet sie.
    """
    logger.info(_event_context_line("Published", event))

    if not _SUBSCRIBERS:
        return None

    timeout = float(os.environ.get("DFLOWP_EVENTSYSTEM_NOTIFY_TIMEOUT", "10.0"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        for subscriber_id, callback_url in list(_SUBSCRIBERS.items()):
            try:
                response = await client.post(callback_url, json=event)
                if 200 <= response.status_code < 300:
                    logger.info(
                        "%s | subscriber_id=%r callback_url=%r http_status=%s",
                        _event_context_line("Notified", event),
                        subscriber_id,
                        callback_url,
                        response.status_code,
                    )
                    continue
                logger.warning(
                    "%s | subscriber_id=%r callback_url=%r http_status=%s",
                    _event_context_line("Notify failed", event),
                    subscriber_id,
                    callback_url,
                    response.status_code,
                )
            except Exception as exc:
                logger.warning(
                    "%s | subscriber_id=%r callback_url=%r error=%s",
                    _event_context_line("Notify failed", event),
                    subscriber_id,
                    callback_url,
                    exc,
                )
    return None
