"""Remote plugin client worker for plugin microservices."""

from __future__ import annotations

import asyncio
import os
import re
import socket
from typing import Any, Optional

import httpx

from dflowp_processruntime.subprocesses.io_transformation_state import (
    IOTransformationState,
)
from dflowp_processruntime.subprocesses.subprocess import BasePluginWorker
from dflowp_processruntime.subprocesses.subprocess_context import PluginWorkerContext
from dflowp_core.utils.logger import get_logger

logger = get_logger(__name__)


def _slugify_plugin_type(plugin_type: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", plugin_type.lower()).strip("-")
    return slug or "plugin"


def _service_env_suffix(plugin_type: str) -> str:
    return _slugify_plugin_type(plugin_type).replace("-", "_").upper()


def build_remote_plugin_worker(plugin_type: str) -> "RemotePluginWorker":
    return RemotePluginWorker(plugin_type=plugin_type)


class RemotePluginWorker(BasePluginWorker):
    """Forwards plugin-worker execution to a remote plugin service over HTTP."""

    def __init__(self, plugin_type: str, base_url: Optional[str] = None) -> None:
        super().__init__(plugin_type)
        self._base_url = base_url.rstrip("/") if base_url else None

    async def run(
        self,
        context: PluginWorkerContext,
        event_emitter: Optional[Any] = None,
        state_updater: Optional[Any] = None,
        data_repository: Optional[Any] = None,
        dataset_repository: Optional[Any] = None,
    ) -> list[IOTransformationState]:
        retries = int(
            context.config.get(
                "plugin_retry_attempts",
                os.environ.get("DFLOWP_PLUGIN_REMOTE_RETRIES", "15"),
            )
        )
        delay_seconds = float(
            context.config.get(
                "plugin_retry_delay_seconds",
                os.environ.get("DFLOWP_PLUGIN_REMOTE_RETRY_DELAY_SECONDS", "25"),
            )
        )
        request_timeout = float(
            context.config.get(
                "plugin_request_timeout_seconds",
                os.environ.get("DFLOWP_PLUGIN_REMOTE_HTTP_TIMEOUT", "600"),
            )
        )

        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                service_url = await self._resolve_service_url(context)
                async with httpx.AsyncClient(timeout=request_timeout) as client:
                    response = await client.post(
                        f"{service_url}/plugin/run",
                        json={"context": context.model_dump(mode="json")},
                    )
                    response.raise_for_status()
                    payload = response.json()
                raw_states = payload.get("io_transformation_states", [])
                return [IOTransformationState.from_dict(item) for item in raw_states]
            except Exception as exc:
                last_error = exc
                if attempt < retries:
                    logger.warning(
                        "Remote plugin call fehlgeschlagen (%s, attempt %d/%d): %s",
                        self.plugin_type,
                        attempt,
                        retries,
                        exc,
                    )
                    await asyncio.sleep(delay_seconds)

        raise RuntimeError(
            f"Remote plugin call für {self.plugin_type} fehlgeschlagen: {last_error}"
        )

    async def _assert_dns_resolvable(
        self, host: str, port: int | None = None
    ) -> None:
        """Prüft, ob der Hostname per DNS auflösbar ist (vor dem HTTP-Call)."""
        try:
            loop = asyncio.get_running_loop()
            await loop.getaddrinfo(
                host, port if port is not None else 0, type=socket.SOCK_STREAM
            )
        except OSError as exc:
            raise RuntimeError(
                f"Plugin-Host '{host}' ist per DNS nicht auflösbar: {exc}"
            ) from exc

    async def _resolve_service_url(self, context: PluginWorkerContext) -> str:
        if self._base_url:
            host = _host_from_url(self._base_url)
            if "plugin" not in host:
                raise ValueError(
                    f"Ungültiger plugin_service_url Host '{host}': muss 'plugin' enthalten"
                )
            await self._assert_dns_resolvable(host)
            return self._base_url

        override_url = context.config.get("plugin_service_url")
        if override_url:
            service_url = str(override_url).rstrip("/")
            host = _host_from_url(service_url)
            if "plugin" not in host:
                raise ValueError(
                    f"Ungültiger plugin_service_url Host '{host}': muss 'plugin' enthalten"
                )
            await self._assert_dns_resolvable(host)
            return service_url

        env_suffix = _service_env_suffix(self.plugin_type)
        default_name = f"plugin-{_slugify_plugin_type(self.plugin_type)}"
        service_name = str(
            context.config.get(
                "plugin_service_name",
                os.environ.get(f"DFLOWP_PLUGIN_SERVICE_{env_suffix}", default_name),
            )
        )
        if "plugin" not in service_name:
            raise ValueError(
                f"Ungültiger plugin_service_name '{service_name}': muss 'plugin' enthalten"
            )
        service_port = int(
            context.config.get(
                "plugin_service_port",
                os.environ.get(
                    f"DFLOWP_PLUGIN_PORT_{env_suffix}",
                    os.environ.get("DFLOWP_PLUGIN_DEFAULT_PORT", "8010"),
                ),
            )
        )
        await self._assert_dns_resolvable(service_name, service_port)
        return f"http://{service_name}:{service_port}"


def _host_from_url(url: str) -> str:
    without_scheme = url.split("://", 1)[-1]
    host_port = without_scheme.split("/", 1)[0]
    return host_port.split(":", 1)[0]

