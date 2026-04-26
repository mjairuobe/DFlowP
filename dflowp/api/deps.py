"""FastAPI-Dependencies für Repositories."""

from dflowp_core.database.dataflow_repository import DataflowRepository
from dflowp_core.database.dataflow_state_repository import DataflowStateRepository
from dflowp_core.database.data_item_repository import DataItemRepository
from dflowp_core.database.event_repository import EventRepository
from dflowp_core.database.plugin_configuration_repository import PluginConfigurationRepository
from dflowp_core.database.process_repository import ProcessRepository


def get_process_repository() -> ProcessRepository:
    return ProcessRepository()


def get_data_item_repository() -> DataItemRepository:
    return DataItemRepository()


def get_event_repository() -> EventRepository:
    return EventRepository()


def get_dataflow_repository() -> DataflowRepository:
    return DataflowRepository()


def get_dataflow_state_repository() -> DataflowStateRepository:
    return DataflowStateRepository()


def get_plugin_configuration_repository() -> PluginConfigurationRepository:
    return PluginConfigurationRepository()
