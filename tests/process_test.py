"""
Tests für Prozesse, Subprozesse, DataFlow und Plugins.

Abgedeckte Bereiche:
- DataFlow Parsen & Traversierung
- IOTransformationState
- ProcessConfiguration & ProcessState
- Plugin-Loader
- ProcessEngine (mit gemockten Repositories)
- FetchFeedItems Plugin (mit gemocktem HTTP)
- EmbedData Plugin (mit gemockter OpenAI API)
"""

import asyncio
import os
import uuid
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dflowp.core.dataflow.dataflow import DataFlow, DataflowEdge, DataflowNodeDef
from dflowp.core.dataflow.dataflow_node import DataflowNodeState
from dflowp.core.dataflow.dataflow_parser import parse_dataflow
from dflowp.core.dataflow.dataflow_state import DataflowState
from dflowp.core.datastructures.data import Data
from dflowp.core.engine.process_engine import ProcessEngine
from dflowp.core.events.event_bus import EventBus
from dflowp.core.events.event_service import EventService
from dflowp.core.processes.process_configuration import ProcessConfiguration
from dflowp.core.processes.process_state import ProcessState
from dflowp.core.subprocesses.io_transformation_state import (
    IOTransformationState,
    TransformationStatus,
)
from dflowp.core.subprocesses.subprocess import BaseSubprocess
from dflowp.core.subprocesses.subprocess_context import SubprocessContext
from dflowp.infrastructure.plugins.plugin_loader import (
    get_subprocess,
    load_builtin_plugins,
    register_subprocess,
)
from dflowp.plugins.embedding.embed_data import EmbedData
from dflowp.plugins.fetch_feed_items.fetch_feed_items import FetchFeedItems


# ---------------------------------------------------------------------------
# Hilfsfunktionen & Fixtures
# ---------------------------------------------------------------------------

SAMPLE_RSS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Article 1</title>
      <link>https://example.com/article-1</link>
      <description>Description of article 1</description>
      <pubDate>Mon, 10 Mar 2025 10:00:00 +0000</pubDate>
    </item>
    <item>
      <title>Article 2</title>
      <link>https://example.com/article-2</link>
      <description>Description of article 2</description>
      <pubDate>Mon, 10 Mar 2025 11:00:00 +0000</pubDate>
    </item>
  </channel>
