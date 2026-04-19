#!/usr/bin/env bash
# Generiert docker/uibakery.env mit zufälligen Secrets.
# Nutzung:
#   export UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET="…"   # On-Premise-Lizenz (lokal / Jenkins-injiziert)
#   export UI_BAKERY_APP_SERVER_NAME="https://dflowp.ddns.net/App"  # optional
#   ./docker/generate_uibakery_env.sh
#
# Jenkins: weiterhin credentialsId UI_BAKERY_LICENSE_KEY → variable UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/docker/uibakery.env"
RAND() { LC_ALL=C tr -cd 'A-Za-z0-9' < /dev/urandom | head -c "$1" | tr -d '\n'; }

: "${UI_BAKERY_VERSION:=latest}"
: "${UI_BAKERY_PORT:=8010}"
# Öffentliche URL im Browser (Reverse-Proxy, inkl. Base-Path /App)
: "${UI_BAKERY_APP_SERVER_NAME:=https://dflowp.ddns.net/App}"

LICENSE_RAW="${UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET:-}"
if [[ -z "${LICENSE_RAW}" ]]; then
  echo "Fehlend: UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET" >&2
  exit 1
fi

# Stores können den Wert als JSON liefern – nur den JWT/String in die .env schreiben.
_extract_license_plain() {
  LICENSE_RAW="$LICENSE_RAW" python3 <<'PY'
import json
import os
import sys

raw = os.environ["LICENSE_RAW"].strip()
if not raw.startswith("{"):
    print(raw)
    sys.exit(0)
try:
    obj = json.loads(raw)
except json.JSONDecodeError:
    print(raw, end="")
    sys.exit(0)
if isinstance(obj, dict):
    for key in ("UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET", "UI_BAKERY_LICENSE_KEY"):
        val = obj.get(key)
        if isinstance(val, str) and val.strip():
            print(val.strip())
            sys.exit(0)
print(raw, end="")
PY
}

UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET="$(_extract_license_plain)"

if [[ -z "${UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET}" ]]; then
  echo "Fehlend oder leer nach Auflösung: UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET (JSON ohne gültigen Wert?)" >&2
  exit 1
fi

{
  echo "UI_BAKERY_VERSION=${UI_BAKERY_VERSION}"
  echo "UI_BAKERY_APP_SERVER_NAME=${UI_BAKERY_APP_SERVER_NAME}"
  echo "UI_BAKERY_PORT=${UI_BAKERY_PORT}"
  echo "UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET=${UI_BAKERY_ON_PREMISE_LICENSE_KEY_SECRET}"
  echo "UI_BAKERY_JWT_SECRET=$(RAND 42)"
  echo "UI_BAKERY_JWT_SERVICE_ACCOUNT_SECRET=$(RAND 55)"
  echo "UI_BAKERY_JWT_REFRESH_SECRET=$(RAND 42)"
  echo "UI_BAKERY_CREDENTIALS_SECRET=$(RAND 32)"
  echo "UI_BAKERY_PROJECT_PRIVATE_KEY_SECRET=$(RAND 32)"
  echo "UI_BAKERY_AUTH_DEVICE_INFO_SECRET=$(RAND 32)"
  echo "UI_BAKERY_MFA_SECRET=$(RAND 32)"
  echo "UI_BAKERY_INTERNAL_API_URL=http://bakery-back:8080"
} > "$OUT"
chmod 600 "$OUT" 2>/dev/null || true
echo "Geschrieben: $OUT"
