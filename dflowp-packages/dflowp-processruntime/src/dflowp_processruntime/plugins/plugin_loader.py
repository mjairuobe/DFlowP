"""Lädt Subprozess-Plugins zur Laufzeit (Registry + Remote-HTTP-Clients)."""

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


def load_remote_plugin_services() -> None:
    """
    Registriert Remote-Plugin-Implementierungen über HTTP (Docker-DNS o.ä.).

    Umgebungsvariable DFLOWP_PLUGIN_ENDPOINTS:
      FetchFeedItems=...,EmbedData=...,Clustering_DBSCAN=...

    Jeder Eintrag ist ``SubprocessType=base_url``. Der Hostname in der URL muss
    ``plugin`` enthalten (Sicherheitsregel im Remote-Client).
    """
    endpoints_raw = os.environ.get(
        "DFLOWP_PLUGIN_ENDPOINTS",
        "FetchFeedItems=http://plugin-fetchfeeditems:8101,"
        "EmbedData=http://plugin-embeddata:8102,"
        "Clustering_DBSCAN=http://plugin-clustering-dbscan:8103,"
        "Clustering_HDBSCAN=http://plugin-clustering-hdbscan:8104",
    )
    for entry in [x.strip() for x in endpoints_raw.split(",") if x.strip()]:
        if "=" not in entry:
            continue
        subprocess_type, base_url = [x.strip() for x in entry.split("=", 1)]
        if not subprocess_type or not base_url:
            continue
        host_part = base_url.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0]
        if "plugin" not in host_part:
            continue
        register_subprocess(
            subprocess_type,
            RemotePluginSubprocess(
                subprocess_type=subprocess_type,
                base_url=base_url,
            ),
        )


def clear_registry() -> None:
    """Leert die Registry (v. a. für Tests)."""
    _REGISTRY.clear()
