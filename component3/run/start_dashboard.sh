#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
COMPONENT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
REPOSITORY_ROOT="$(cd -- "${COMPONENT_ROOT}/.." && pwd -P)"
PYTHON="${COMPONENT_ROOT}/.venv/bin/python"
DASHBOARD_MODULE="component3.simulations.navigation_dashboard.dashboard"
DASHBOARD_FILE="${COMPONENT_ROOT}/simulations/navigation_dashboard/dashboard.py"
PORT="${COMP3_DASHBOARD_PORT:-8765}"

usage() {
  printf '%s\n' "Usage: $0 [--port PORT]" "" \
    "Environment: COMP3_DASHBOARD_PORT overrides the default port 8765."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -p|--port)
      if [ "$#" -lt 2 ]; then
        printf 'ERROR: %s requires a value.\n' "$1" >&2
        usage >&2
        exit 2
      fi
      PORT="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$PORT" in
  ''|*[!0-9]*)
    printf 'ERROR: port must be an integer from 1 to 65535; received %s.\n' "$PORT" >&2
    exit 2
    ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  printf 'ERROR: port must be between 1 and 65535; received %s.\n' "$PORT" >&2
  exit 2
fi

if [ ! -x "$PYTHON" ]; then
  printf 'ERROR: project Python is unavailable or not executable: %s\n' "$PYTHON" >&2
  printf 'This launcher never installs packages or modifies global Python.\n' >&2
  exit 1
fi
if [ ! -f "$DASHBOARD_FILE" ]; then
  printf 'ERROR: dashboard entry point is missing: %s\n' "$DASHBOARD_FILE" >&2
  exit 1
fi

cd -- "$REPOSITORY_ROOT"

if ! "$PYTHON" -B -c \
  "import cv2, numpy; import ${DASHBOARD_MODULE}" >/dev/null 2>&1; then
  printf 'ERROR: the existing project environment cannot import the dashboard, OpenCV, and NumPy.\n' >&2
  printf 'Run %s/check_dashboard.sh for details.\n' "$SCRIPT_DIR" >&2
  exit 1
fi

set +e
PORT_PROBE="$("$PYTHON" -B - "$PORT" <<'PY'
import json
import socket
import sys
import urllib.error
import urllib.request

port = int(sys.argv[1])
try:
    connection = socket.create_connection(("127.0.0.1", port), timeout=0.5)
except OSError:
    print("free")
    raise SystemExit(0)
else:
    connection.close()

try:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/api/session/state", timeout=1.5
    ) as response:
        payload = json.load(response)
    if (
        response.status == 200
        and isinstance(payload, dict)
        and str(payload.get("session_id", "")).startswith("nav-")
        and payload.get("map_id") == "comp3-synthetic-supermarket-demo-v1"
    ):
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

BASE_URL="http://127.0.0.1:${PORT}"
if [ "$PROBE_STATUS" -eq 10 ]; then
  printf 'Component 3 dashboard is already running on port %s; no duplicate was started.\n' "$PORT"
  printf 'Customer View:           %s/customer\n' "$BASE_URL"
  printf 'Research Execution View: %s/\n' "$BASE_URL"
  printf 'Historical Research Map: %s/research\n' "$BASE_URL"
  exit 0
fi
if [ "$PROBE_STATUS" -ne 0 ]; then
  printf 'ERROR: port %s is occupied, but it is not a healthy Component 3 dashboard.\n' "$PORT" >&2
  printf 'Choose another port with --port PORT or COMP3_DASHBOARD_PORT.\n' >&2
  exit 1
fi

printf 'Starting Component 3 dashboard with %s\n' "$PYTHON"
printf 'Customer View:           %s/customer\n' "$BASE_URL"
printf 'Research Execution View: %s/\n' "$BASE_URL"
printf 'Historical Research Map: %s/research\n' "$BASE_URL"
printf 'Press Ctrl+C once to stop the server and release any open camera.\n\n'

# Replacing this shell with Python gives the dashboard Ctrl+C directly. Its existing
# try/finally block stops CameraScanner and closes the HTTP server on normal shutdown.
exec "$PYTHON" -B -m "$DASHBOARD_MODULE" --host 127.0.0.1 --port "$PORT"
