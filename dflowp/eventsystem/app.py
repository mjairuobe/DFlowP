"""Einfaches Eventsystem zum Entgegennehmen weitergeleiteter Events."""

from __future__ import annotations

from fastapi import FastAPI, status

from dflowp_core.utils.logger import get_component_logger

logger = get_component_logger("EventSystem")
app = FastAPI(title="DFlowP EventSystem", version="1.0.0")


@app.post("/internal/events", status_code=status.HTTP_204_NO_CONTENT)
async def receive_event(event: dict) -> None:
    """
    Nimmt vom Event-Broker weitergeleitete Events entgegen.
    """
    logger.info("Event empfangen: %s", event.get("event_type"))
    return None
