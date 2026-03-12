"""Übergeordnete Datenklasse mit ID zur Referenzierung in der Datenbank."""

from typing import Any, Optional
from typing_extensions import Literal

from pydantic import BaseModel, Field


class Data(BaseModel):
    """
    Abstrakte Datenklasse.
    Referenziert Daten in der Datenbank über data_id.
    """

    data_id: str = Field(..., description="Eindeutige ID zur Lokalisierung in der Datenbank")
    content: dict[str, Any] = Field(default_factory=dict, description="Dateninhalt")
    type: str = Field(default="generic", description="Typ der Daten (z.B. input, output)")
    doc_type: Literal["data"] = Field(default="data", description="Dokumenttyp ('data' für einzelne Daten)")

    def to_db_dict(self) -> dict[str, Any]:
        """Konvertiert zu Dict für die Datenbank."""
        return self.model_dump()

    @classmethod
    def from_db_dict(cls, d: dict[str, Any]) -> "Data":
        """Erstellt aus Datenbank-Dict."""
        return cls(**d)