</rss>"""

MOCK_EMBEDDING = [0.1, 0.2, 0.3, 0.4, 0.5]

_SIMPLE_DATAFLOW_CONFIG = {
    "nodes": [
        {"subprocess_id": "A", "subprocess_type": "TypeA"},
        {"subprocess_id": "B", "subprocess_type": "TypeB"},
    ],
    "edges": [{"from": "A", "to": "B"}],
}


def _make_process_config(
    process_id: str = "proc_test",
    nodes: Optional[list] = None,
    edges: Optional[list] = None,
    subprocess_config: Optional[dict] = None,
) -> ProcessConfiguration:
    nodes = nodes or [{"subprocess_id": "A", "subprocess_type": "TypeA"}]
    return ProcessConfiguration.from_dict(
        {
            "process_id": process_id,
            "software_version": "1.0.0",
            "input_dataset_id": "ds_test",
            "dataflow": {"nodes": nodes, "edges": edges or []},
            "subprocess_config": subprocess_config or {},
        }
    )


def _make_feed_context(
    feeds: list[dict],
    process_id: str = "proc_fetch_test",
) -> SubprocessContext:
    return SubprocessContext(
        process_id=process_id,
        subprocess_id="FetchFeedItems1",
        subprocess_type="FetchFeedItems",
        config={},
        input_data=[
            Data(data_id=f"feed_{i}", content=feed, type="input")
            for i, feed in enumerate(feeds)
        ],
    )


def _make_article_context(
    articles: list[dict],
    config: Optional[dict] = None,
    process_id: str = "proc_embed_test",
) -> SubprocessContext:
    return SubprocessContext(
        process_id=process_id,
        subprocess_id="EmbedData1",
        subprocess_type="EmbedData",
        config=config or {},
        input_data=[
            Data(data_id=f"article_{i}", content=art, type="output")
            for i, art in enumerate(articles)
        ],
    )


class _IsolatedEventService(EventService):
    """EventService mit dediziertem EventBus für isolierte Tests."""

    def __init__(self) -> None:
        self._bus = EventBus()


@pytest.fixture
def isolated_event_service():
    return _IsolatedEventService()


def _make_mock_process_config_doc(process_id: str, nodes=None, edges=None):
    """Erstellt ein Prozess-Dokument-Dict für Mock-Repositories."""
    nodes = nodes or [{"subprocess_id": "A", "subprocess_type": "TypeA"}]
    return {
        "process_id": process_id,
        "status": "running",
        "configuration": {
            "process_id": process_id,
            "software_version": "1.0.0",
            "input_dataset_id": "ds_test",
            "dataflow": {"nodes": nodes, "edges": edges or []},
            "subprocess_config": {},
        },
    }


@pytest.fixture
def mock_repos():
    """Erstellt Mock-Repositories, die eine einfache Prozesskonfiguration kennen."""
    process_repo = AsyncMock()
    process_repo.insert = AsyncMock(return_value="mock_inserted_id")
    process_repo.update = AsyncMock(return_value=True)
    # find_by_id muss immer ein dict zurückgeben (kein AsyncMock),
    # sonst gibt .get() darauf eine Coroutine zurück
    process_repo.find_by_id = AsyncMock(
        return_value=_make_mock_process_config_doc("proc_test")
    )

    dataflow_state_repo = AsyncMock()
    dataflow_state_repo.update_node_state = AsyncMock(return_value=True)
    dataflow_state_repo.get_dataflow_state = AsyncMock(
        return_value={
            "nodes": [
                {
                    "subprocess_id": "A",
                    "subprocess_type": "TypeA",
                    "event_status": "EVENT_COMPLETED",
                    "io_transformation_states": [],
                }
            ],
            "edges": [],
        }
    )

    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()
    data_repo.find_by_id = AsyncMock(
        return_value={
            "data_id": "d1",
            "content": {"text": "input_data"},
            "type": "input",
        }
    )

    dataset_repo = AsyncMock()
    dataset_repo.find_by_id = AsyncMock(
        return_value={"dataset_id": "ds_test", "data_ids": ["d1"]}
    )

    return process_repo, dataflow_state_repo, data_repo, dataset_repo


# ===========================================================================
# Abschnitt 1: DataFlow-Modell-Tests
# ===========================================================================


def test_dataflow_parsing_nodes_and_edges():
    """DataFlow wird korrekt aus einem Dict geparst."""
    df = parse_dataflow(_SIMPLE_DATAFLOW_CONFIG)

    assert len(df.nodes) == 2
    assert len(df.edges) == 1
    assert df.nodes[0].subprocess_id == "A"
    assert df.nodes[0].subprocess_type == "TypeA"
    assert df.edges[0].from_node == "A"
    assert df.edges[0].to_node == "B"


def test_dataflow_root_nodes_single():
    """Root-Knoten (ohne Vorgänger) werden korrekt erkannt."""
    df = parse_dataflow(_SIMPLE_DATAFLOW_CONFIG)
    roots = df.get_root_nodes()

    assert len(roots) == 1
    assert roots[0] == "A"


def test_dataflow_root_nodes_multiple():
    """Mehrere Root-Knoten werden alle erkannt."""
    config = {
        "nodes": [
            {"subprocess_id": "A", "subprocess_type": "T"},
            {"subprocess_id": "B", "subprocess_type": "T"},
            {"subprocess_id": "C", "subprocess_type": "T"},
        ],
        "edges": [
            {"from": "A", "to": "C"},
            {"from": "B", "to": "C"},
        ],
    }
    df = parse_dataflow(config)
    roots = set(df.get_root_nodes())

    assert roots == {"A", "B"}


def test_dataflow_successors_and_predecessors():
    """get_successors und get_predecessors funktionieren korrekt."""
    config = {
        "nodes": [
            {"subprocess_id": "A", "subprocess_type": "T"},
            {"subprocess_id": "B", "subprocess_type": "T"},
            {"subprocess_id": "C", "subprocess_type": "T"},
        ],
        "edges": [
            {"from": "A", "to": "B"},
            {"from": "A", "to": "C"},
        ],
    }
    df = parse_dataflow(config)

    assert set(df.get_successors("A")) == {"B", "C"}
    assert df.get_predecessors("B") == ["A"]
    assert df.get_predecessors("C") == ["A"]
    assert df.get_successors("B") == []
    assert df.get_successors("C") == []


def test_dataflow_get_node():
    """get_node gibt den richtigen Knoten zurück."""
    df = parse_dataflow(_SIMPLE_DATAFLOW_CONFIG)

    node = df.get_node("B")
    assert node is not None
    assert node.subprocess_type == "TypeB"

    assert df.get_node("NONEXISTENT") is None


def test_dataflow_state_from_dataflow():
    """DataflowState wird korrekt aus einem DataFlow initialisiert."""
    df = parse_dataflow(_SIMPLE_DATAFLOW_CONFIG)
    state = DataflowState.from_dataflow(df)

    assert len(state.nodes) == 2
    assert len(state.edges) == 1

    node_a = state.get_node("A")
    assert node_a is not None
    assert node_a.event_status == "Not Started"
    assert node_a.io_transformation_states == []


def test_dataflow_state_to_dict():
    """DataflowState.to_dict erzeugt ein korrektes Dict."""
    df = parse_dataflow(_SIMPLE_DATAFLOW_CONFIG)
    state = DataflowState.from_dataflow(df)
    d = state.to_dict()

    assert "nodes" in d
    assert "edges" in d
    assert d["nodes"][0]["subprocess_id"] == "A"
    assert d["edges"][0]["from"] == "A"


def test_dataflow_node_add_or_update_io_state():
    """DataflowNodeState.add_or_update_io_state fügt hinzu und aktualisiert korrekt."""
    node = DataflowNodeState(
        subprocess_id="A",
        subprocess_type="TypeA",
        event_status="Not Started",
        io_transformation_states=[],
    )

    s1 = IOTransformationState(
        input_data_id="inp_1",
        output_data_ids=["out_1"],
        status=TransformationStatus.FINISHED,
    )
    node.add_or_update_io_state(s1)
    assert len(node.io_transformation_states) == 1

    # Aktualisieren: dieselbe input_data_id
    s1_updated = IOTransformationState(
        input_data_id="inp_1",
        output_data_ids=["out_1", "out_2"],
        status=TransformationStatus.FINISHED,
    )
    node.add_or_update_io_state(s1_updated)
    assert len(node.io_transformation_states) == 1
    assert len(node.io_transformation_states[0].output_data_ids) == 2

    # Hinzufügen: neue input_data_id
    s2 = IOTransformationState(
        input_data_id="inp_2",
        output_data_ids=["out_3"],
        status=TransformationStatus.FINISHED,
    )
    node.add_or_update_io_state(s2)
    assert len(node.io_transformation_states) == 2


# ===========================================================================
# Abschnitt 2: IOTransformationState Tests
# ===========================================================================


def test_io_transformation_state_defaults():
    """IOTransformationState hat sinnvolle Standardwerte."""
    s = IOTransformationState(input_data_id="inp_0")

    assert s.status == TransformationStatus.NOT_STARTED
    assert s.output_data_ids == []
    assert s.quality is None


def test_io_transformation_state_to_dict():
    """to_dict liefert alle Felder korrekt."""
    s = IOTransformationState(
        input_data_id="inp_1",
        output_data_ids=["out_1", "out_2"],
        status=TransformationStatus.FINISHED,
        quality=0.95,
    )
    d = s.to_dict()

    assert d["input_data_id"] == "inp_1"
    assert d["output_data_ids"] == ["out_1", "out_2"]
    assert d["status"] == "Finished"
    assert d["quality"] == 0.95


def test_io_transformation_state_from_dict_roundtrip():
    """from_dict rekonstruiert den ursprünglichen State."""
    original = IOTransformationState(
        input_data_id="inp_2",
        output_data_ids=["out_3"],
        status=TransformationStatus.IN_PROGRESS,
        quality=0.5,
    )
    restored = IOTransformationState.from_dict(original.to_dict())

    assert restored.input_data_id == original.input_data_id
    assert restored.output_data_ids == original.output_data_ids
    assert restored.status == original.status
    assert restored.quality == original.quality


def test_io_transformation_state_failed_status():
    """FAILED-Status wird korrekt gesetzt und serialisiert."""
    s = IOTransformationState(
        input_data_id="inp_bad",
        output_data_ids=[],
        status=TransformationStatus.FAILED,
        quality=0.0,
    )
    assert s.status == TransformationStatus.FAILED
    assert s.to_dict()["status"] == "Failed"


# ===========================================================================
# Abschnitt 3: ProcessConfiguration & ProcessState Tests
# ===========================================================================


def test_process_configuration_from_dict():
    """ProcessConfiguration.from_dict parst alle Felder korrekt."""
    pc = _make_process_config(
        process_id="test_001",
        nodes=[{"subprocess_id": "A", "subprocess_type": "TypeA"}],
        subprocess_config={"A": {"param": "value"}},
    )

    assert pc.process_id == "test_001"
    assert pc.software_version == "1.0.0"
    assert pc.input_dataset_id == "ds_test"
    assert len(pc.dataflow.nodes) == 1
    assert pc.subprocess_config["A"]["param"] == "value"


def test_process_configuration_to_dict_roundtrip():
    """ProcessConfiguration.to_dict erzeugt ein Dict, aus dem from_dict neu erstellt werden kann."""
    pc = _make_process_config(
        process_id="test_roundtrip",
        nodes=[
            {"subprocess_id": "X", "subprocess_type": "TX"},
            {"subprocess_id": "Y", "subprocess_type": "TY"},
        ],
        edges=[{"from": "X", "to": "Y"}],
    )
    d = pc.to_dict()
    pc2 = ProcessConfiguration.from_dict(d)

    assert pc2.process_id == pc.process_id
    assert len(pc2.dataflow.nodes) == 2
    assert len(pc2.dataflow.edges) == 1


def test_process_state_to_dict():
    """ProcessState.to_dict enthält alle Felder."""
    ps = ProcessState(process_id="proc_xyz", status="running")
    d = ps.to_dict()

    assert d["process_id"] == "proc_xyz"
    assert d["status"] == "running"
    assert "dataflow_state" in d


# ===========================================================================
# Abschnitt 4: Plugin-Loader Tests
# ===========================================================================


def test_plugin_registration_and_retrieval():
    """Plugins können registriert und abgerufen werden."""

    class _DummySub(BaseSubprocess):
        def __init__(self):
            super().__init__("_DummyType_test")

        async def run(self, context, **kwargs):
            return []

    dummy = _DummySub()
    register_subprocess("_DummyType_test", dummy)

    result = get_subprocess("_DummyType_test")
    assert result is dummy


def test_get_subprocess_unknown_type():
    """Unbekannter Typ liefert None zurück."""
    assert get_subprocess("NonExistentType_xyz") is None


def test_load_builtin_plugins():
    """Eingebaute Plugins werden korrekt geladen."""
    load_builtin_plugins()

    fetch = get_subprocess("FetchFeedItems")
    embed = get_subprocess("EmbedData")

    assert fetch is not None
    assert embed is not None
    assert isinstance(fetch, FetchFeedItems)
    assert isinstance(embed, EmbedData)


# ===========================================================================
# Abschnitt 5: ProcessEngine Tests (mit Mock-Repositories)
# ===========================================================================


@pytest.mark.asyncio
async def test_process_engine_inserts_process_document(
    isolated_event_service, mock_repos
):
    """ProcessEngine speichert Prozess-Dokument beim Start."""
    process_repo, dataflow_state_repo, data_repo, dataset_repo = mock_repos
    config = _make_process_config(process_id="proc_insert_test")
    process_repo.find_by_id = AsyncMock(
        return_value=_make_mock_process_config_doc("proc_insert_test")
    )

    dummy_subprocess = AsyncMock()
    dummy_subprocess.run = AsyncMock(
        return_value=[
            IOTransformationState(
                input_data_id="d1",
                output_data_ids=["out1"],
                status=TransformationStatus.FINISHED,
            )
        ]
    )

    engine = ProcessEngine(
        event_service=isolated_event_service,
        process_repository=process_repo,
        dataflow_state_repository=dataflow_state_repo,
        data_repository=data_repo,
        dataset_repository=dataset_repo,
        get_subprocess=lambda t: dummy_subprocess,
    )
    engine.start()

    await engine.start_process(config)
    await asyncio.sleep(0.15)  # Tasks ablaufen lassen

    process_repo.insert.assert_called_once()
    inserted_doc = process_repo.insert.call_args[0][0]
    assert inserted_doc["process_id"] == "proc_insert_test"
    assert inserted_doc["status"] == "running"
    assert "dataflow_state" in inserted_doc


@pytest.mark.asyncio
async def test_process_engine_starts_root_subprocess(isolated_event_service, mock_repos):
    """ProcessEngine startet den Root-Subprozess und aktualisiert dessen Status."""
    process_repo, dataflow_state_repo, data_repo, dataset_repo = mock_repos
    config = _make_process_config(process_id="proc_root_test")
    process_repo.find_by_id = AsyncMock(
        return_value=_make_mock_process_config_doc("proc_root_test")
    )

    dummy_subprocess = AsyncMock()
    dummy_subprocess.run = AsyncMock(
        return_value=[
            IOTransformationState(
                input_data_id="d1",
                output_data_ids=["out1"],
                status=TransformationStatus.FINISHED,
            )
        ]
    )

    engine = ProcessEngine(
        event_service=isolated_event_service,
        process_repository=process_repo,
        dataflow_state_repository=dataflow_state_repo,
        data_repository=data_repo,
        dataset_repository=dataset_repo,
        get_subprocess=lambda t: dummy_subprocess,
    )
    engine.start()

    await engine.start_process(config)
    await asyncio.sleep(0.15)

    # Subprocess wurde aufgerufen
    dummy_subprocess.run.assert_called_once()

    # DataflowState wurde aktualisiert
    assert dataflow_state_repo.update_node_state.call_count >= 2  # STARTED + COMPLETED


@pytest.mark.asyncio
async def test_process_engine_subprocess_chaining(isolated_event_service):
    """Nach Abschluss von Subprozess A wird Subprozess B automatisch gestartet."""
    chain_config = ProcessConfiguration.from_dict(
        {
            "process_id": "proc_chain_test",
            "software_version": "1.0.0",
            "input_dataset_id": "ds_chain",
            "dataflow": {
                "nodes": [
                    {"subprocess_id": "Step1", "subprocess_type": "TypeA"},
                    {"subprocess_id": "Step2", "subprocess_type": "TypeB"},
                ],
                "edges": [{"from": "Step1", "to": "Step2"}],
            },
            "subprocess_config": {},
        }
    )

    process_repo = AsyncMock()
    process_repo.insert = AsyncMock(return_value="id")
    process_repo.update = AsyncMock(return_value=True)
    process_repo.find_by_id = AsyncMock(
        return_value={
            "process_id": "proc_chain_test",
            "configuration": chain_config.to_dict(),
        }
    )

    dataflow_state_repo = AsyncMock()
    dataflow_state_repo.update_node_state = AsyncMock(return_value=True)
    dataflow_state_repo.get_dataflow_state = AsyncMock(
        return_value={
            "nodes": [
                {
                    "subprocess_id": "Step1",
                    "subprocess_type": "TypeA",
                    "event_status": "EVENT_COMPLETED",
                    "io_transformation_states": [
                        {
                            "input_data_id": "d1",
                            "output_data_ids": ["out_step1"],
                            "status": "Finished",
                            "quality": 1.0,
                        }
                    ],
                },
                {
                    "subprocess_id": "Step2",
                    "subprocess_type": "TypeB",
                    "event_status": "EVENT_COMPLETED",
                    "io_transformation_states": [],
                },
            ],
            "edges": [{"from": "Step1", "to": "Step2"}],
        }
    )

    async def mock_find_data(data_id: str):
        return {"data_id": data_id, "content": {"text": data_id}, "type": "output"}

    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()
    data_repo.find_by_id = mock_find_data

    dataset_repo = AsyncMock()
    dataset_repo.find_by_id = AsyncMock(
        return_value={"dataset_id": "ds_chain", "data_ids": ["d1"]}
    )

    started: list[str] = []

    async def mock_run(context, **kwargs):
        started.append(context.subprocess_id)
        return [
            IOTransformationState(
                input_data_id=context.input_data[0].data_id
                if context.input_data
                else "none",
                output_data_ids=["out_" + context.subprocess_id],
                status=TransformationStatus.FINISHED,
            )
        ]

    dummy = AsyncMock()
    dummy.run = mock_run

    engine = ProcessEngine(
        event_service=isolated_event_service,
        process_repository=process_repo,
        dataflow_state_repository=dataflow_state_repo,
        data_repository=data_repo,
        dataset_repository=dataset_repo,
        get_subprocess=lambda t: dummy,
    )
    engine.start()

    await engine.start_process(chain_config)
    await asyncio.sleep(0.3)

    assert "Step1" in started, "Step1 wurde nicht ausgeführt"
    assert "Step2" in started, "Step2 wurde nach Step1 nicht gestartet"


@pytest.mark.asyncio
async def test_process_engine_marks_completed_when_all_done(
    isolated_event_service, mock_repos
):
    """Prozess wird als 'completed' markiert wenn alle Subprozesse fertig sind."""
    process_repo, dataflow_state_repo, data_repo, dataset_repo = mock_repos
    config = _make_process_config(process_id="proc_complete_test")
    process_repo.find_by_id = AsyncMock(
        return_value=_make_mock_process_config_doc("proc_complete_test")
    )

    dummy_subprocess = AsyncMock()
    dummy_subprocess.run = AsyncMock(
        return_value=[
            IOTransformationState(
                input_data_id="d1",
                output_data_ids=["out1"],
                status=TransformationStatus.FINISHED,
            )
        ]
    )

    engine = ProcessEngine(
        event_service=isolated_event_service,
        process_repository=process_repo,
        dataflow_state_repository=dataflow_state_repo,
        data_repository=data_repo,
        dataset_repository=dataset_repo,
        get_subprocess=lambda t: dummy_subprocess,
    )
    engine.start()

    await engine.start_process(config)
    await asyncio.sleep(0.2)

    # process_repo.update sollte mit status="completed" aufgerufen worden sein
    update_calls = process_repo.update.call_args_list
    completed_calls = [c for c in update_calls if c[0][1].get("status") == "completed"]
    assert len(completed_calls) >= 1


@pytest.mark.asyncio
async def test_process_engine_handles_missing_subprocess_type(
    isolated_event_service, mock_repos
):
    """Unbekannter Subprocess-Typ führt zu EVENT_FAILED, kein Absturz."""
    process_repo, dataflow_state_repo, data_repo, dataset_repo = mock_repos
    config = _make_process_config(process_id="proc_missing_type")
    process_repo.find_by_id = AsyncMock(
        return_value=_make_mock_process_config_doc("proc_missing_type")
    )

    engine = ProcessEngine(
        event_service=isolated_event_service,
        process_repository=process_repo,
        dataflow_state_repository=dataflow_state_repo,
        data_repository=data_repo,
        dataset_repository=dataset_repo,
        get_subprocess=lambda t: None,  # Kein Plugin registriert
    )
    engine.start()

    # Kein Exception soll propagieren
    await engine.start_process(config)
    await asyncio.sleep(0.15)

    # Node-Status wurde auf FAILED gesetzt
    update_calls = dataflow_state_repo.update_node_state.call_args_list
    assert any(
        "EVENT_FAILED" in str(call) for call in update_calls
    ), "Kein EVENT_FAILED für unbekannten Subprocess-Typ"


# ===========================================================================
# Abschnitt 6: FetchFeedItems Plugin Tests
# ===========================================================================


@pytest.mark.asyncio
async def test_fetch_feed_items_success_two_articles():
    """Ein RSS-Feed mit 2 Artikeln erzeugt 2 Output-Data-Einträge."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    context = _make_feed_context(
        [{"title": "Test Feed", "xmlUrl": "https://example.com/feed", "htmlUrl": "https://example.com"}]
    )
    plugin = FetchFeedItems()

    with patch(
        "dflowp.plugins.fetch_feed_items.fetch_feed_items.httpx.AsyncClient"
    ) as mock_client:
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_RSS_XML
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_resp
        )

        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 1
    assert results[0].status == TransformationStatus.FINISHED
    assert len(results[0].output_data_ids) == 2
    assert data_repo.insert.call_count == 2


