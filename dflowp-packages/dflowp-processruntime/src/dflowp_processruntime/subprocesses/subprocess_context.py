"""Kontext für einen zu startenden Plugin-Worker."""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from dflowp_processruntime.datastructures.data import Data
from dflowp_processruntime.datastructures.dataset import Dataset


class PluginWorkerContext(BaseModel):
    """Laufzeitkontext für einen Plugin-Worker."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    pipeline_id: str
    plugin_worker_id: str
    plugin_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    input_dataset: Optional[Dataset] = None
    input_data: list[Data] = Field(default_factory=list)

