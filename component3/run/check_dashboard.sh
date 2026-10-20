#!/usr/bin/env bash

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
COMPONENT_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
REPOSITORY_ROOT="$(cd -- "${COMPONENT_ROOT}/.." && pwd -P)"
PYTHON="${COMPONENT_ROOT}/.venv/bin/python"
DASHBOARD_FILE="${COMPONENT_ROOT}/simulations/navigation_dashboard/dashboard.py"
PORT="${COMP3_DASHBOARD_PORT:-8765}"
FAILURES=0

usage() {
  printf '%s\n' "Usage: $0 [--port PORT]" "" \
    "This command checks the existing environment and listener; it never starts a server."
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    -p|--port)
      if [ "$#" -lt 2 ]; then
        printf 'FAIL  port: %s requires a value.\n' "$1" >&2
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
      printf 'FAIL  argument: unknown argument %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "$PORT" in
  ''|*[!0-9]*)
    printf 'FAIL  port: expected integer 1-65535, received %s\n' "$PORT" >&2
    exit 2
    ;;
esac
if [ "$PORT" -lt 1 ] || [ "$PORT" -gt 65535 ]; then
  printf 'FAIL  port: expected 1-65535, received %s\n' "$PORT" >&2
  exit 2
fi

printf 'Component 3 dashboard preflight\n'
printf 'Repository: %s\n' "$REPOSITORY_ROOT"
printf 'Port:       %s\n\n' "$PORT"

if [ -x "$PYTHON" ]; then
  printf 'PASS  virtual environment: %s\n' "$PYTHON"
else
  printf 'FAIL  virtual environment: missing executable %s\n' "$PYTHON"
  FAILURES=$((FAILURES + 1))
fi

if [ -f "$DASHBOARD_FILE" ]; then
  printf 'PASS  dashboard entry point: %s\n' "$DASHBOARD_FILE"
else
  printf 'FAIL  dashboard entry point: missing %s\n' "$DASHBOARD_FILE"
  FAILURES=$((FAILURES + 1))
fi

if [ -x "$PYTHON" ]; then
  PYTHON_VERSION="$("$PYTHON" -B -c 'import platform; print(platform.python_version())' 2>&1)"
  VERSION_STATUS=$?
  if [ "$VERSION_STATUS" -eq 0 ]; then
    printf 'PASS  Python version: %s\n' "$PYTHON_VERSION"
  else
    printf 'FAIL  Python version: %s\n' "$PYTHON_VERSION"
    FAILURES=$((FAILURES + 1))
  fi

  IMPORT_REPORT="$(cd -- "$REPOSITORY_ROOT" && "$PYTHON" -B - <<'PY' 2>&1
import cv2
import numpy
from component3.backend.comp3_reco_navigation.navigation.camera_scanner import CameraScanner
from component3.simulations.navigation_dashboard import dashboard

print(f"dashboard=ok; cv2={cv2.__version__}; numpy={numpy.__version__}; scanner={CameraScanner.__name__}")
PY
)"
  IMPORT_STATUS=$?
  if [ "$IMPORT_STATUS" -eq 0 ]; then
    printf 'PASS  required imports: %s\n' "$IMPORT_REPORT"
  else
    printf 'FAIL  required imports: %s\n' "$IMPORT_REPORT"
    FAILURES=$((FAILURES + 1))
  fi

  PORT_REPORT="$("$PYTHON" -B - "$PORT" <<'PY' 2>&1
import json
import socket
import sys
import urllib.error
import urllib.request

port = int(sys.argv[1])
try:
    connection = socket.create_connection(("127.0.0.1", port), timeout=0.5)
except OSError:
    print("FREE|No process is accepting loopback connections; HTTP readiness NOT RUN.")
    raise SystemExit(0)
else:
    connection.close()

try:
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/api/session/state", timeout=1.5
    ) as response:
        payload = json.load(response)
    healthy = (
        response.status == 200
        and isinstance(payload, dict)
        and str(payload.get("session_id", "")).startswith("nav-")
        and payload.get("map_id") == "comp3-synthetic-supermarket-demo-v1"
        and "camera_status" in payload
    )
    if healthy:
        print(f"DASHBOARD|HTTP 200 ready; session={payload['session_id']}; camera state present")
        raise SystemExit(0)
except (OSError, ValueError, urllib.error.URLError) as error:
    print(f"UNKNOWN|Listener did not provide healthy dashboard state: {error}")
    raise SystemExit(1)
print("UNKNOWN|Listener returned an unexpected dashboard payload.")
raise SystemExit(1)
PY
)"
  PORT_STATUS=$?
  PORT_KIND="${PORT_REPORT%%|*}"
  PORT_DETAIL="${PORT_REPORT#*|}"
  if [ "$PORT_STATUS" -eq 0 ] && [ "$PORT_KIND" = "FREE" ]; then
    printf 'PASS  port availability: port %s is free\n' "$PORT"
    printf 'INFO  HTTP readiness: %s\n' "$PORT_DETAIL"
  elif [ "$PORT_STATUS" -eq 0 ] && [ "$PORT_KIND" = "DASHBOARD" ]; then
    printf 'PASS  port ownership: existing Component 3 dashboard\n'
    printf 'PASS  HTTP readiness: %s\n' "$PORT_DETAIL"
  else
    printf 'FAIL  port/readiness: %s\n' "$PORT_DETAIL"
    FAILURES=$((FAILURES + 1))
  fi
else
  printf 'SKIP  Python version, imports, port and HTTP checks: project interpreter unavailable\n'
fi

printf '\n'
if [ "$FAILURES" -eq 0 ]; then
  printf 'Overall: PASS (%s failure(s)); no server was started.\n' "$FAILURES"
  exit 0
fi
printf 'Overall: FAIL (%s failure(s)); no server was started.\n' "$FAILURES" >&2
exit 1
