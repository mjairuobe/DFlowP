"""MongoDB Verbindung für DFlowP."""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from dflowp.utils.logger import get_logger

logger = get_logger(__name__)

# Globale MongoDB-Instanz
_mongo_client: Optional[AsyncIOMotorClient] = None
_mongo_db: Optional[AsyncIOMotorDatabase] = None


async def connect_to_mongodb(
    uri: str = "mongodb://localhost:27017",
    database_name: str = "dflowp",
) -> AsyncIOMotorDatabase:
    """
    Stellt die Verbindung zur MongoDB her.

    Args:
        uri: MongoDB Connection URI
        database_name: Name der Datenbank

    Returns:
        Die verbundene Datenbank-Instanz
    """
    global _mongo_client, _mongo_db

    if _mongo_db is not None:
        return _mongo_db

    try:
        _mongo_client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=5000,
        )
        # Verbindung testen
        await _mongo_client.admin.command("ping")
        _mongo_db = _mongo_client[database_name]
        logger.info(
            "MongoDB verbunden: %s, Datenbank: %s",
            uri.split("@")[-1] if "@" in uri else uri,
            database_name,
        )
        return _mongo_db
    except Exception as e:
        logger.exception("MongoDB Verbindungsfehler: %s", e)
        raise


async def close_mongodb_connection() -> None:
    """Schließt die MongoDB-Verbindung."""
    global _mongo_client, _mongo_db

    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
        _mongo_db = None
        logger.info("MongoDB-Verbindung geschlossen")


def get_database() -> AsyncIOMotorDatabase:
    """
    Gibt die aktuelle Datenbank-Instanz zurück.

    Raises:
        RuntimeError: Wenn noch keine Verbindung hergestellt wurde
    """
    if _mongo_db is None:
        raise RuntimeError(
            "MongoDB nicht verbunden. Rufe zuerst connect_to_mongodb() auf."
        )
    return _mongo_db
