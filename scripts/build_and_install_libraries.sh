#!/usr/bin/env bash
set -euo pipefail

python3 -m pip install --upgrade pip setuptools wheel build

rm -rf packages/dflowp-core/dist packages/dflowp-processruntime/dist
python3 -m build packages/dflowp-core
python3 -m build packages/dflowp-processruntime

python3 -m pip install --force-reinstall \
  packages/dflowp-core/dist/dflowp_core-*.whl \
  packages/dflowp-processruntime/dist/dflowp_processruntime-*.whl
