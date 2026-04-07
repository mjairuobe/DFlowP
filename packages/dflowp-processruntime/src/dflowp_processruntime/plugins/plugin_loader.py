"""Lädt Subprozess-Plugins zur Laufzeit."""

from typing import Any, Optional

from dflowp_processruntime.subprocesses.subprocess import BaseSubprocess


_REGISTRY: dict[str, BaseSubprocess] = {}


def register_subprocess(subprocess_type: str, instance: BaseSubprocess) -> None:
    """Registriert einen Subprozess-Typ."""
    _REGISTRY[subprocess_type] = instance


def get_subprocess(subprocess_type: str) -> Optional[BaseSubprocess]:
    """Gibt eine Instanz des Subprozesses zurück."""
    return _REGISTRY.get(subprocess_type)


def load_builtin_plugins() -> None:
    """Lädt die eingebauten Plugins (FetchFeedItems, EmbedData)."""
    from dflowp_processruntime.plugins.fetch_feed_items.fetch_feed_items import FetchFeedItems
    from dflowp_processruntime.plugins.embedding.embed_data import EmbedData

    register_subprocess("FetchFeedItems", FetchFeedItems())
    register_subprocess("EmbedData", EmbedData())
