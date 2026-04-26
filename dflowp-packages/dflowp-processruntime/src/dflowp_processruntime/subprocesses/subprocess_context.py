"""Kontext für einen zu startenden Plugin-Worker (Subprozess)."""

from typing import Any, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from dflowp_processruntime.datastructures.data import Data
from dflowp_processruntime.datastructures.dataset import Dataset


class SubprocessContext(BaseModel):
    """Laufzeitkontext für einen Plugin-Worker."""

    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )

    pipeline_id: str = Field(validation_alias=AliasChoices("pipeline_id", "process_id"))
    plugin_worker_id: str = Field(validation_alias=AliasChoices("plugin_worker_id", "subprocess_id"))
    plugin_type: str = Field(validation_alias=AliasChoices("plugin_type", "subprocess_type"))
    config: dict[str, Any] = Field(default_factory=dict)
    input_dataset: Optional[Dataset] = None
    input_data: list[Data] = Field(default_factory=list)

    @property
    def process_id(self) -> str:
        return self.pipeline_id

    @property
    def subprocess_id(self) -> str:
        return self.plugin_worker_id

    @property
    def subprocess_type(self) -> str:
        return self.plugin_type
