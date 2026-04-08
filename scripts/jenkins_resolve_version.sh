#!/usr/bin/env bash
# Jenkins: SOFTWARE_VERSION und Docker-Tag aus Git, ohne Docker Hub.
#
# Formel: MAJOR.<Branch-Anzahl>.<erste 4 Hex-Zeichen des Short-SHA als Dezimalzahl>
# MAJOR wird aus packages/.../software_version.py (MAJOR_VERSION) gelesen.
#
# Schreibt .jenkins_runtime.env mit SOFTWARE_VERSION und IMAGE_TAG (gleicher Wert).

set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "${ROOT}"

SHORT_SHA="$(git rev-parse --short HEAD)"
# Erste 4 Hex-Zeichen des Short-SHA (Git liefert typ. 7+ Zeichen, nur [0-9a-f])
HEX4="${SHORT_SHA:0:4}"
DECIMAL="$((16#${HEX4}))"

BRANCH_COUNT="$(git for-each-ref refs/heads refs/remotes | wc -l | tr -d ' ')"

SV_FILE="packages/dflowp-processruntime/src/dflowp_processruntime/processes/software_version.py"
MAJOR="$(grep -E '^MAJOR_VERSION[[:space:]]*=' "${SV_FILE}" | head -1 | sed -E 's/.*=[[:space:]]*([0-9]+).*/\1/')"
MAJOR="${MAJOR:-0}"

SOFTWARE_VERSION="${MAJOR}.${BRANCH_COUNT}.${DECIMAL}"
IMAGE_TAG="${SOFTWARE_VERSION}"

echo "Git short SHA: ${SHORT_SHA} → HEX4=${HEX4} → decimal=${DECIMAL}"
echo "Branch refs (heads+remotes): ${BRANCH_COUNT}"
echo "Resolved SOFTWARE_VERSION=${SOFTWARE_VERSION} (IMAGE_TAG=${IMAGE_TAG})"

{
  printf 'SOFTWARE_VERSION=%s\n' "${SOFTWARE_VERSION}"
  printf 'IMAGE_TAG=%s\n' "${IMAGE_TAG}"
} > .jenkins_runtime.env
