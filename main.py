"""
DFlowP - Einstiegspunkt

Startet die News-Pipeline aus der Beispielkonfiguration:
  1. Input-Dataset (RSS-Feed-URLs) in MongoDB laden
  2. Prozess gemäß processconfig_example.json starten
  3. Warten bis FetchFeedItems + EmbedData abgeschlossen sind

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
from dflowp.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Konfiguration (überschreibbar per Umgebungsvariable)
# ---------------------------------------------------------------------------

MONGODB_URI      = os.environ.get("MONGODB_URI",      "mongodb://localhost:27017")
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

    # Sauberes Beenden bei Strg+C
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(_shutdown(runtime)))

    try:
        await runtime.start()

        # --- Prozesskonfiguration laden --------------------------------------
        with open(CONFIG_PATH, encoding="utf-8") as f:
            config_dict = json.load(f)

        config_dict["process_id"] = f"{config_dict["process_id"]}_{time.time()}"
        config = ProcessConfiguration.from_dict(config_dict)
        
        # OpenAI API Key in die EmbedData-Config eintragen, falls nicht
        # explizit in der JSON-Config gesetzt
        for subprocess_id, sub_cfg in config.subprocess_config.items():
            node = config.dataflow.get_node(subprocess_id)
            if node and node.subprocess_type == "EmbedData":
                sub_cfg.setdefault("openai_api_key", os.environ["OPENAI_API_KEY"])

        # --- Input-Dataset laden (idempotent - überspringt wenn vorhanden) --
        await runtime.load_input_dataset(
            dataset_id=config.input_dataset_id,
            input_json_path=INPUT_PATH,
        )

        # --- Prozess starten -------------------------------------------------
        logger.info("Starte Prozess '%s' ...", config.process_id)
        await runtime.engine.start_process(config)

        # Warten bis alle asyncio-Tasks beendet sind
        logger.info("Pipeline läuft. Strg+C zum Beenden.")
        await _wait_for_completion()

    finally:
        await runtime.stop()


async def _wait_for_completion() -> None:
    """Wartet bis keine weiteren Hintergrund-Tasks mehr laufen."""
    while True:
        tasks = [
            t for t in asyncio.all_tasks()
            if t is not asyncio.current_task()
        ]
        if not tasks:
            break
        await asyncio.sleep(2)


async def _shutdown(runtime: Runtime) -> None:
    logger.info("Beende DFlowP ...")
    await runtime.stop()
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
