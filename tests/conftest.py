"""Pytest-Konfiguration und Fixtures für DFlowP-Tests."""

import os
import sys
from pathlib import Path
import uuid

import pytest

# Monorepo: ohne installierte Wheels müssen die src-Pfade für Imports erreichbar sein
# (zusätzlich zu [tool.pytest.ini_options] pythonpath in pyproject.toml).
_ROOT = Path(__file__).resolve().parents[1]
for _p in (
    _ROOT / "dflowp-packages" / "dflowp-core" / "src",
    _ROOT / "dflowp-packages" / "dflowp-processruntime" / "src",
):
    if _p.is_dir():
        s = str(_p)
        if s not in sys.path:
            sys.path.insert(0, s)


import pytest_asyncio

from dflowp_core.eventinterfaces.event_bus import EventBus
from dflowp_core.database.mongo import (
    close_mongodb_connection,
    connect_to_mongodb,
    get_database,
    resolve_mongodb_uri,
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
