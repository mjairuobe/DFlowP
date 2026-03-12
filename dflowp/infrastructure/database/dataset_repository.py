"""Repository für Datasets (Wrapper für einheitliches DataItemRepository)."""

from typing import Any, Optional

from dflowp.infrastructure.database.data_item_repository import DataItemRepository


class DatasetRepository:
    """
    Wrapper-Klasse für Rückwärtskompatibilität.

    Delegiert an das einheitliche DataItemRepository und mappt Feldnamen
    zwischen "dataset_id" (alte API) und "id" (neue interne Darstellung).
    """

    COLLECTION_NAME = "datasets"  # Behält alte Konstante für Kompatibilität

    def __init__(self) -> None:
        self._unified_repo = DataItemRepository()

    async def create_indexes(self) -> None:
        """Erstellt Indizes im einheitlichen Repository."""
        await self._unified_repo.create_indexes()

    async def insert(self, dataset: dict[str, Any]) -> str:
        """
        Speichert ein Dataset. Mappt dataset_id zu id und setzt doc_type.

        Args:
            dataset: Datasetdict mit mindestens dataset_id, data_ids

        Returns:
            Die MongoDB _id des eingefügten Dokuments
        """
        # Konvertiere dataset_id zu id für internes Format
        doc = dict(dataset)
        if "dataset_id" in doc:
            doc["id"] = doc.pop("dataset_id")

        # Stelle sicher, dass doc_type gesetzt ist
        if "doc_type" not in doc:
            doc["doc_type"] = "dataset"

        return await self._unified_repo.insert(doc)

    async def find_by_id(self, dataset_id: str) -> Optional[dict[str, Any]]:
        """
        Findet ein Dataset anhand der dataset_id.

        Mappt das interne "id"-Feld zurück zu "dataset_id" für Rückwärtskompatibilität.

        Args:
            dataset_id: Die Dataset-ID

        Returns:
            Das Datasetdict mit dataset_id (statt id) oder None
        """
        doc = await self._unified_repo.find_by_id(dataset_id)
        if doc:
            # Stelle "dataset_id" für Rückwärtskompatibilität wieder her
            if "id" in doc:
                doc["dataset_id"] = doc.pop("id")
        return doc
