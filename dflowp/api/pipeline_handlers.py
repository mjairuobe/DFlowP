"""Gemeinsame Logik zum Anlegen einer Pipeline (Mongo: Dataflow, Config, State, Pipeline-Referenzen)."""

from typing import Any, Optional

from fastapi import HTTPException, status

from dflowp.api.process_persist import persist_input_dataset_rows
from dflowp_processruntime.processes.process_configuration import ProcessConfiguration
from dflowp_core.database.data_item_repository import DataItemRepository
from dflowp_core.database.process_repository import ProcessRepository


async def create_pipeline_document(
    *,
    pipeline_id: str,
    software_version: str,
    input_dataset_id: str,
    dataflow: dict[str, Any],
    plugin_config: dict[str, dict[str, Any]],
    input_data: Optional[list[dict[str, Any]]],
    start_immediately: bool,
    process_repo: ProcessRepository,
    data_item_repo: DataItemRepository,
) -> dict:
    """Legt eine Pipeline inkl. referenzierter Dokumente an."""
    if await process_repo.find_by_id(pipeline_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline '{pipeline_id}' existiert bereits.",
        )
    try:
        configuration = ProcessConfiguration.from_dict(
            {
                "pipeline_id": pipeline_id,
                "process_id": pipeline_id,
                "software_version": software_version,
                "input_dataset_id": input_dataset_id,
                "dataflow": dataflow,
                "plugin_config": plugin_config,
                "subprocess_config": plugin_config,
            }
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültige Pipeline-Konfiguration: {exc}",
        ) from exc

    configuration.apply_default_openai_key_from_env()
    configuration.apply_software_version_from_env()

    if input_data is not None:
        existing_ds = await data_item_repo.find_dataset_by_id(input_dataset_id)
        if existing_ds:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Dataset '{input_dataset_id}' existiert bereits; Input kann nicht angelegt werden.",
            )
        await persist_input_dataset_rows(
            data_item_repo=data_item_repo,
            dataset_id=input_dataset_id,
            rows=input_data,
        )

    st = "running" if start_immediately else "pending"
    created = await process_repo.insert_from_configuration(configuration, status=st)
    if not created:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline wurde nicht gespeichert.",
        )
    return created
