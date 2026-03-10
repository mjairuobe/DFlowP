"""SubprocessContext - Kontext für einen zu startenden Subprozess."""

from typing import Any, Optional

from pydantic import BaseModel, Field

from dflowp.core.datastructures.data import Data
from dflowp.core.datastructures.dataset import Dataset


class SubprocessContext(BaseModel):
    """
    Enthält den kompletten Kontext, den ein zu startender Subprozess benötigt.
    Zusammengesetzt aus Prozesskonfiguration und Input-Daten der Vorgänger-Subprozesse.
    """

    process_id: str
    subprocess_id: str
    subprocess_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    input_dataset: Optional[Dataset] = None
    input_data: list[Data] = Field(default_factory=list)

    class Config:
        arbitrary_types_allowed = True