@pytest.mark.asyncio
async def test_fetch_feed_items_source_included_in_output():
    """Output-Daten enthalten Quellinformationen des Feeds."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    context = _make_feed_context(
        [{"title": "My Source", "xmlUrl": "https://src.example.com/feed", "htmlUrl": "https://src.example.com"}]
    )
    plugin = FetchFeedItems()

    with patch(
        "dflowp.plugins.fetch_feed_items.fetch_feed_items.httpx.AsyncClient"
    ) as mock_client:
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_RSS_XML
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_resp
        )

        await plugin.run(context=context, data_repository=data_repo)

    inserted_content = data_repo.insert.call_args_list[0][0][0]["content"]
    assert "source" in inserted_content
    assert inserted_content["source"]["title"] == "My Source"
    assert inserted_content["source"]["xmlUrl"] == "https://src.example.com/feed"


@pytest.mark.asyncio
async def test_fetch_feed_items_output_has_article_fields():
    """Artikel enthalten title, link, summary und published."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    context = _make_feed_context(
        [{"title": "Feed", "xmlUrl": "https://example.com/feed"}]
    )
    plugin = FetchFeedItems()

    with patch(
        "dflowp.plugins.fetch_feed_items.fetch_feed_items.httpx.AsyncClient"
    ) as mock_client:
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_RSS_XML
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_resp
        )

        await plugin.run(context=context, data_repository=data_repo)

    article = data_repo.insert.call_args_list[0][0][0]["content"]
    assert "title" in article
    assert "link" in article
    assert article["title"] == "Article 1"
    assert "example.com/article-1" in article["link"]


