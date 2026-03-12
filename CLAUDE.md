# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DFlowP** is a Python framework for data-flow-oriented programming (Datenflussorientierte Programmierung). It enables building resilient, data-intensive applications with:

- **Event-driven architecture**: All state transitions emit events for observability and reproducibility
- **Checkpoint-based recovery**: Data flows are monitored and checkpointed, allowing resumption from failure points
- **Migratable pipelines**: Processes can be cloned with new configurations for testing, A/B testing, or recovery with different parameters
- **Modular plugins**: Extensible subprocess types for data transformation (embedding, web scraping, etc.)

Core use cases: RAG pipelines, data ETL, web scraping with automatic retry, AI workflow management.

## Setup & Common Commands

### Installation

```bash
# Development setup with test dependencies
pip install -e ".[dev]"
```

### Running the Application

```bash
# Prerequisites: MongoDB running on localhost:27017, OPENAI_API_KEY environment variable set
python main.py
```

The main entry point loads process configuration from `examples/processconfig_example.json` and input data from `examples/inputdata_set.json`, then executes the pipeline.

### Running Tests

```bash
# All tests
pytest tests/ -v

# Single test file
pytest tests/process_test.py -v

# With coverage
pytest tests/ --cov=dflowp --cov-report=term-missing

# Specific test (requires MongoDB running)
pytest tests/database_test.py::TestProcessRepository -v
```

**Database tests require MongoDB** running on `localhost:27017`. Configure via `MONGODB_URI` environment variable if needed.

### Database Management

```bash
# View MongoDB collections (requires mongosh or mongo shell)
mongosh dflowp

# List process documents
db.processes.find()

# View all events for a process
db.events.find({process_id: "your_process_id"})

# Data migration (e.g., updating embedded text format)
db.datasets.updateMany({}, [{ $set: {...} }])
```

## Architecture

### High-Level Design

```
Runtime
├── ProcessEngine (coordinates all processes)
│   ├── Subscribes to EventBus for lifecycle events
│   ├── Creates subprocess contexts from DataFlow + Config
│   └── Manages process state transitions
├── EventBus / EventService (publish-subscribe)
│   └── Persists all events to MongoDB for auditability
└── Repositories (data persistence)
    ├── ProcessRepository
    ├── DataRepository (actual data content)
    ├── DatasetRepository (collections of Data references)
    └── EventRepository

Process Execution Flow:
1. ProcessConfiguration (defines what to run) → ProcessEngine
2. Engine creates ProcessState, DataflowState, and subprocess contexts
3. Engine starts initial subprocesses based on DataFlow
4. Each subprocess emits EVENT_STARTED → EventBus
5. Subprocess processes data, updates io_transformation_state
6. On completion: EVENT_COMPLETED → EventBus (triggers dependent subprocesses)
7. Engine updates ProcessState as all subprocesses complete
```

### Core Components

**`dflowp/core/processes/`**
- `process.py`: Abstract base for runnable processes with event emission
- `process_configuration.py`: Defines what will be executed (process_id, subprocess_config, dataflow)
- `process_state.py`: Tracks runtime state (status, created_at, dataflow_state)

**`dflowp/core/subprocesses/`**
- `subprocess.py`: Abstract base for data transformations (auto-emits STARTED/COMPLETED/FAILED events)
- `subprocess_context.py`: Provides subprocess with input data, config, and process context
- `io_transformation_state.py`: Tracks input→output transformation and quality metrics

**`dflowp/core/dataflow/`**
- `dataflow.py`: Tree structure describing subprocess execution order (can be sequential, parallel, conditional)
- `dataflow_node.py`: A single node in the tree (subprocess_id, subprocess_type, status)
- `dataflow_state.py`: Runtime state for entire dataflow (maps all node states)
- `dataflow_parser.py`: Parses JSON-based dataflow definitions

**`dflowp/core/datastructures/`**
- `data.py`: Single data item with ID for database referencing
- `dataset.py`: Collection of Data items (typically input or output of a subprocess)

