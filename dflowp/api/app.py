"""FastAPI-Schnittstelle für Repository-Read-Zugriffe."""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from fastapi import Body, Depends, FastAPI, HTTPException, Query, status

from dflowp.api.auth import require_api_key
from dflowp.api.process_persist import persist_input_dataset_rows
from dflowp.api.schemas import ProcessCloneRequest, ProcessCreateRequest, ProcessStopRequest
from dflowp_processruntime.dataflow.dataflow_state import DataflowState
from dflowp_processruntime.processes.process_configuration import ProcessConfiguration
from dflowp_core.database.data_item_repository import DataItemRepository
from dflowp_core.database.event_repository import EventRepository
from dflowp_core.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    resolve_mongodb_uri,
)
from dflowp_core.database.process_repository import ProcessRepository


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


def get_event_repository() -> EventRepository:
    return EventRepository()


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


@app.get("/api/v1/dataitems", dependencies=[Depends(require_api_key)])
async def list_dataitems(
    pagination: tuple[int, int] = Depends(_pagination_params),
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict:
    page, page_size = pagination
    return await data_item_repo.list_dataitems(page=page, page_size=page_size)


@app.get("/api/v1/dataitems/{item_id}", dependencies=[Depends(require_api_key)])
async def get_dataitem(
    item_id: str,
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict:
    item = await data_item_repo.find_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataItem '{item_id}' wurde nicht gefunden.",
        )
    return item


@app.get("/api/v1/data-items", dependencies=[Depends(require_api_key)])
async def list_data_items_alias(
    pagination: tuple[int, int] = Depends(_pagination_params),
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict:
    """Alias-Endpunkt für dataitems mit Bindestrich."""
    page, page_size = pagination
    return await data_item_repo.list_data_items(page=page, page_size=page_size)


@app.get("/api/v1/data-items/{item_id}", dependencies=[Depends(require_api_key)])
async def get_data_item_alias(
    item_id: str,
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict:
    """Alias-Endpunkt für DataItem-Detail mit Bindestrich."""
    item = await data_item_repo.find_data_item_by_id(item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"DataItem '{item_id}' wurde nicht gefunden.",
        )
    return item


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


@app.get("/api/v1/events", dependencies=[Depends(require_api_key)])
async def list_events(
    pagination: tuple[int, int] = Depends(_pagination_params),
    event_repo: EventRepository = Depends(get_event_repository),
) -> dict:
    page, page_size = pagination
    return await event_repo.list_events(page=page, page_size=page_size)


@app.get("/api/v1/events/{event_id}", dependencies=[Depends(require_api_key)])
async def get_event(
    event_id: str,
    event_repo: EventRepository = Depends(get_event_repository),
) -> dict:
    event = await event_repo.find_by_id(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event '{event_id}' wurde nicht gefunden.",
        )
    return event


@app.post(
    "/api/v1/processes/{process_id}/clone",
    dependencies=[Depends(require_api_key)],
    status_code=status.HTTP_201_CREATED,
)
async def copy_process(
    process_id: str,
    request: ProcessCloneRequest = Body(...),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict:
    """
    Kopiert einen Prozess unter neuer ID und markiert Teile des DAGs zur Re-Execution.
    """
    source_process = await process_repo.find_by_id(process_id)
    if not source_process:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prozess '{process_id}' wurde nicht gefunden.",
        )

    target_process_id = request.new_process_id or f"{process_id}_copy"
    if not request.new_process_id:
        counter = 1
        while await process_repo.find_by_id(target_process_id):
            counter += 1
            target_process_id = f"{process_id}_copy_{counter}"

    copied = await process_repo.copy_process_with_reexecution(
        source_process_id=process_id,
        target_process_id=target_process_id,
        parent_subprocess_ids=request.parent_subprocess_ids,
        subprocess_config_override=request.subprocess_config,
    )
    if not copied:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prozess konnte nicht kopiert werden.",
        )
    return copied


@app.post(
    "/api/v1/processes",
    dependencies=[Depends(require_api_key)],
    status_code=status.HTTP_201_CREATED,
)
async def create_process(
    request: ProcessCreateRequest = Body(...),
    process_repo: ProcessRepository = Depends(get_process_repository),
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict:
    """
    Legt einen Prozess mit Konfiguration an; optional werden Input-Zeilen als Dataset gespeichert.
    `start_immediately=false` (Standard): status=pending – der Runtime-Worker übernimmt den Start.
    `start_immediately=true`: status=running – für direkten Engine-Start (selten über API).
    """
    if await process_repo.find_by_id(request.process_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Prozess '{request.process_id}' existiert bereits.",
        )

    try:
        configuration = ProcessConfiguration.from_dict(
            {
                "process_id": request.process_id,
                "software_version": request.software_version,
                "input_dataset_id": request.input_dataset_id,
                "dataflow": request.dataflow,
                "subprocess_config": request.subprocess_config,
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültige Prozesskonfiguration: {exc}",
        ) from exc

    configuration.apply_default_openai_key_from_env()
    configuration.apply_software_version_from_env()

    if request.input_data is not None:
        existing_ds = await data_item_repo.find_dataset_by_id(request.input_dataset_id)
        if existing_ds:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Dataset '{request.input_dataset_id}' existiert bereits; Input kann nicht angelegt werden.",
            )
        await persist_input_dataset_rows(
            data_item_repo=data_item_repo,
            dataset_id=request.input_dataset_id,
            rows=request.input_data,
        )

    dataflow_state = DataflowState.from_dataflow(configuration.dataflow)
    process_doc: dict = {
        "process_id": configuration.process_id,
        "software_version": configuration.software_version,
        "input_dataset_id": configuration.input_dataset_id,
        "configuration": configuration.to_dict(),
        "dataflow_state": dataflow_state.to_dict(),
        "status": "running" if request.start_immediately else "pending",
    }
    await process_repo.insert(process_doc)
    created = await process_repo.find_by_id(configuration.process_id)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Prozess wurde nicht gespeichert.",
        )
    return created


@app.post(
    "/api/v1/processes/{process_id}/stop",
    dependencies=[Depends(require_api_key)],
)
async def stop_process(
    process_id: str,
    request: ProcessStopRequest = Body(default=ProcessStopRequest()),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict:
    """
    Beendet einen Prozess administrativ (status=stopped).
    Laufende Subprozesse werden nicht zwangsweise abgebrochen; für ein hartes Abbrechen ist ein Runtime-Eingriff nötig.
    """
    existing = await process_repo.find_by_id(process_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prozess '{process_id}' wurde nicht gefunden.",
        )
    update: dict = {"status": "stopped"}
    if request.reason:
        update["cancelled_reason"] = request.reason
    await process_repo.update(process_id, update)
    out = await process_repo.find_by_id(process_id)
    return out or existing


@app.delete(
    "/api/v1/processes/{process_id}",
    dependencies=[Depends(require_api_key)],
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_process(
    process_id: str,
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> None:
    """Löscht das Prozessdokument."""
    deleted = await process_repo.delete_by_id(process_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prozess '{process_id}' wurde nicht gefunden.",
        )