@pytest.mark.asyncio
async def test_fetch_feed_items_no_xml_url():
    """Feed ohne xmlUrl wird als FAILED markiert, kein DB-Eintrag."""
    data_repo = AsyncMock()
    context = _make_feed_context([{"title": "Feed Without URL"}])
    plugin = FetchFeedItems()

    results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 1
    assert results[0].status == TransformationStatus.FAILED
    assert results[0].output_data_ids == []
    data_repo.insert.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_feed_items_http_error_continues_other_feeds():
    """HTTP-Fehler bei einem Feed stoppt nicht die Verarbeitung anderer Feeds."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    context = _make_feed_context(
        [
            {"title": "Bad Feed", "xmlUrl": "https://bad.example.com/feed"},
            {"title": "Good Feed", "xmlUrl": "https://good.example.com/feed"},
        ]
    )
    plugin = FetchFeedItems()

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if "bad" in url:
            import httpx
            raise httpx.ConnectError("Connection failed")
        resp = MagicMock()
        resp.text = SAMPLE_RSS_XML
        resp.raise_for_status = MagicMock()
        return resp

    with patch(
        "dflowp.plugins.fetch_feed_items.fetch_feed_items.httpx.AsyncClient"
    ) as mock_client:
        mock_client.return_value.__aenter__.return_value.get = mock_get

        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 2
    assert results[0].status == TransformationStatus.FAILED
    assert results[1].status == TransformationStatus.FINISHED
    assert len(results[1].output_data_ids) == 2


@pytest.mark.asyncio
async def test_fetch_feed_items_empty_feed():
    """Feed ohne Artikel: FINISHED mit 0 Output-IDs und quality=0.0."""
    data_repo = AsyncMock()
    empty_rss = (
        '<?xml version="1.0"?><rss version="2.0">'
        "<channel><title>Empty</title></channel></rss>"
    )
    context = _make_feed_context(
        [{"title": "Empty Feed", "xmlUrl": "https://empty.example.com/feed"}]
    )
    plugin = FetchFeedItems()

    with patch(
        "dflowp.plugins.fetch_feed_items.fetch_feed_items.httpx.AsyncClient"
    ) as mock_client:
        mock_resp = MagicMock()
        mock_resp.text = empty_rss
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_resp
        )

        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 1
    assert results[0].status == TransformationStatus.FINISHED
    assert results[0].output_data_ids == []
    assert results[0].quality == 0.0


@pytest.mark.asyncio
async def test_fetch_feed_items_multiple_feeds():
    """Mehrere Feeds werden alle verarbeitet und erzeugen separate IO-States."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    context = _make_feed_context(
        [
            {"title": "Feed A", "xmlUrl": "https://a.example.com/feed"},
            {"title": "Feed B", "xmlUrl": "https://b.example.com/feed"},
        ]
    )
    plugin = FetchFeedItems()

    with patch(
        "dflowp.plugins.fetch_feed_items.fetch_feed_items.httpx.AsyncClient"
    ) as mock_client:
        mock_resp = MagicMock()
        mock_resp.text = SAMPLE_RSS_XML
        mock_resp.raise_for_status = MagicMock()
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=mock_resp
        )

        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 2
    assert results[0].status == TransformationStatus.FINISHED
    assert results[1].status == TransformationStatus.FINISHED
    # 2 Feeds × 2 Artikel = 4 Inserts
    assert data_repo.insert.call_count == 4


