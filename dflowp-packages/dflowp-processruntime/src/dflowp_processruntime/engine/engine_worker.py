"""Worker-Prozess zum Starten der DFlowP-ProcessEngine ohne API."""

import asyncio
import json
import os
import signal
import sys
import time
from pathlib import Path

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


async def run_worker() -> None:
    """Startet Runtime + Engine als separaten Worker-Prozess."""
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error(
            "OPENAI_API_KEY ist nicht gesetzt. "
            "Bitte exportiere ihn: export OPENAI_API_KEY=sk-..."
        )
        sys.exit(1)

    for path in (CONFIG_PATH, INPUT_PATH):
        if not Path(path).exists():
            logger.error("Datei nicht gefunden: %s", path)
            sys.exit(1)

    runtime = Runtime(
        mongodb_uri=MONGODB_URI,
        mongodb_database=MONGODB_DATABASE,
    )

    shutdown = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        logger.info("Beende-Anforderung empfangen …")
        shutdown.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_shutdown)

    try:
        await runtime.start()

        with open(CONFIG_PATH, encoding="utf-8") as file:
            config_dict = json.load(file)

        config_dict["pipeline_id"] = build_human_readable_document_id(
            domain="pipeline",
            document_type="proc",
        )
        config = ProcessConfiguration.from_dict(config_dict)
        config.apply_default_openai_key_from_env()

        await runtime.load_input_dataset(
            dataset_id=config.input_dataset_id,
            input_json_path=INPUT_PATH,
        )

        logger.info("Starte Pipeline '%s' ...", config.pipeline_id)
        await runtime.engine.start_process(config)

        poll_interval = float(os.environ.get("DFLOWP_POLL_INTERVAL", "5"))
        logger.info(
            "Engine-Worker aktiv; wartende Prozesse (status=pending) werden gepollt. "
            "Intervall: %s s",
            poll_interval,
        )

        while not shutdown.is_set():
            await runtime.engine.wait_until_idle(shutdown=shutdown, poll_seconds=0.5)
            if shutdown.is_set():
                break

            claimed = await runtime.process_repository.claim_next_pending()
            if claimed:
                pl_id = claimed.get("pipeline_id") or claimed.get("process_id")
                logger.info("Übernehme wartende Pipeline '%s' …", pl_id)
                await runtime.engine.activate_pending_process(pl_id)
            else:
                try:
                    await asyncio.wait_for(shutdown.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
    finally:
        await runtime.stop()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
