"""Plugin-Service für Clustering_DBSCAN."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
import uvicorn

from dflowp_core.database.dataset_repository import DatasetRepository
from dflowp_core.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    resolve_mongodb_uri,
)
from dflowp.plugin_clustering_dbscan.clustering_dbscan import ClusteringDBSCAN
from dflowp_processruntime.subprocesses.io_transformation_state import IOTransformationState
from dflowp_processruntime.subprocesses.subprocess_context import PluginWorkerContext

PLUGIN_NAME = "Clustering_DBSCAN"
PLUGIN_VERSION = os.environ.get("SOFTWARE_VERSION", "dev")
PLUGIN_SERVICE_NAME = "plugin-clustering-dbscan"


class PluginRunRequest(BaseModel):
    context: dict[str, Any] = Field(...)


class PluginRunResponse(BaseModel):
    io_transformation_states: list[dict[str, Any]]


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongodb(
        uri=resolve_mongodb_uri(),
        database_name=os.environ.get("MONGODB_DATABASE", "dflowp"),
    )
    try:
        yield
    finally:
        await close_mongodb_connection()


app = FastAPI(
    title="DFlowP Plugin Clustering_DBSCAN",
    version=PLUGIN_VERSION,
    lifespan=lifespan,
)
_plugin = ClusteringDBSCAN()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": PLUGIN_SERVICE_NAME}


@app.get("/plugin/info")
async def plugin_info() -> dict[str, Any]:
    return {
        "plugin_name": PLUGIN_NAME,
        "plugin_version": PLUGIN_VERSION,
        "service_name": PLUGIN_SERVICE_NAME,
        "capabilities": ["run", "health", "info"],
        "status": "ready",
    }


@app.post("/plugin/run", response_model=PluginRunResponse)
async def plugin_run(request: PluginRunRequest) -> PluginRunResponse:
    try:
        context = PluginWorkerContext.model_validate(request.context)
        dataset_repo = DatasetRepository()
        io_states: list[IOTransformationState] = await _plugin.run(
            context=context,
            dataset_repository=dataset_repo,
        )
        return PluginRunResponse(
            io_transformation_states=[state.to_dict() for state in io_states]
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Plugin run failed: {exc}",
        ) from exc


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PLUGIN_PORT", "8103")))


if __name__ == "__main__":
    main()
