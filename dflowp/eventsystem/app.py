"""Einfaches Eventsystem zum Entgegennehmen und Verteilen weitergeleiteter Events."""

from __future__ import annotations

import os
from typing import Any

import httpx
from fastapi import FastAPI, status
from pydantic import AnyHttpUrl, BaseModel, Field

from dflowp_core.utils.logger import get_component_logger

logger = get_component_logger("EventSystem")
app = FastAPI(title="DFlowP EventSystem", version="1.0.0")

_SUBSCRIBERS: dict[str, str] = {}


class SubscriberRegistration(BaseModel):
    subscriber_id: str = Field(..., description="Stabile Subscriber-ID (z. B. runtime-1)")
    callback_url: AnyHttpUrl = Field(..., description="Callback-URL für Event-Notifications")


@app.post("/internal/subscriptions", status_code=status.HTTP_201_CREATED)
async def register_subscriber(registration: SubscriberRegistration) -> dict[str, Any]:
    callback_url = str(registration.callback_url).rstrip("/")
    _SUBSCRIBERS[registration.subscriber_id] = callback_url
    logger.info("Subscriber registriert: %s -> %s", registration.subscriber_id, callback_url)
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
    logger.info("Event empfangen: %s", event.get("event_type"))
    if not _SUBSCRIBERS:
        return None

    timeout = float(os.environ.get("DFLOWP_EVENTSYSTEM_NOTIFY_TIMEOUT", "10.0"))
    async with httpx.AsyncClient(timeout=timeout) as client:
        for subscriber_id, callback_url in list(_SUBSCRIBERS.items()):
            try:
                response = await client.post(callback_url, json=event)
                if 200 <= response.status_code < 300:
                    continue
                logger.warning(
                    "Notify an %s fehlgeschlagen mit HTTP %s",
                    subscriber_id,
                    response.status_code,
                )
            except Exception as exc:
                logger.warning("Notify an %s fehlgeschlagen: %s", subscriber_id, exc)
    return None
