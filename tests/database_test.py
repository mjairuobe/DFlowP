"""Tests für die MongoDB-Verbindung und alle Repositories."""

import os
import re
import pytest
import pytest_asyncio

from dflowp.infrastructure.database.data_repository import DataRepository
from dflowp.infrastructure.database.data_item_repository import DataItemRepository
from dflowp.infrastructure.database.dataset_repository import DatasetRepository
from dflowp.infrastructure.database.event_repository import EventRepository
from dflowp.infrastructure.database.mongo import (
    resolve_mongodb_uri,
    close_mongodb_connection,
    connect_to_mongodb,
    get_database,
)
from dflowp.infrastructure.database.process_repository import ProcessRepository


TIMESTAMP_HUMAN_PATTERN = re.compile(r"^\d{2}_\d{2}_\d{4}_\d{2}:\d{2}_UTC[+-]\d+$")

@pytest_asyncio.fixture(scope="module", autouse=True)
async def cleanup_database():
    """Löscht alle Collections in der dflowp_test-Datenbank."""
    uri = os.environ.get("MONGODB_URI", resolve_mongodb_uri())
    db = await connect_to_mongodb(uri=uri, database_name="dflowp_test")
    collections = await db.list_collection_names()
    for coll in collections:
        await db[coll].delete_many({})
    await close_mongodb_connection()

def should_delete():
    # Lösche Testdaten nur, wenn '--no-delete' nicht als pytest-Parameter übergeben wurde
    import sys
    return "--no-delete" not in sys.argv

@pytest.mark.asyncio
async def test_mongodb_connection():
    """Testet ob die MongoDB-Verbindung hergestellt werden kann."""
    uri = os.environ.get("MONGODB_URI", resolve_mongodb_uri())
    db = await connect_to_mongodb(uri=uri, database_name="dflowp_test")
    assert db is not None
    assert db.name == "dflowp_test"

    # Ping zur Bestätigung
    await db.command("ping")

    await close_mongodb_connection()


@pytest.mark.asyncio
async def test_mongodb_connection_reuses_singleton():
    """Testet ob mehrfache Verbindungen dieselbe Instanz nutzen."""
    uri = os.environ.get("MONGODB_URI", resolve_mongodb_uri())
    db1 = await connect_to_mongodb(
        uri=uri,
        database_name="dflowp_test",
    )
    db2 = await connect_to_mongodb(
        uri=uri,
        database_name="dflowp_test",
    )
    assert db1 is db2
    await close_mongodb_connection()


@pytest_asyncio.fixture
async def db_session():
    """Setup und Teardown für Repo-Tests."""
    uri = os.environ.get("MONGODB_URI", resolve_mongodb_uri())
    await connect_to_mongodb(
        uri=uri,
        database_name="dflowp_test",
    )
    yield get_database()
    await close_mongodb_connection()


@pytest.mark.asyncio
async def test_process_repository_crud(db_session):
    """Testet ProcessRepository: Insert und Find."""
    repo = ProcessRepository()
    await repo.create_indexes()

    process = {
        "process_id": "proc_test_001",
        "software_version": "1.0.0",
        "status": "running",
    }
    inserted_id = await repo.insert(process)
    assert inserted_id

    found = await repo.find_by_id("proc_test_001")
    assert found is not None
    assert found["process_id"] == "proc_test_001"
    assert found["status"] == "running"
    assert isinstance(found["timestamp_ms"], int)
    assert isinstance(found["timestamp_human"], str)
    assert TIMESTAMP_HUMAN_PATTERN.match(found["timestamp_human"])

    updated = await repo.update("proc_test_001", {"status": "completed"})
    assert updated is True

    found2 = await repo.find_by_id("proc_test_001")
    assert found2["status"] == "completed"

    # Cleanup
    if should_delete():
        await db_session[ProcessRepository.COLLECTION_NAME].delete_one(
            {"process_id": "proc_test_001"}
        )


@pytest.mark.asyncio
async def test_data_repository_crud(db_session):
    """Testet DataRepository: Insert und Find (Wrapper-Test)."""
    repo = DataRepository()
    await repo.create_indexes()

    data = {
        "data_id": "data_test_001",
        "type": "output",
        "content": {"value": 42},
    }
    inserted_id = await repo.insert(data)
    assert inserted_id

    found = await repo.find_by_id("data_test_001")
    assert found is not None
    assert found["data_id"] == "data_test_001"
    assert found["content"]["value"] == 42
    # Wrapper soll doc_type hinzugefügt haben
    assert found.get("doc_type") == "data"

    if should_delete():
        # Cleanup in der neuen unified collection
        await db_session[DataItemRepository.COLLECTION_NAME].delete_one(
            {"id": "data_test_001"}
        )


