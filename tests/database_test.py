"""Tests für die MongoDB-Verbindung und alle Repositories."""

import pytest
import pytest_asyncio

from dflowp.infrastructure.database.data_repository import DataRepository
from dflowp.infrastructure.database.dataset_repository import DatasetRepository
from dflowp.infrastructure.database.event_repository import EventRepository
from dflowp.infrastructure.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    get_database,
)
from dflowp.infrastructure.database.process_repository import ProcessRepository

@pytest_asyncio.fixture(scope="module", autouse=True)
async def cleanup_database():
    """Löscht alle Collections in der dflowp_test-Datenbank."""
    db = await connect_to_mongodb(uri="mongodb://localhost:27017", database_name="dflowp_test")
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
    uri = "mongodb://localhost:27017"
    db = await connect_to_mongodb(uri=uri, database_name="dflowp_test")
    assert db is not None
    assert db.name == "dflowp_test"

    # Ping zur Bestätigung
    await db.client.admin.command("ping")

    await close_mongodb_connection()


@pytest.mark.asyncio
async def test_mongodb_connection_reuses_singleton():
    """Testet ob mehrfache Verbindungen dieselbe Instanz nutzen."""
    db1 = await connect_to_mongodb(
        uri="mongodb://localhost:27017",
        database_name="dflowp_test",
    )
    db2 = await connect_to_mongodb(
        uri="mongodb://localhost:27017",
        database_name="dflowp_test",
    )
    assert db1 is db2
    await close_mongodb_connection()


@pytest_asyncio.fixture
async def db_session():
    """Setup und Teardown für Repo-Tests."""
    await connect_to_mongodb(
        uri="mongodb://localhost:27017",
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
    """Testet DataRepository: Insert und Find."""
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

    if should_delete():
        await db_session[DataRepository.COLLECTION_NAME].delete_one(
            {"data_id": "data_test_001"}
        )


@pytest.mark.asyncio
async def test_dataset_repository_crud(db_session):
    """Testet DatasetRepository: Insert und Find."""
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

    # Cleanup
    if should_delete():
        await db_session[DatasetRepository.COLLECTION_NAME].delete_one(
            {"dataset_id": "ds_test_001"}
        )


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

    if should_delete():
        await db_session[EventRepository.COLLECTION_NAME].delete_many(
            {"process_id": "proc_evt_001"}
        )

    await db_session[EventRepository.COLLECTION_NAME].delete_many(
        {"process_id": "proc_evt_001"}
    )
