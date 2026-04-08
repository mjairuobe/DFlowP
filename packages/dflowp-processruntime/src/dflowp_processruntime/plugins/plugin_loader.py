"""Lädt Subprozess-Plugins zur Laufzeit."""

import os
from typing import Optional

from dflowp_processruntime.subprocesses.subprocess import BaseSubprocess
from dflowp_processruntime.plugins.remote_plugin import RemotePluginSubprocess


_REGISTRY: dict[str, BaseSubprocess] = {}


def register_subprocess(subprocess_type: str, instance: BaseSubprocess) -> None:
    """Registriert einen Subprozess-Typ."""
    _REGISTRY[subprocess_type] = instance


def get_subprocess(subprocess_type: str) -> Optional[BaseSubprocess]:
    """Gibt eine Instanz des Subprozesses zurück."""
    return _REGISTRY.get(subprocess_type)


def load_builtin_plugins() -> None:
    """Lädt lokale Fallback-Plugins (FetchFeedItems, EmbedData)."""
    from dflowp_processruntime.plugins.fetch_feed_items.fetch_feed_items import FetchFeedItems
    from dflowp_processruntime.plugins.embedding.embed_data import EmbedData

    register_subprocess("FetchFeedItems", FetchFeedItems())
    register_subprocess("EmbedData", EmbedData())


def load_remote_plugin_services() -> None:
    """
    Registriert Remote-Plugin-Implementierungen über Docker-DNS.

    Hinweis: Docker Embedded DNS bietet kein Wildcard-/Listing-API.
    Deshalb wird eine konfigurierbare Kandidatenliste geprüft.
    """
    endpoints_raw = os.environ.get(
        "DFLOWP_PLUGIN_ENDPOINTS",
        "plugin-fetchfeeditems=http://plugin-fetchfeeditems:8101,"
        "plugin-embeddata=http://plugin-embeddata:8102",
    )
    plugin_map = {
        "plugin-fetchfeeditems": "FetchFeedItems",
        "plugin-embeddata": "EmbedData",
    }
    remote_enabled: set[str] = set()
    for entry in [x.strip() for x in endpoints_raw.split(",") if x.strip()]:
        if "=" not in entry:
            continue
        key, base_url = [x.strip() for x in entry.split("=", 1)]
        if "plugin" not in key:
            continue
        subprocess_type = plugin_map.get(key)
        if not subprocess_type:
            continue
        register_subprocess(
            subprocess_type,
            RemotePluginSubprocess(
                subprocess_type=subprocess_type,
                base_url=base_url,
            ),
        )
        remote_enabled.add(subprocess_type)

    for enabled in sorted(remote_enabled):
        print(f"[PluginLoader] Remote plugin aktiv: {enabled}")
