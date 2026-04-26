"""REST-Routen gemäß Plan: kebab-case-Pfade (pipelines, dataflows, …)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from dflowp.api.auth import require_api_key
from dflowp.api.deps import (
    get_dataflow_repository,
    get_dataflow_state_repository,
    get_data_item_repository,
    get_event_repository,
    get_plugin_configuration_repository,
    get_process_repository,
)
from dflowp.api.list_summaries import (
    apply_summary_to_page,
    summarize_dataflow_list_item,
    summarize_dataflow_state_list_item,
    summarize_pipeline_list_item,
    summarize_plugin_configuration_list_item,
)
from dflowp.api.pipeline_handlers import create_pipeline_document
from dflowp.api.schemas import (
    DataflowCreateRequest,
    DataflowStateCreateRequest,
    EventCreateRequest,
    PipelineCreateRequest,
    PluginConfigurationCreateRequest,
    ProcessCloneRequest,
    ProcessStopRequest,
)
from dflowp_core.database.dataflow_repository import DataflowRepository
from dflowp_core.database.dataflow_state_repository import DataflowStateRepository
from dflowp_core.database.data_item_repository import DataItemRepository
from dflowp_core.database.event_repository import EventRepository
from dflowp_core.database.plugin_configuration_repository import PluginConfigurationRepository
from dflowp_core.database.process_repository import ProcessRepository

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_api_key)],
    tags=["v1"],
)


def _pagination(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> tuple[int, int]:
    return page, page_size


# --- Pipelines (Parität zu /processes, primäre Namen) ---


@router.get("/pipelines")
async def list_pipelines(
    pagination: tuple[int, int] = Depends(_pagination),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict[str, Any]:
    page, page_size = pagination
    raw = await process_repo.list_pipelines(page=page, page_size=page_size)
    return apply_summary_to_page(raw, summarize_pipeline_list_item)


@router.get("/pipelines/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict[str, Any]:
    doc = await process_repo.find_by_id(pipeline_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' wurde nicht gefunden.",
        )
    return doc


@router.post("/pipelines", status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    request: PipelineCreateRequest = Body(...),
    process_repo: ProcessRepository = Depends(get_process_repository),
    data_item_repo: DataItemRepository = Depends(get_data_item_repository),
) -> dict[str, Any]:
    return await create_pipeline_document(
        pipeline_id=request.pipeline_id,
        software_version=request.software_version,
        input_dataset_id=request.input_dataset_id,
        dataflow=request.dataflow,
        plugin_config=request.plugin_config,
        input_data=request.input_data,
        start_immediately=request.start_immediately,
        process_repo=process_repo,
        data_item_repo=data_item_repo,
    )


@router.post("/pipelines/{pipeline_id}/stop")
async def stop_pipeline(
    pipeline_id: str,
    request: ProcessStopRequest = Body(default=ProcessStopRequest()),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict[str, Any]:
    existing = await process_repo.find_by_id(pipeline_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' wurde nicht gefunden.",
        )
    update: dict[str, Any] = {"status": "stopped"}
    if request.reason:
        update["cancelled_reason"] = request.reason
    await process_repo.update(pipeline_id, update)
    return await process_repo.find_by_id(pipeline_id) or existing


@router.post("/pipelines/{pipeline_id}/clone", status_code=status.HTTP_201_CREATED)
async def clone_pipeline(
    pipeline_id: str,
    request: ProcessCloneRequest = Body(...),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict[str, Any]:
    source = await process_repo.find_by_id(pipeline_id)
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' wurde nicht gefunden.",
        )
    target = request.new_process_id or f"{pipeline_id}_copy"
    if not request.new_process_id:
        counter = 1
        while await process_repo.find_by_id(target):
            counter += 1
            target = f"{pipeline_id}_copy_{counter}"
    copied = await process_repo.copy_process_with_reexecution(
        source_process_id=pipeline_id,
        target_process_id=target,
        parent_subprocess_ids=request.parent_subprocess_ids,
        subprocess_config_override=request.subprocess_config,
    )
    if not copied:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline konnte nicht geklont werden.",
        )
    return copied


@router.delete("/pipelines/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pipeline(
    pipeline_id: str,
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> None:
    if not await process_repo.delete_by_id(pipeline_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pipeline '{pipeline_id}' wurde nicht gefunden.",
        )


# --- Plugin-Worker-Liste (Alias zu Subprozessen) ---


@router.get("/plugin-workers")
async def list_plugin_workers(
    pagination: tuple[int, int] = Depends(_pagination),
    process_repo: ProcessRepository = Depends(get_process_repository),
) -> dict[str, Any]:
    page, page_size = pagination
    return await process_repo.list_plugin_workers(page=page, page_size=page_size)


# --- Dataflows ---


@router.get("/dataflows")
async def list_dataflows_endpoint(
    pagination: tuple[int, int] = Depends(_pagination),
    dfr: DataflowRepository = Depends(get_dataflow_repository),
) -> dict[str, Any]:
    page, page_size = pagination
    raw = await dfr.list_dataflows(page=page, page_size=page_size)
    return apply_summary_to_page(raw, summarize_dataflow_list_item)


@router.get("/dataflows/{dataflow_id}")
async def get_dataflow(
    dataflow_id: str,
    dfr: DataflowRepository = Depends(get_dataflow_repository),
) -> dict[str, Any]:
    doc = await dfr.find_by_id(dataflow_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Dataflow '{dataflow_id}' nicht gefunden.")
    return doc


@router.post("/dataflows", status_code=status.HTTP_201_CREATED)
async def post_dataflow(
    request: DataflowCreateRequest = Body(...),
    dfr: DataflowRepository = Depends(get_dataflow_repository),
) -> dict[str, Any]:
    if await dfr.find_by_id(request.dataflow_id):
        raise HTTPException(status_code=409, detail="Dataflow-ID existiert bereits.")
    doc: dict[str, Any] = {
        "dataflow_id": request.dataflow_id,
        "name": request.name,
        "nodes": request.nodes,
        "edges": request.edges,
    }
    await dfr.insert(doc)
    out = await dfr.find_by_id(request.dataflow_id)
    if not out:
        raise HTTPException(500, detail="Dataflow nach insert nicht lesbar.")
    return out


@router.put("/dataflows/{dataflow_id}")
async def put_dataflow(
    dataflow_id: str,
    request: DataflowCreateRequest = Body(...),
    dfr: DataflowRepository = Depends(get_dataflow_repository),
) -> dict[str, Any]:
    if request.dataflow_id != dataflow_id:
        raise HTTPException(422, detail="dataflow_id im Body muss dem Pfad entsprechen.")
    doc: dict[str, Any] = {
        "dataflow_id": dataflow_id,
        "name": request.name,
        "nodes": request.nodes,
        "edges": request.edges,
    }
    if not await dfr.replace_by_id(dataflow_id, doc):
        raise HTTPException(404, detail="Dataflow nicht gefunden.")
    return (await dfr.find_by_id(dataflow_id)) or doc


@router.delete("/dataflows/{dataflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataflow(
    dataflow_id: str,
    dfr: DataflowRepository = Depends(get_dataflow_repository),
) -> None:
    if not await dfr.delete_by_id(dataflow_id):
        raise HTTPException(404, detail="Dataflow nicht gefunden.")


# --- Dataflow-States ---


@router.get("/dataflow-states")
async def list_dataflow_states_endpoint(
    pagination: tuple[int, int] = Depends(_pagination),
    pipeline_id: Annotated[Optional[str], Query()] = None,
    dataflow_id: Annotated[Optional[str], Query()] = None,
    dsr: DataflowStateRepository = Depends(get_dataflow_state_repository),
) -> dict[str, Any]:
    page, page_size = pagination
    raw = await dsr.list_dataflow_states(
        page=page, page_size=page_size, pipeline_id=pipeline_id, dataflow_id=dataflow_id
    )
    return apply_summary_to_page(raw, summarize_dataflow_state_list_item)


@router.get("/dataflow-states/{dataflow_state_id}")
async def get_dataflow_state(
    dataflow_state_id: str,
    dsr: DataflowStateRepository = Depends(get_dataflow_state_repository),
) -> dict[str, Any]:
    doc = await dsr.get_by_id(dataflow_state_id)
    if not doc:
        raise HTTPException(404, detail="DataflowState nicht gefunden.")
    return doc


@router.post("/dataflow-states", status_code=status.HTTP_201_CREATED)
async def post_dataflow_state(
    request: DataflowStateCreateRequest = Body(...),
    dsr: DataflowStateRepository = Depends(get_dataflow_state_repository),
) -> dict[str, Any]:
    if await dsr.get_by_id(request.dataflow_state_id):
        raise HTTPException(409, detail="dataflow_state_id existiert bereits.")
    st: dict[str, Any] = {
        "nodes": request.nodes,
        "edges": request.edges,
    }
    ins: dict[str, Any] = {
        "dataflow_state_id": request.dataflow_state_id,
        "pipeline_id": request.pipeline_id,
        "dataflow_id": request.dataflow_id,
        "nodes": request.nodes,
        "edges": request.edges,
        "dataflow_state": st,
    }
    await dsr.insert(ins)
    out = await dsr.get_by_id(request.dataflow_state_id)
    if not out:
        raise HTTPException(500, detail="DataflowState nach insert nicht lesbar.")
    return out


@router.patch("/dataflow-states/{dataflow_state_id}")
async def patch_dataflow_state(
    dataflow_state_id: str,
    body: dict[str, Any] = Body(...),
    dsr: DataflowStateRepository = Depends(get_dataflow_state_repository),
) -> dict[str, Any]:
    """Erwartet mindestens 'nodes'/'edges' oder vollständiges 'dataflow_state' (Map)."""
    if not await dsr.get_by_id(dataflow_state_id):
        raise HTTPException(404, detail="DataflowState nicht gefunden.")
    if "dataflow_state" in body and isinstance(body["dataflow_state"], dict):
        ok = await dsr.update_dataflow_state(dataflow_state_id, body["dataflow_state"])
    else:
        nodes = body.get("nodes")
        edges = body.get("edges")
        if nodes is None and edges is None:
            raise HTTPException(422, detail="Keine gültigen Felder zum Update (nodes/edges/dataflow_state).")
        cur = await dsr.get_dataflow_state(dataflow_state_id) or {"nodes": [], "edges": []}
        new_state = {**cur, "nodes": nodes if nodes is not None else cur.get("nodes", []), "edges": edges if edges is not None else cur.get("edges", [])}
        ok = await dsr.update_dataflow_state(dataflow_state_id, new_state)
    if not ok:
        raise HTTPException(500, detail="Update fehlgeschlagen.")
    return (await dsr.get_by_id(dataflow_state_id)) or {}


@router.delete("/dataflow-states/{dataflow_state_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dataflow_state(
    dataflow_state_id: str,
    dsr: DataflowStateRepository = Depends(get_dataflow_state_repository),
) -> None:
    if not await dsr.delete_by_id(dataflow_state_id):
        raise HTTPException(404, detail="DataflowState nicht gefunden.")


# --- Plugin-Konfigurationen (kein in-place-Update) ---


@router.get("/plugin-configurations")
async def list_plugin_configurations(
    pagination: tuple[int, int] = Depends(_pagination),
    pcr: PluginConfigurationRepository = Depends(get_plugin_configuration_repository),
) -> dict[str, Any]:
    page, page_size = pagination
    raw = await pcr.list_configurations(page=page, page_size=page_size)
    return apply_summary_to_page(raw, summarize_plugin_configuration_list_item)


@router.get("/plugin-configurations/{plugin_configuration_id}")
async def get_plugin_configuration(
    plugin_configuration_id: str,
    pcr: PluginConfigurationRepository = Depends(get_plugin_configuration_repository),
) -> dict[str, Any]:
    doc = await pcr.find_by_id(plugin_configuration_id)
    if not doc:
        raise HTTPException(404, detail="Plugin-Konfiguration nicht gefunden.")
    return doc


@router.post("/plugin-configurations", status_code=status.HTTP_201_CREATED)
async def post_plugin_configuration(
    request: PluginConfigurationCreateRequest = Body(...),
    pcr: PluginConfigurationRepository = Depends(get_plugin_configuration_repository),
) -> dict[str, Any]:
    if await pcr.find_by_id(request.plugin_configuration_id):
        raise HTTPException(409, detail="plugin_configuration_id existiert bereits.")
    doc: dict[str, Any] = {
        "plugin_configuration_id": request.plugin_configuration_id,
        "by_plugin_worker_id": request.by_plugin_worker_id,
    }
    await pcr.insert(doc)
    return (await pcr.find_by_id(request.plugin_configuration_id)) or doc


@router.delete("/plugin-configurations/{plugin_configuration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin_configuration(
    plugin_configuration_id: str,
    pcr: PluginConfigurationRepository = Depends(get_plugin_configuration_repository),
) -> None:
    if not await pcr.delete_by_id(plugin_configuration_id):
        raise HTTPException(404, detail="Plugin-Konfiguration nicht gefunden.")


# --- Events (Ergänzung: POST) ---


@router.post("/events", status_code=status.HTTP_201_CREATED)
async def post_event(
    request: EventCreateRequest = Body(...),
    event_repo: EventRepository = Depends(get_event_repository),
) -> dict[str, Any]:
    ev: dict[str, Any] = {
        "pipeline_id": request.pipeline_id,
        "plugin_worker_id": request.plugin_worker_id,
        "process_id": request.pipeline_id,
        "subprocess_id": request.plugin_worker_id,
        "event_type": request.event_type,
        "event_time": datetime.now(timezone.utc),
    }
    if request.payload is not None:
        ev["payload"] = request.payload
    _id = await event_repo.insert(ev)
    return {"_id": _id, **{k: v for k, v in ev.items() if k != "_id"}}
