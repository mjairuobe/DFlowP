"""FastAPI-Schnittstelle für Repository-Read-Zugriffe."""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Query, status

from dflowp.api.auth import require_api_key
from dflowp.infrastructure.database.data_item_repository import DataItemRepository
from dflowp.infrastructure.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    resolve_mongodb_uri,
)
from dflowp.infrastructure.database.process_repository import ProcessRepository


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
        await process_repo.create_indexes()
        await data_item_repo.create_indexes()

    try:
        yield
    finally:
        if not skip_db_init:
            await close_mongodb_connection()


app = FastAPI(title="DFlowP API", version="1.0.0", lifespan=lifespan)


def _pagination_params(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> tuple[int, int]:
    return page, page_size


def get_process_repository() -> ProcessRepository:
    return ProcessRepository()


def get_data_item_repository() -> DataItemRepository:
    return DataItemRepository()


@app.get("/api/v1/datasets", dependencies=[Depends(require_api_key)])
async def list_datasets(
    pagination: tuple[int, int] = Depends(_pagination_params),
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict:
    page, page_size = pagination
    return await data_item_repo.list_datasets(page=page, page_size=page_size)


@app.get("/api/v1/datasets/{dataset_id}", dependencies=[Depends(require_api_key)])
async def get_dataset(
    dataset_id: str,
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict:
    dataset = await data_item_repo.find_dataset_by_id(dataset_id)
    if not dataset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset '{dataset_id}' wurde nicht gefunden.",
        )
    return dataset


@app.get("/api/v1/processes", dependencies=[Depends(require_api_key)])
async def list_processes(
    pagination: tuple[int, int] = Depends(_pagination_params),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict:
    page, page_size = pagination
    return await process_repo.list_processes(page=page, page_size=page_size)


@app.get("/api/v1/processes/{process_id}", dependencies=[Depends(require_api_key)])
async def get_process(
    process_id: str,
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict:
    process = await process_repo.find_by_id(process_id)
    if not process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prozess '{process_id}' wurde nicht gefunden.",
        )
    return process


@app.get("/api/v1/subprocesses", dependencies=[Depends(require_api_key)])
async def list_subprocesses(
    pagination: tuple[int, int] = Depends(_pagination_params),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict:
    page, page_size = pagination
    return await process_repo.list_subprocesses(page=page, page_size=page_size)


@app.get(
    "/api/v1/subprocesses/{subprocess_id}",
    dependencies=[Depends(require_api_key)],
)
async def get_subprocess(
    subprocess_id: str,
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict:
    subprocess_doc = await process_repo.find_subprocess_by_id(subprocess_id)
    if not subprocess_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subprozess '{subprocess_id}' wurde nicht gefunden.",
        )
    return subprocess_doc
