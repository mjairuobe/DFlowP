"""FastAPI-Einstieg: nur Lifespan, CORS und der Router unter ``/api/v1`` (``kebab_routes``)."""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from fastapi import FastAPI

from dflowp.api.cors import add_cors_middleware
from dflowp.api.kebab_routes import router as kebab_v1_router
from dflowp_core.database.data_item_repository import DataItemRepository
from dflowp_core.database.event_repository import EventRepository
from dflowp_core.database.process_repository import ProcessRepository
from dflowp_core.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    resolve_mongodb_uri,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """Initialisiert die DB-Verbindung für die API-Laufzeit."""
    skip_db_init = os.environ.get("DFLOWP_SKIP_DB_INIT", "0") == "1"
    if not skip_db_init:
        await connect_to_mongodb(
            uri=resolve_mongodb_uri(),
            database_name=os.environ.get("MONGODB_DATABASE", "dflowp"),
        )
        process_repo = ProcessRepository()
        data_item_repo = DataItemRepository()
        event_repo = EventRepository()
        await process_repo.create_indexes()
        await data_item_repo.create_indexes()
        await event_repo.create_indexes()

    try:
        yield
    finally:
        if not skip_db_init:
            await close_mongodb_connection()


app = FastAPI(
    title="DFlowP API",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "REST-API für Pipelines, Data-Items, Datasets, Events, Dataflows, Dataflow-States und "
        "Plugin-Konfigurationen. Authentifizierung: Header `X-API-Key` auf allen Endpunkten. "
        "Vollständige Endpunktliste, cURL-Beispiele pro Route und beispielhafte JSON-Responses für "
        "Detail-GETs: Repository-Datei `docs/api-reference.md`."
    ),
    openapi_tags=[
        {
            "name": "v1",
            "description": (
                "API unter /api/v1. Doku: `docs/api-reference.md`."
            ),
        },
    ],
)
add_cors_middleware(app)
app.include_router(kebab_v1_router)