@pytest.mark.asyncio
async def test_fetch_feed_items_requires_data_repository():
    """Fehlende data_repository löst ValueError aus."""
    context = _make_feed_context(
        [{"title": "Feed", "xmlUrl": "https://example.com/feed"}]
    )
    plugin = FetchFeedItems()

    with pytest.raises(ValueError, match="data_repository"):
        await plugin.run(context=context, data_repository=None)


# ===========================================================================
# Abschnitt 7: EmbedData Plugin Tests
# ===========================================================================


def _mock_openai_create(embedding: list[float] = None):
    """Erstellt eine Mock-Funktion für AsyncOpenAI.embeddings.create."""
    embedding = embedding or MOCK_EMBEDDING

    async def mock_create(input, model):
        resp = MagicMock()
        resp.data = [MagicMock(embedding=embedding)]
        return resp

    return mock_create


@pytest.mark.asyncio
async def test_embed_data_success():
    """Embedding wird korrekt erstellt und in DB gespeichert."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    context = _make_article_context(
        [{"title": "Test Article", "summary": "Summary text"}],
        config={"openai_api_key": "test-key"},
    )
    plugin = EmbedData()

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.embeddings.create = _mock_openai_create()
        mock_openai_cls.return_value = mock_client

        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 1
    assert results[0].status == TransformationStatus.FINISHED
    assert len(results[0].output_data_ids) == 1

    inserted = data_repo.insert.call_args_list[0][0][0]
    assert inserted["type"] == "output"
    assert "embedding" in inserted["content"]
    assert inserted["content"]["embedding"] == MOCK_EMBEDDING
    assert inserted["content"]["source_data_id"] == "article_0"


@pytest.mark.asyncio
async def test_embed_data_default_attributes_title_and_summary():
    """Ohne Konfiguration werden title und summary embedded."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    captured: list[str] = []

    async def mock_create(input, model):
        captured.append(input)
        resp = MagicMock()
        resp.data = [MagicMock(embedding=MOCK_EMBEDDING)]
        return resp

    context = _make_article_context(
        [{"title": "My Title", "summary": "My Summary", "link": "https://x.com"}],
        config={"openai_api_key": "test-key"},
    )
    plugin = EmbedData()

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        mock_openai_cls.return_value = mock_client

        await plugin.run(context=context, data_repository=data_repo)

    assert len(captured) == 1
    assert "My Title" in captured[0]
    assert "My Summary" in captured[0]
    assert "https://x.com" not in captured[0]  # link ist kein Default-Attribut


