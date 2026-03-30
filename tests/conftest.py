"""Pytest-Konfiguration und Fixtures für DFlowP-Tests."""

import os
import uuid

import pytest


import pytest_asyncio

from dflowp.core.events.event_bus import EventBus
from dflowp.infrastructure.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    get_database,
)

def pytest_addoption(parser):
    parser.addoption(
        "--no-delete",
        action="store_true",
        default=False,
        help="Testdaten nach den Tests nicht löschen",
    )


@pytest_asyncio.fixture
async def mongodb_connection():
    """Stellt eine MongoDB-Verbindung für Tests her."""
    uri = os.environ.get("MONGODB_URI", resolve_mongodb_uri())
    db_name = os.environ.get("MONGODB_TEST_DB", "dflowp_test")
    await connect_to_mongodb(uri=uri, database_name=db_name)
    yield get_database()
    await close_mongodb_connection()


@pytest_asyncio.fixture
async def event_bus_fresh():
    """Gibt einen frischen EventBus ohne Persistenz (für isolierte Event-Tests)."""
    return EventBus()


@pytest.fixture
def unique_process_id():
    """Generiert eine eindeutige Prozess-ID für Tests."""
    return f"test_process_{uuid.uuid4().hex[:12]}"


@pytest.fixture
def unique_subprocess_id():
    """Generiert eine eindeutige Subprozess-ID für Tests."""
    return f"test_subprocess_{uuid.uuid4().hex[:12]}"
