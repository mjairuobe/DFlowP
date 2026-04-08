#!/usr/bin/env bash
set -euo pipefail

python3.11 -m ensurepip --upgrade
python3.11 -m pip install --upgrade pip setuptools wheel build

rm -rf packages/dflowp-core/dist packages/dflowp-processruntime/dist dist
python3.11 -m build packages/dflowp-core
python3.11 -m build packages/dflowp-processruntime
python3.11 -m build .

python3.11 -m pip install --force-reinstall \
  packages/dflowp-core/dist/dflowp_core-*.whl
python3.11 -m pip install --force-reinstall --no-deps \
  packages/dflowp-processruntime/dist/dflowp_processruntime-*.whl
# Metapaket „dflowp“ (Repo-Root): liefert dflowp.* inkl. Plugin-Code; zieht u. a. feedparser/openai.
python3.11 -m pip install --force-reinstall \
  dist/dflowp-*.whl
