#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
COMPONENT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
REPOSITORY_ROOT="$(cd -- "${COMPONENT_ROOT}/.." && pwd -P)"
PORT="${COMP3_NAVIGATION_DEMO_PORT:-8765}"

if [ "$#" -ne 0 ]; then
  printf 'Usage: %s\nThis launcher always binds to 127.0.0.1. Set COMP3_NAVIGATION_DEMO_PORT to change only the port.\n' "$0" >&2
  exit 2
fi
case "$PORT" in ''|*[!0-9]*) printf 'ERROR: invalid port: %s\n' "$PORT" >&2; exit 2;; esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then printf 'ERROR: port must be 1-65535.\n' >&2; exit 2; fi

if [ -x "${COMPONENT_ROOT}/.venv/bin/python" ]; then
  PYTHON="${COMPONENT_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="$(command -v python3)"
else
  printf 'ERROR: no existing .venv Python or python3 was found; nothing will be installed.\n' >&2
  exit 1
fi

export COMP3_RECO_MIN_ITEMS=3
export COMP3_RECO_DEBOUNCE_SECONDS=0.35
URL="http://127.0.0.1:${PORT}/"
cd -- "$REPOSITORY_ROOT"

set +e
PROBE_STATUS="$(
"$PYTHON" - "$PORT" <<'PY'
import json, socket, sys, urllib.error, urllib.request
port = int(sys.argv[1])
try:
    connection = socket.create_connection(("127.0.0.1", port), timeout=0.5)
except OSError:
    print("free")
    raise SystemExit(0)
else:
    connection.close()

try:
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/session/state", timeout=1.5) as response:
        payload = json.load(response)
    if response.status == 200 and isinstance(payload, dict) and payload.get("map_id") == "comp3-synthetic-supermarket-demo-v1":
        print("component3_dashboard")
        raise SystemExit(10)
except (OSError, ValueError, urllib.error.URLError):
    pass
print("occupied_unknown")
raise SystemExit(11)
PY
)"
PROBE_STATUS=$?
set -e

if [ "$PROBE_STATUS" -eq 10 ]; then
  printf 'Component 3 Navigation demo is already running on port %s; no duplicate was started.\n' "$PORT"
  printf 'Customer View:  http://127.0.0.1:%s/customer\n' "$PORT"
  printf 'Operator View:  http://127.0.0.1:%s/\n' "$PORT"
  if command -v open >/dev/null 2>&1; then (sleep 0.2; open "$URL") &
  elif command -v xdg-open >/dev/null 2>&1; then (sleep 0.2; xdg-open "$URL") &
  fi
  exit 0
fi

if [ "$PROBE_STATUS" -ne 0 ]; then
  printf 'ERROR: port %s is occupied by another process; cannot start Navigation demo.\n' "$PORT" >&2
  printf 'Set COMP3_NAVIGATION_DEMO_PORT to select another port, or terminate the existing process.\n' >&2
  exit 1
fi

printf 'Navigation demo: %s\nRecommendation gate: %s distinct items\n' "$URL" "$COMP3_RECO_MIN_ITEMS"
if command -v open >/dev/null 2>&1; then (sleep 0.8; open "$URL") &
elif command -v xdg-open >/dev/null 2>&1; then (sleep 0.8; xdg-open "$URL") &
else printf 'Open this URL in a browser: %s\n' "$URL"; fi
exec "$PYTHON" -B -m component3.simulations.navigation_dashboard.dashboard --mode navigation --host 127.0.0.1 --port "$PORT"
