#!/usr/bin/env bash
set -euo pipefail

python3.11 -m ensurepip --upgrade
python3.11 -m pip install --upgrade pip setuptools wheel build

rm -rf dflowp-packages/dflowp-core/dist dflowp-packages/dflowp-processruntime/dist
python3.11 -m build dflowp-packages/dflowp-core
python3.11 -m build dflowp-packages/dflowp-processruntime

python3.11 -m pip install --force-reinstall \
  dflowp-packages/dflowp-core/dist/dflowp_core-*.whl
python3.11 -m pip install --force-reinstall --no-deps \
  dflowp-packages/dflowp-processruntime/dist/dflowp_processruntime-*.whl