@pytest.mark.asyncio
async def test_dataset_repository_crud(db_session):
    """Testet DatasetRepository: Insert und Find (Wrapper-Test)."""
    repo = DatasetRepository()
    await repo.create_indexes()

    dataset = {
        "dataset_id": "ds_test_001",
        "data_ids": ["data_1", "data_2"],
    }
    inserted_id = await repo.insert(dataset)
    assert inserted_id

    found = await repo.find_by_id("ds_test_001")
    assert found is not None
    assert found["dataset_id"] == "ds_test_001"
    assert len(found["data_ids"]) == 2
    # Wrapper soll doc_type hinzugefügt haben
    assert found.get("doc_type") == "dataset"

    # Cleanup
    if should_delete():
        # Cleanup in der neuen unified collection
        await db_session[DataItemRepository.COLLECTION_NAME].delete_one(
            {"id": "ds_test_001"}
        )


@pytest.mark.asyncio
async def test_data_item_repository_crud(db_session):
    """Testet DataItemRepository (unified repository) direkt."""
    repo = DataItemRepository()
    await repo.create_indexes()

    # Test: Data-Dokument einfügen
    data_doc = {
        "id": "data_item_test_001",
        "doc_type": "data",
        "type": "output",
        "content": {"value": 100},
    }
    data_id = await repo.insert(data_doc)
    assert data_id

    found_data = await repo.find_by_id("data_item_test_001")
    assert found_data is not None
    assert found_data["id"] == "data_item_test_001"
    assert found_data["doc_type"] == "data"
    assert found_data["content"]["value"] == 100
    assert isinstance(found_data["timestamp_ms"], int)
    assert isinstance(found_data["timestamp_human"], str)
    assert TIMESTAMP_HUMAN_PATTERN.match(found_data["timestamp_human"])

    # Test: Dataset-Dokument einfügen
    dataset_doc = {
        "id": "dataset_item_test_001",
        "doc_type": "dataset",
        "data_ids": ["data_1", "data_2", "data_3"],
    }
    dataset_id = await repo.insert(dataset_doc)
    assert dataset_id

    found_dataset = await repo.find_by_id("dataset_item_test_001")
    assert found_dataset is not None
    assert found_dataset["id"] == "dataset_item_test_001"
    assert found_dataset["doc_type"] == "dataset"
    assert len(found_dataset["data_ids"]) == 3
    assert isinstance(found_dataset["timestamp_ms"], int)
    assert isinstance(found_dataset["timestamp_human"], str)
    assert TIMESTAMP_HUMAN_PATTERN.match(found_dataset["timestamp_human"])

    # Cleanup
    if should_delete():
        await db_session[DataItemRepository.COLLECTION_NAME].delete_many(
            {"id": {"$in": ["data_item_test_001", "dataset_item_test_001"]}}
        )


@pytest.mark.asyncio
async def test_data_item_repository_type_validation(db_session):
    """Testet dass DataItemRepository doc_type validiert."""
    repo = DataItemRepository()
    await repo.create_indexes()

    # Test: Fehler bei fehlender doc_type
    with pytest.raises(ValueError, match="doc_type field is required"):
        await repo.insert({"id": "test_001", "content": {}})

    # Test: Fehler bei ungültigem doc_type
    with pytest.raises(ValueError, match="Invalid doc_type"):
        await repo.insert({
            "id": "test_002",
            "doc_type": "invalid",
            "content": {}
        })

    # Test: Fehler bei Data ohne content
    with pytest.raises(ValueError, match="content field is required"):
        await repo.insert({
            "id": "test_003",
            "doc_type": "data"
        })

    # Test: Fehler bei Dataset ohne data_ids
    with pytest.raises(ValueError, match="data_ids field is required"):
        await repo.insert({
            "id": "test_004",
            "doc_type": "dataset"
        })


@pytest.mark.asyncio
async def test_event_repository_crud(db_session):
    """Testet EventRepository: Insert, Find, Count."""
    repo = EventRepository()
    await repo.create_indexes()

    event = {
        "process_id": "proc_evt_001",
        "subprocess_id": "sub_evt_001",
        "event_type": "EVENT_STARTED",
        "subprocess_instance_id": 1,
    }
    inserted_id = await repo.insert(event)
    assert inserted_id

    count = await repo.count_by_process("proc_evt_001")
    assert count >= 1

    events = []
    async for e in repo.find_by_process_id("proc_evt_001"):
        events.append(e)
    assert len(events) >= 1
    assert events[0]["event_type"] == "EVENT_STARTED"

    latest = await repo.get_latest_event("proc_evt_001", "sub_evt_001")
    assert latest is not None
    assert latest["event_type"] == "EVENT_STARTED"
    assert isinstance(latest["timestamp_ms"], int)
    assert isinstance(latest["timestamp_human"], str)
    assert TIMESTAMP_HUMAN_PATTERN.match(latest["timestamp_human"])

    if should_delete():
        await db_session[EventRepository.COLLECTION_NAME].delete_many(
            {"process_id": "proc_evt_001"}
        )

    await db_session[EventRepository.COLLECTION_NAME].delete_many(
        {"process_id": "proc_evt_001"}
    )