@pytest.mark.asyncio
async def test_embed_data_custom_attributes():
    """Konfigurierte Attribute werden ausschließlich verwendet."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    captured: list[str] = []

    async def mock_create(input, model):
        captured.append(input)
        resp = MagicMock()
        resp.data = [MagicMock(embedding=MOCK_EMBEDDING)]
        return resp

    context = _make_article_context(
        [{"title": "Title Only", "summary": "Ignored Summary"}],
        config={"openai_api_key": "test-key", "embedding_attributes": ["title"]},
    )
    plugin = EmbedData()

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        mock_openai_cls.return_value = mock_client

        await plugin.run(context=context, data_repository=data_repo)

    assert "Title Only" in captured[0]
    assert "Ignored Summary" not in captured[0]


@pytest.mark.asyncio
async def test_embed_data_custom_model():
    """Das konfigurierte Modell wird an die OpenAI API übergeben."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    used_models: list[str] = []

    async def mock_create(input, model):
        used_models.append(model)
        resp = MagicMock()
        resp.data = [MagicMock(embedding=MOCK_EMBEDDING)]
        return resp

    context = _make_article_context(
        [{"title": "Article"}],
        config={"openai_api_key": "test-key", "model": "text-embedding-3-large"},
    )
    plugin = EmbedData()

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        mock_openai_cls.return_value = mock_client

        await plugin.run(context=context, data_repository=data_repo)

    assert used_models[0] == "text-embedding-3-large"


