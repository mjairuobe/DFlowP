"""Rückwärtskompatibler Import – nutzt :class:`PipelineRepository`."""

from dflowp_core.database.pipeline_repository import (  # noqa: F401
    PipelineRepository,
    ProcessRepository,
)

__all__ = ["PipelineRepository", "ProcessRepository"]
