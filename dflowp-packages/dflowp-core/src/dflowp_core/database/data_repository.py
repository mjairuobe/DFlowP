"""Repository für Input- und Output-Daten (Wrapper für einheitliches DataItemRepository)."""

from typing import Any, Optional

from dflowp_core.database.data_item_repository import DataItemRepository


class DataRepository:
    """
    Wrapper-Klasse für Rückwärtskompatibilität.

    Delegiert an das einheitliche DataItemRepository und mappt Feldnamen
    zwischen "data_id" (alte API) und "id" (neue interne Darstellung).
    """

    COLLECTION_NAME = "data"  # Behält alte Konstante für Kompatibilität

    def __init__(self) -> None:
        self._unified_repo = DataItemRepository()

    async def create_indexes(self) -> None:
        """Erstellt Indizes im einheitlichen Repository."""
        await self._unified_repo.create_indexes()

    async def insert(self, data: dict[str, Any]) -> str:
        """
        Speichert Daten. Mappt data_id zu id und setzt doc_type.

        Args:
            data: Datendict mit mindestens data_id, content, type

        Returns:
            Die MongoDB _id des eingefügten Dokuments
        """
        # Konvertiere data_id zu id für internes Format
        doc = dict(data)
        if "data_id" in doc:
            doc["id"] = doc.pop("data_id")

        # Stelle sicher, dass doc_type gesetzt ist
        if "doc_type" not in doc:
            doc["doc_type"] = "data"

        return await self._unified_repo.insert(doc)

    async def find_by_id(self, data_id: str) -> Optional[dict[str, Any]]:
        """
        Findet Daten anhand der data_id.

        Mappt das interne "id"-Feld zurück zu "data_id" für Rückwärtskompatibilität.

        Args:
            data_id: Die Daten-ID

        Returns:
            Das Datendict mit data_id (statt id) oder None
        """
        doc = await self._unified_repo.find_by_id(data_id)
        if doc:
            # Stelle "data_id" für Rückwärtskompatibilität wieder her
            if "id" in doc:
                doc["data_id"] = doc.pop("id")
        return doc