**`dflowp/core/events/`**
- `event_types.py`: EVENT_STARTED, EVENT_COMPLETED, EVENT_FAILED, EVENT_PROGRESS (future)
- `event_service.py`: Pub/sub interface (emit, subscribe by process_id or subprocess_id)
- `event_bus.py`: Persistent event storage and broadcasting

**`dflowp/infrastructure/`**
- Repositories for MongoDB access (process, data, dataset, event)
- MongoDB schema is auto-initialized via Pydantic models

### Plugin System

Plugins extend the framework with subprocess types. Located in `dflowp/plugins/`:

```
plugins/
├── embedding/
│   └── embedder.py (EmbedData subprocess type)
├── fetch_feed_items/
│   └── fetch_feed_items.py (FetchFeedItems subprocess type)
└── [your_plugin_here]/
    └── your_plugin.py
```

**Creating a Plugin:**
1. Inherit from `subprocess.SubProcess`
2. Implement `async def run(context: SubprocessContext) -> Dataset`
3. Emit events via `context.event_service.emit()`
4. Return output Dataset with transformed data
5. Register in plugin_loader.py if using dynamic loading

**Key Pattern:** Subprocesses are stateless; all data flow through DataSets and Events. Configuration comes via `subprocess_config` dict in ProcessConfiguration.

## Key Design Patterns

### Event-Driven State Management

- Every state transition (subprocess start/complete/fail) emits an event to EventBus
- Events are persisted for auditability and recovery
- ProcessEngine subscribes to events to trigger dependent subprocesses
- Never modify ProcessState directly; use events as the single source of truth

### Async/Await Throughout

- All I/O (database, API calls) is async via `motor` (MongoDB driver) and `httpx`
- Subprocesses run concurrently if they have no data dependencies
- Use `async def` and `await` in all subprocess implementations

### Configuration-Driven Execution

- Processes are defined entirely by JSON (ProcessConfiguration + DataFlow)
- Same code can execute different workflows without code changes
- ProcessConfiguration includes per-subprocess config dict (API keys, model names, thresholds, etc.)
- Config can be dynamically updated per process instance (e.g., different LLM per clone)

### Repository Pattern

- All database access goes through repositories (ProcessRepository, DataRepository, etc.)
- Repositories abstract MongoDB details from business logic
- Use repositories in ProcessEngine and subprocesses, not direct MongoDB calls

## Common Workflows

### Running a Process Manually

Edit `examples/processconfig_example.json` to define your DataFlow and subprocess configurations, then `python main.py`.

### Debugging a Process

1. Check event history: `db.events.find({process_id: "X"}).sort({event_time: -1})`
2. Inspect process state: `db.processes.findOne({process_id: "X"})`
3. View subprocess output data: `db.datasets.findOne({_id: ObjectId(...)})`
4. Check io_transformation_state for quality metrics: `db.processes.findOne().dataflow_state.nodes[...].io_transformation_state`

### Adding a Database Schema Migration

1. Update the relevant Pydantic model in `dflowp/core/` or `dflowp/infrastructure/`
2. Write a MongoDB update script in main.py or tests/conftest.py
3. Test migration on a copy of production data
4. Document in TODOS.md before committing

### Cloning a Process with New Config

(Feature in development per TODOS.md) When complete, clone will:
1. Create a new ProcessConfiguration pointing to a new DataFlow
2. Copy the old DataflowState as a starting point
3. Only re-execute modified subprocess nodes
4. Reuse existing data/datasets (no duplication)

## Notes for Future Development

**See TODOS.md for in-progress items:**
- Process cloning with partial re-execution
- Dataflow/ProcessConfiguration/DataflowState database storage and referencing
- EVENT_PROGRESS and EVENT_LOG event types for granular monitoring
- API routes for starting processes and querying status (api/routes/)

**Testing:** All core logic has pytest tests. Database tests require MongoDB. Use `conftest.py` for shared fixtures.

**Logging:** Use `dflowp.utils.logger.get_logger(__name__)` for consistent log output with context.

**Error Handling:** Exceptions in subprocess.run() automatically trigger EVENT_FAILED. ProcessEngine handles retry logic (TBD in design).