@pytest.mark.asyncio
async def test_embed_data_empty_content_uses_placeholder():
    """Artikel ohne konfigurierte Attribute erhalten den Platzhalter '(leer)'."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    captured: list[str] = []

    async def mock_create(input, model):
        captured.append(input)
        resp = MagicMock()
        resp.data = [MagicMock(embedding=MOCK_EMBEDDING)]
        return resp

    context = _make_article_context(
        [{"other_field": "irrelevant"}],
        config={"openai_api_key": "test-key"},
    )
    plugin = EmbedData()

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        mock_openai_cls.return_value = mock_client

        results = await plugin.run(context=context, data_repository=data_repo)

    assert results[0].status == TransformationStatus.FINISHED
    assert "(leer)" in captured[0]


@pytest.mark.asyncio
async def test_embed_data_missing_api_key_marks_as_failed():
    """Fehlender API-Key markiert das Item als FAILED, kein Absturz."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    context = _make_article_context(
        [{"title": "Test", "summary": "Summary"}],
        config={},  # Kein openai_api_key
    )
    plugin = EmbedData()

    env_without_key = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
    with patch.dict(os.environ, env_without_key, clear=True):
        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 1
    assert results[0].status == TransformationStatus.FAILED
    assert results[0].output_data_ids == []
    data_repo.insert.assert_not_called()


