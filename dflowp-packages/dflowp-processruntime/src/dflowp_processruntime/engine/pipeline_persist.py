"""Delegiert an :meth:`PipelineRepository.insert_from_configuration` (ein Einstiegspunkt für Skripte)."""

from typing import Any

from dflowp_core.database.pipeline_repository import PipelineRepository
from dflowp_processruntime.processes.process_configuration import PipelineConfiguration


async def insert_full_pipeline(
    configuration: PipelineConfiguration,
    *,
    status: str = "running",
    pipeline_repo: PipelineRepository | None = None,
) -> dict[str, Any]:
    pr = pipeline_repo or PipelineRepository()
    return await pr.insert_from_configuration(configuration, status=status)
