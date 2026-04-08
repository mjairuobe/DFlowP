#!/usr/bin/env python3
"""Exportiert DOCKER_IMAGE_* für docker-compose (DFlowP)."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ci_lib import (
    image_for_service,
    load_modules,
    path_to_env_key,
    repo_root,
)


def load_env_file(path: Path) -> dict[str, str]:
    d: dict[str, str] = {}
    if not path.is_file():
        return d
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        d[k.strip()] = v.strip()
    return d


def tag_from_container(name: str, fallback: str) -> str:
    try:
        r = subprocess.run(
            ["docker", "inspect", "-f", "{{.Config.Image}}", name],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return fallback
    img = (r.stdout or "").strip()
    if not img:
        return fallback
    return img.split(":", 1)[-1]


def main() -> int:
    root = repo_root()
    modules = load_modules()
    compose_map = modules.get("compose", {})
    env_names = modules.get("compose_env", {})
    rt = load_env_file(root / ".jenkins_runtime.env")
    plan = load_env_file(root / ".jenkins_build_plan.env")
    sv = rt.get("SOFTWARE_VERSION", "v0.0.0")

    out: dict[str, str] = {"SOFTWARE_VERSION": sv}

    for compose_key, module_path in compose_map.items():
        var = env_names.get(compose_key)
        if not var:
            continue
        repo = image_for_service(modules, module_path)
        tk = path_to_env_key(module_path, "TREE")
        exp = rt.get(tk, "00000").lower()
        builds_key = path_to_env_key(module_path, "BUILDSVC")
        # Fallback: Jenkinsfile nutzt BUILD_* (ohne BUILDSVC_)
        flag_map = modules.get("docker", {}).get("build_plan_flags", {})
        legacy = flag_map.get(module_path)
        cname = modules["docker"]["containers"][module_path]

        if plan.get(builds_key) == "1" or (legacy and plan.get(legacy) == "1"):
            tag = exp
        else:
            tag = tag_from_container(cname, exp)
        out[var] = f"{repo}:{tag}"

    for k, v in sorted(out.items()):
        print(f"export {k}={shlex.quote(v)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
