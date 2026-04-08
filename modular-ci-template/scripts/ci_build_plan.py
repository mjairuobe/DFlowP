#!/usr/bin/env python3
"""Schreibt .jenkins_skip_pipeline und .jenkins_build_plan.env."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ci_lib import all_paths, image_for_service, load_modules, path_to_env_key, repo_root


def docker_ps_images() -> list[str]:
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.Image}}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return []
    return [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]


def normalize_img(s: str) -> str:
    s = s.strip()
    for p in ("docker.io/", "registry-1.docker.io/"):
        if s.startswith(p):
            s = s[len(p) :]
    return s


def has_running(want: str, images: list[str]) -> bool:
    w = normalize_img(want)
    return any(normalize_img(i) == w for i in images)


def has_mongo(images: list[str]) -> bool:
    for i in images:
        n = normalize_img(i)
        if n.startswith("mongo:") or "mongo:" in n:
            return True
        if n.startswith("library/mongo:"):
            return True
    return False


def load_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def load_last_trees(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        k, v = line.split("=", 1)
        if k.startswith("LAST_TREE_"):
            out[k] = v.strip()
    return out


def tree_key_for_path(path: str) -> str:
    return path_to_env_key(path, "TREE")


def last_key_for_path(path: str) -> str:
    # z. B. LAST_TREE_EXAMPLE_PACKAGES_ALPHA_LIB
    return "LAST_" + path_to_env_key(path, "TREE")


def main() -> int:
    root = repo_root()
    os.chdir(root)
    modules = load_modules()
    pkgs, svcs = all_paths(modules)
    require_mongo = bool(modules.get("require_mongo", False))

    env_path = root / ".jenkins_runtime.env"
    env = load_env(env_path)
    if not env:
        (root / ".jenkins_skip_pipeline").write_text("false\n", encoding="utf-8")
        (root / ".jenkins_build_plan.env").write_text("LIB_FORCE=1\n", encoding="utf-8")
        print("ci_build_plan: keine .jenkins_runtime.env")
        return 0

    last_path = root / ".jenkins_last_trees"
    last = load_last_trees(last_path)

    lib_force = 0
    if not last:
        lib_force = 1
        print("LIB_FORCE=1 (kein .jenkins_last_trees)")
    else:
        for p in pkgs:
            tk = tree_key_for_path(p)
            lk = last_key_for_path(p)
            cur = env.get(tk, "")
            prev = last.get(lk, "")
            if cur != prev:
                lib_force = 1
                print(f"LIB_FORCE=1 (package {p}: {prev!r} -> {cur!r})")
                break

    images = docker_ps_images()
    all_current = 1
    if require_mongo and not has_mongo(images):
        all_current = 0
        print("Mongo fehlt (require_mongo=true)")

    for svc in svcs:
        repo = image_for_service(modules, svc)
        tk = tree_key_for_path(svc)
        tag = env.get(tk, "00000").lower()
        full = f"{repo}:{tag}"
        if not has_running(full, images):
            all_current = 0
            print(f"Nicht aktuell: {full}")

    skip = lib_force == 0 and all_current == 1
    (root / ".jenkins_skip_pipeline").write_text(("true" if skip else "false") + "\n", encoding="utf-8")

    lines = [f"LIB_FORCE={lib_force}"]
    for svc in svcs:
        key = path_to_env_key(svc, "BUILDSVC")
        if lib_force:
            lines.append(f"{key}=1")
        else:
            repo = image_for_service(modules, svc)
            tk = tree_key_for_path(svc)
            tag = env.get(tk, "00000").lower()
            need = 0 if has_running(f"{repo}:{tag}", images) else 1
            lines.append(f"{key}={need}")

    (root / ".jenkins_build_plan.env").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("=== .jenkins_build_plan.env ===")
    print((root / ".jenkins_build_plan.env").read_text(encoding="utf-8"))
    print("=== .jenkins_skip_pipeline ===")
    print((root / ".jenkins_skip_pipeline").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
