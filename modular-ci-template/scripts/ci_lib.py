"""Hilfen für modules.json und Pfade."""

from __future__ import annotations

import json
import re
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def load_modules() -> dict:
    p = repo_root() / "modules.json"
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def all_paths(modules: dict) -> tuple[list[str], list[str]]:
    d = modules.get("dir", {})
    return list(d.get("packages", [])), list(d.get("services", []))


def path_to_env_key(path: str, prefix: str) -> str:
    """z. B. example-services/http-api -> TREE_example_services_http_api"""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", path).strip("_").upper()
    return f"{prefix}_{slug}"


def image_for_service(modules: dict, service_path: str) -> str:
    reg = modules.get("docker", {}).get("registry", "docker.io/example-org").rstrip("/")
    names = modules.get("docker", {}).get("images", {})
    short = names.get(service_path)
    if not short:
        short = Path(service_path).name
    return f"{reg}/{short}"


def container_for_service(modules: dict, service_path: str) -> str:
    c = modules.get("docker", {}).get("containers", {})
    return c.get(service_path, Path(service_path).name.replace("/", "-"))
