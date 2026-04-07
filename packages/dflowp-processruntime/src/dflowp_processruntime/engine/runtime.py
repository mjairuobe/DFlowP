"""
Runtime - Startet und verbindet alle DFlowP-Komponenten.

Verantwortlichkeiten:
- MongoDB-Verbindung herstellen
- Repositories instanziieren
- Plugins laden
- ProcessEngine aufbauen und zurückgeben
"""

import json
from pathlib import Path
from typing import Optional

from dflowp_processruntime.engine.process_engine import ProcessEngine
from dflowp_core.eventinterfaces.event_service import get_event_service
from dflowp_processruntime.processes.process_configuration import ProcessConfiguration
from dflowp_core.database.data_repository import DataRepository
from dflowp_core.database.dataflow_state_repository import DataflowStateRepository
from dflowp_core.database.dataset_repository import DatasetRepository
from dflowp_core.database.event_repository import EventRepository
from dflowp_core.database.mongo import connect_to_mongodb, close_mongodb_connection, resolve_mongodb_uri
from dflowp_core.database.process_repository import ProcessRepository
from dflowp_processruntime.plugins.plugin_loader import get_subprocess, load_builtin_plugins
from dflowp_core.utils.document_naming import build_human_readable_document_id
from dflowp_core.utils.logger import get_logger

logger = get_logger(__name__)


class Runtime:
    """
    Verbindet alle Komponenten des Frameworks und stellt eine
    fertig konfigurierte ProcessEngine bereit.
    """

    def __init__(
        self,
        mongodb_uri: str = resolve_mongodb_uri(),
        mongodb_database: str = "dflowp",
    ) -> None:
        self._mongodb_uri = mongodb_uri
        self._mongodb_database = mongodb_database
        self._engine: Optional[ProcessEngine] = None
        self._process_repo: Optional[ProcessRepository] = None

    async def start(self) -> "Runtime":
        """
        Stellt die Datenbankverbindung her, lädt Plugins und
        initialisiert die ProcessEngine.
        """
        logger.info("DFlowP Runtime startet...")

        await connect_to_mongodb(
            uri=self._mongodb_uri,
            database_name=self._mongodb_database,
        )
        logger.info("MongoDB verbunden: %s / %s", self._mongodb_uri, self._mongodb_database)

        load_builtin_plugins()
        logger.info("Plugins geladen: FetchFeedItems, EmbedData")

        process_repo = ProcessRepository()
        dataflow_state_repo = DataflowStateRepository()
        data_repo = DataRepository()
        dataset_repo = DatasetRepository()
        event_repo = EventRepository()

        await process_repo.create_indexes()
        await data_repo.create_indexes()
        await dataset_repo.create_indexes()
        await event_repo.create_indexes()

        event_service = get_event_service()
        event_service.set_event_repository(event_repo)

        self._engine = ProcessEngine(
            event_service=event_service,
            process_repository=process_repo,
            dataflow_state_repository=dataflow_state_repo,
            data_repository=data_repo,
            dataset_repository=dataset_repo,
            get_subprocess=get_subprocess,
        )
        self._engine.start()

        self._process_repo = process_repo
        self._data_repo = data_repo
        self._dataset_repo = dataset_repo

        logger.info("ProcessEngine bereit.")
        return self

    async def stop(self) -> None:
        """Schließt die Datenbankverbindung."""
        await close_mongodb_connection()
        logger.info("DFlowP Runtime gestoppt.")

    @property
    def engine(self) -> ProcessEngine:
        if self._engine is None:
            raise RuntimeError("Runtime wurde noch nicht gestartet. Rufe zuerst await runtime.start() auf.")
        return self._engine

    @property
    def process_repository(self) -> ProcessRepository:
        if self._process_repo is None:
            raise RuntimeError("Runtime wurde noch nicht gestartet. Rufe zuerst await runtime.start() auf.")
        return self._process_repo

    async def load_input_dataset(
        self,
        dataset_id: str,
        input_json_path: str,
    ) -> int:
        """
        Lädt ein Input-Dataset aus einer JSON-Datei in die Datenbank,
        falls es dort noch nicht existiert.

        Args:
            dataset_id: ID unter der das Dataset gespeichert wird (z. B. "ds_news_001")
            input_json_path: Pfad zur JSON-Datei mit einer Liste von Input-Daten

        Returns:
            Anzahl der geladenen Datensätze (0 wenn Dataset bereits existiert)
        """
        existing = await self._dataset_repo.find_by_id(dataset_id)
        if existing:
            count = len(existing.get("data_ids", []))
            logger.info(
                "Dataset '%s' bereits vorhanden (%d Einträge), wird übersprungen.",
                dataset_id, count,
            )
            return 0

        path = Path(input_json_path)
        if not path.exists():
            raise FileNotFoundError(f"Input-Datei nicht gefunden: {input_json_path}")

        with open(path, encoding="utf-8") as f:
            items = json.load(f)

        if not isinstance(items, list):
            raise ValueError(f"JSON-Datei muss eine Liste enthalten, gefunden: {type(items)}")

        data_ids = []
        for i, item in enumerate(items):
            data_id = build_human_readable_document_id(
                domain=dataset_id,
                document_type="data",
            )
            await self._data_repo.insert({
                "data_id": data_id,
                "content": item,
                "type": "input",
            })
            data_ids.append(data_id)

        await self._dataset_repo.insert({
            "dataset_id": dataset_id,
            "data_ids": data_ids,
        })

        logger.info(
            "Dataset '%s' geladen: %d Einträge aus '%s'.",
            dataset_id, len(data_ids), input_json_path,
        )
        return len(data_ids)
