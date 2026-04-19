#!/usr/bin/env bash
# Generiert docker/uibakery.env mit zufälligen Secrets.
# Nutzung:
#   export UI_BAKERY_LICENSE_KEY="…"   # On-Premise-Key (Jenkins: aus Secret)
#   export UI_BAKERY_APP_SERVER_NAME="https://dflowp.ddns.net/App"  # optional
#   ./docker/generate_uibakery_env.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/docker/uibakery.env"
RAND() { LC_ALL=C tr -cd 'A-Za-z0-9' < /dev/urandom | head -c "$1" | tr -d '\n'; }

: "${UI_BAKERY_VERSION:=latest}"
: "${UI_BAKERY_PORT:=8010}"
# Öffentliche URL im Browser (Reverse-Proxy, inkl. Base-Path /App)
: "${UI_BAKERY_APP_SERVER_NAME:=https://dflowp.ddns.net/App}"

if [[ -z "${UI_BAKERY_LICENSE_KEY:-}" ]]; then
  echo "Fehlend: UI_BAKERY_LICENSE_KEY" >&2
  exit 1
fi

# Jenkins (oder andere Stores) können den Secret-Wert als JSON liefern, z. B.
# {"UI_BAKERY_LICENSE_KEY":"<jwt>"}. In docker/uibakery.env soll nur der Token stehen.
_extract_license_plain() {
  UI_BAKERY_LICENSE_KEY="$UI_BAKERY_LICENSE_KEY" python3 <<'PY'
import json
import os
import sys

raw = os.environ["UI_BAKERY_LICENSE_KEY"].strip()
if not raw.startswith("{"):
    print(raw)
    sys.exit(0)
try:
    obj = json.loads(raw)
except json.JSONDecodeError:
    print(raw, end="")
    sys.exit(0)
if isinstance(obj, dict):
    val = obj.get("UI_BAKERY_LICENSE_KEY")
    if isinstance(val, str) and val.strip():
        print(val.strip())
        sys.exit(0)
print(raw, end="")
PY
}

UI_BAKERY_LICENSE_KEY="$(_extract_license_plain)"

if [[ -z "${UI_BAKERY_LICENSE_KEY}" ]]; then
  echo "Fehlend oder leer nach Auflösung: UI_BAKERY_LICENSE_KEY (JSON ohne gültigen Wert?)" >&2
  exit 1
fi

{
  echo "UI_BAKERY_VERSION=${UI_BAKERY_VERSION}"
  echo "UI_BAKERY_APP_SERVER_NAME=${UI_BAKERY_APP_SERVER_NAME}"
  echo "UI_BAKERY_PORT=${UI_BAKERY_PORT}"
  echo "UI_BAKERY_LICENSE_KEY=${UI_BAKERY_LICENSE_KEY}"
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
