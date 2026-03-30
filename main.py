"""
DFlowP - Einstiegspunkt

Startet die News-Pipeline aus der Beispielkonfiguration:
  1. Input-Dataset (RSS-Feed-URLs) in MongoDB laden
  2. Prozess gemäß processconfig_example.json starten
  3. Nach Abschluss: wartet dauerhaft und übernimmt neue Prozesse
     mit status "pending" aus der Collection processes (Polling).
     Intervall: DFLOWP_POLL_INTERVAL (Sekunden), Standard 5.

Zum Einreihen eines Prozesses: Dokument in MongoDB mit status "pending"
und denselben Feldern wie nach einem insert (process_id, configuration, …).

Voraussetzungen:
  - MongoDB läuft auf localhost:27017  (oder MONGODB_URI setzen)
  - OPENAI_API_KEY ist gesetzt         (für EmbedData)

Start:
  python main.py
"""

import asyncio
import json
import time
import os
import signal
import sys
from pathlib import Path

from dflowp.core.engine.runtime import Runtime
from dflowp.core.processes.process_configuration import ProcessConfiguration
from dflowp.infrastructure.database.mongo import resolve_mongodb_uri
from dflowp.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Konfiguration (überschreibbar per Umgebungsvariable)
# ---------------------------------------------------------------------------

MONGODB_URI      = resolve_mongodb_uri()
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "dflowp")
CONFIG_PATH      = os.environ.get("PROCESS_CONFIG",   "examples/processconfig_example.json")
INPUT_PATH       = os.environ.get("INPUT_DATA",       "examples/inputdata_set.json") # ds_news_002 in der DB
BIG_INPUT_PATH       = os.environ.get("INPUT_DATA",       "examples/inputdata_set_big.json") # ds_news_001 in der DB

async def main() -> None:
    # --- Voraussetzungen prüfen -------------------------------------------
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

    # --- Runtime starten -----------------------------------------------------
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

        # --- Prozesskonfiguration laden --------------------------------------
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config_dict = json.load(f)

        config_dict["process_id"] = f"{config_dict['process_id']}_{time.time()}"
        config = ProcessConfiguration.from_dict(config_dict)
        config.apply_default_openai_key_from_env()

        # --- Input-Dataset laden (idempotent - überspringt wenn vorhanden) --
        await runtime.load_input_dataset(
            dataset_id=config.input_dataset_id,
            input_json_path=INPUT_PATH,
        )

        # --- Ersten Prozess starten ------------------------------------------
        logger.info("Starte Prozess '%s' ...", config.process_id)
        await runtime.engine.start_process(config)

        poll_interval = float(os.environ.get("DFLOWP_POLL_INTERVAL", "5"))
        logger.info(
            "Pipeline aktiv; nach jedem Abschluss werden wartende Prozesse (status=pending) "
            "abgeholt. Poll-Intervall ohne Job: %s s. Strg+C zum Beenden.",
            poll_interval,
        )

        while not shutdown.is_set():
            await runtime.engine.wait_until_idle(shutdown=shutdown, poll_seconds=0.5)
            if shutdown.is_set():
                break
            claimed = await runtime.process_repository.claim_next_pending()
            if claimed:
                pid = claimed["process_id"]
                logger.info("Übernehme wartenden Prozess '%s' …", pid)
                await runtime.engine.activate_pending_process(pid)
            else:
                try:
                    await asyncio.wait_for(shutdown.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass

    finally:
        await runtime.stop()


if __name__ == "__main__":
    asyncio.run(main())