@pytest.mark.asyncio
async def test_embed_data_api_error_continues_other_items():
    """API-Fehler bei einem Artikel stoppt nicht die Verarbeitung weiterer Artikel."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    call_count = 0

    async def mock_create(input, model):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("Simulated API error")
        resp = MagicMock()
        resp.data = [MagicMock(embedding=MOCK_EMBEDDING)]
        return resp

    context = _make_article_context(
        [
            {"title": "Bad Article", "summary": "Will fail"},
            {"title": "Good Article", "summary": "Will succeed"},
        ],
        config={"openai_api_key": "test-key"},
    )
    plugin = EmbedData()

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.embeddings.create = mock_create
        mock_openai_cls.return_value = mock_client

        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 2
    assert results[0].status == TransformationStatus.FAILED
    assert results[1].status == TransformationStatus.FINISHED


@pytest.mark.asyncio
async def test_embed_data_multiple_articles():
    """Mehrere Artikel erzeugen je einen Embedding-Eintrag."""
    data_repo = AsyncMock()
    data_repo.insert = AsyncMock()

    articles = [
        {"title": f"Article {i}", "summary": f"Summary {i}"} for i in range(5)
    ]
    context = _make_article_context(articles, config={"openai_api_key": "test-key"})
    plugin = EmbedData()

    with patch("openai.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_client.embeddings.create = _mock_openai_create()
        mock_openai_cls.return_value = mock_client

        results = await plugin.run(context=context, data_repository=data_repo)

    assert len(results) == 5
    assert all(r.status == TransformationStatus.FINISHED for r in results)
    assert data_repo.insert.call_count == 5


@pytest.mark.asyncio
async def test_embed_data_requires_data_repository():
    """Fehlende data_repository löst ValueError aus."""
    context = _make_article_context(
        [{"title": "Test"}],
        config={"openai_api_key": "test-key"},
    )
    plugin = EmbedData()

    with pytest.raises(ValueError, match="data_repository"):
        await plugin.run(context=context, data_repository=None)
