"""Dataset - Gruppierung von Data-Referenzen."""

from typing_extensions import Literal

from pydantic import BaseModel, Field


class Dataset(BaseModel):
    """
    Enthält Mengen von Daten (Data) ohne Ordnung.
    Referenziert auf Dataset in der Datenbank (dataset_id).
    """

    dataset_id: str = Field(..., description="Eindeutige ID des Datasets")
    data_ids: list[str] = Field(default_factory=list, description="IDs der enthaltenen Daten")
    doc_type: Literal["dataset"] = Field(default="dataset", description="Dokumenttyp ('dataset' für Datengruppen)")

    def to_db_dict(self) -> dict:
        """Konvertiert zu Dict für die Datenbank."""
        return {"dataset_id": self.dataset_id, "data_ids": self.data_ids, "doc_type": "dataset"}

    @classmethod
    def from_db_dict(cls, d: dict) -> "Dataset":
        """Erstellt aus Datenbank-Dict."""
        return cls(dataset_id=d["dataset_id"], data_ids=d.get("data_ids", []))
