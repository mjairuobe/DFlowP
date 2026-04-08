"""HTTP Runtime Listener: empfängt Event-Notifications vom EventSystem."""

from __future__ import annotations

import asyncio
import json
import os
import signal
from pathlib import Path

import httpx
from fastapi import FastAPI, status
from pydantic import BaseModel
import uvicorn

from dflowp_processruntime.engine.runtime import Runtime
from dflowp_processruntime.processes.process_configuration import ProcessConfiguration
from dflowp_core.database.mongo import resolve_mongodb_uri
from dflowp_core.utils.document_naming import build_human_readable_document_id
from dflowp_core.utils.logger import get_logger

logger = get_logger(__name__)

MONGODB_URI = resolve_mongodb_uri()
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "dflowp")
CONFIG_PATH = os.environ.get("PROCESS_CONFIG", "examples/processconfig_example.json")
INPUT_PATH = os.environ.get("INPUT_DATA", "examples/inputdata_set.json")
EVENTSYSTEM_URL = os.environ.get("DFLOWP_EVENTSYSTEM_URL", "http://eventsystem:8001")
RUNTIME_PUBLIC_URL = os.environ.get("DFLOWP_RUNTIME_PUBLIC_URL", "http://worker:8002")
RUNTIME_EVENT_PORT = int(os.environ.get("DFLOWP_RUNTIME_EVENT_PORT", "8002"))
RUNTIME_SUBSCRIBER_ID = os.environ.get("DFLOWP_RUNTIME_SUBSCRIBER_ID", "dflowp-runtime")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


class RuntimeEventPayload(BaseModel):
    event_id: str | None = None
    process_id: str | None = None
    subprocess_id: str | None = None
    subprocess_instance_id: int | None = 1
    event_type: str
    event_time: str | None = None
    payload: dict | None = None
    timestamp_ms: int | None = None


app = FastAPI(title="DFlowP Runtime Event Listener", version="1.0.0")
_runtime: Runtime | None = None
_shutdown_event: asyncio.Event | None = None


@app.post("/internal/events", status_code=status.HTTP_204_NO_CONTENT)
async def receive_runtime_event(event: RuntimeEventPayload) -> None:
    if _runtime is None:
        return None
    await _runtime.engine.handle_event_notification(event.model_dump())
    return None


async def _subscribe_runtime() -> None:
    payload = {
        "subscriber_id": RUNTIME_SUBSCRIBER_ID,
        "callback_url": f"{RUNTIME_PUBLIC_URL.rstrip('/')}/internal/events",
    }
    max_attempts = int(os.environ.get("DFLOWP_EVENTSYSTEM_SUBSCRIBE_RETRIES", "30"))
    retry_sleep = float(os.environ.get("DFLOWP_EVENTSYSTEM_SUBSCRIBE_RETRY_SLEEP", "1.0"))
    last_error: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{EVENTSYSTEM_URL.rstrip('/')}/internal/subscriptions",
                    json=payload,
                )
                response.raise_for_status()
            logger.info("Runtime beim EventSystem subscribed: %s", payload["callback_url"])
            return
        except Exception as exc:
            last_error = exc
            logger.warning(
                "Subscribe beim EventSystem fehlgeschlagen (attempt %d/%d): %s",
                attempt,
                max_attempts,
                exc,
            )
            await asyncio.sleep(retry_sleep)

    raise RuntimeError(f"Subscribe beim EventSystem fehlgeschlagen: {last_error}")


async def _bootstrap_runtime() -> Runtime:
    runtime = Runtime(
        mongodb_uri=MONGODB_URI,
        mongodb_database=MONGODB_DATABASE,
        enable_local_event_subscriptions=False,
    )
    await runtime.start()

    for path in (CONFIG_PATH, INPUT_PATH):
        if not Path(path).exists():
            raise FileNotFoundError(f"Datei nicht gefunden: {path}")

    with open(CONFIG_PATH, encoding="utf-8") as file:
        config_dict = json.load(file)

    config_dict["process_id"] = build_human_readable_document_id(
        domain="pipeline",
        document_type="proc",
    )
    config = ProcessConfiguration.from_dict(config_dict)
    config.apply_default_openai_key_from_env()

    await runtime.load_input_dataset(
        dataset_id=config.input_dataset_id,
        input_json_path=INPUT_PATH,
    )
    logger.info("Starte Prozess '%s' ...", config.process_id)
    await runtime.engine.start_process(config)
    return runtime


async def _poll_pending_processes(shutdown: asyncio.Event, runtime: Runtime) -> None:
    poll_interval = float(os.environ.get("DFLOWP_POLL_INTERVAL", "5"))
    logger.info("Pending-Prozess-Polling aktiv (Intervall: %ss)", poll_interval)
    while not shutdown.is_set():
        claimed = await runtime.process_repository.claim_next_pending()
        if claimed:
            process_id = claimed["process_id"]
            logger.info("Übernehme wartenden Prozess '%s' …", process_id)
            await runtime.engine.activate_pending_process(process_id)
            continue
        try:
            await asyncio.wait_for(shutdown.wait(), timeout=poll_interval)
        except asyncio.TimeoutError:
            pass


async def _main_async() -> None:
    global _runtime, _shutdown_event
    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY ist nicht gesetzt.")
        raise SystemExit(1)

    _shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        if _shutdown_event:
            _shutdown_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_shutdown)

    _runtime = await _bootstrap_runtime()
    await _subscribe_runtime()

    poll_task = asyncio.create_task(_poll_pending_processes(_shutdown_event, _runtime))
    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            host="0.0.0.0",
            port=RUNTIME_EVENT_PORT,
            log_level="info",
        )
    )
    server_task = asyncio.create_task(server.serve())

    await _shutdown_event.wait()
    server.should_exit = True
    await server_task
    poll_task.cancel()
    try:
        await poll_task
    except asyncio.CancelledError:
        pass

    await _runtime.stop()


def main() -> None:
    asyncio.run(_main_async())


if __name__ == "__main__":
    main()
