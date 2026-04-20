#!/usr/bin/env python3
"""Liest ENV[name]; wenn JSON { name: \"…\" }, nur den inneren String ausgeben (Jenkins/AWS Secret-Wrappen)."""
import json
import os
import sys

def main() -> None:
    if len(sys.argv) != 2:
        print("usage: plain_env_maybe_json.py ENV_VAR_NAME", file=sys.stderr)
        sys.exit(2)
    name = sys.argv[1]
    raw = os.environ.get(name, "").strip()
    if not raw:
        sys.exit(0)
    if not raw.startswith("{"):
        print(raw)
        return
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        print(raw)
        return
    if isinstance(obj, dict):
        val = obj.get(name)
        if isinstance(val, str) and val.strip():
            print(val.strip())
            return
    print(raw)


if __name__ == "__main__":
    main()
