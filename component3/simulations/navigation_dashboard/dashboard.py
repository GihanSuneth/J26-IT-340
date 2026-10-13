"""Serve the offline navigation dashboard and local route-planning API."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
from typing import Any

from .adapter import (
    DashboardDataError,
    DashboardRouteError,
    RoutePlan,
    calculate_dashboard_route,
    load_dashboard_data,
)
from .config import DEFAULT_HOST, DEFAULT_PORT, STATIC_ROOT


LOGGER = logging.getLogger("component3.navigation_dashboard")
MAX_REQUEST_BYTES = 64 * 1024
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
}


def _json_route(plan: RoutePlan) -> dict[str, Any]:
    """Convert a validated route plan to the small browser API response."""
    return {
        "selected_destination_ids": list(plan.selected_destination_ids),
        "optimized_visit_order": list(plan.optimized_visit_order),
        "route_node_ids": list(plan.route_node_ids),
        "total_distance_m": plan.total_distance_m,
        "leg_paths": [
            {
                "node_ids": list(leg.node_ids),
                "distance_m": leg.total_distance_m,
            }
            for leg in plan.leg_paths
        ],
    }


def make_handler() -> type[BaseHTTPRequestHandler]:
    """Create an HTTP handler bound to validated map data for this server."""
    map_data = load_dashboard_data()

    class DashboardHandler(BaseHTTPRequestHandler):
        """Serve only bundled assets and local map/route JSON endpoints."""

        server_version = "Component3NavigationDashboard/1.0"

        def do_GET(self) -> None:
            """Return dashboard assets or actual store-map metadata."""
            if self.path == "/api/map":
                self._send_json(200, map_data)
                return
            asset = STATIC_FILES.get(self.path)
            if asset is None:
                self._send_json(404, {"error": "Not found"})
                return
            filename, content_type = asset
            try:
                body = (STATIC_ROOT / filename).read_bytes()
            except OSError as exc:
                LOGGER.exception("Dashboard asset could not be read: %s", filename)
                self._send_json(500, {"error": f"Dashboard asset unavailable: {exc}"})
                return
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            """Validate selected graph destinations and calculate their route."""
            if self.path != "/api/route":
                self._send_json(404, {"error": "Not found"})
                return
            raw_length = self.headers.get("Content-Length")
            try:
                length = int(raw_length or "")
            except ValueError:
                self._send_json(400, {"error": "A valid Content-Length is required"})
                return
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._send_json(413, {"error": "Request body is too large"})
                return
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                self._send_json(400, {"error": f"Invalid JSON request: {exc}"})
                return
            if (
                not isinstance(payload, dict)
                or not isinstance(payload.get("selected_destination_ids"), list)
            ):
                self._send_json(
                    400,
                    {"error": "selected_destination_ids must be a JSON array"},
                )
                return
            try:
                plan = calculate_dashboard_route(
                    map_data, payload["selected_destination_ids"]
                )
            except DashboardRouteError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            except DashboardDataError as exc:
                LOGGER.exception("Map data failed during route calculation")
                self._send_json(500, {"error": f"Map data unavailable: {exc}"})
                return
            self._send_json(200, _json_route(plan))

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            """Serialize one JSON response with local-only content headers."""
            body = json.dumps(payload, allow_nan=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format_string: str, *args: object) -> None:
            """Route standard request logs through the component logger."""
            LOGGER.info("%s - %s", self.address_string(), format_string % args)

    return DashboardHandler


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Start the local-only dashboard server."""
    handler = make_handler()
    server = ThreadingHTTPServer((host, port), handler)
    LOGGER.info("Serving dashboard at http://%s:%d", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Dashboard stopped")
    finally:
        server.server_close()


def main() -> None:
    """Parse local launch arguments and start the dashboard."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    arguments = parser.parse_args()
    if arguments.host not in {"127.0.0.1", "localhost"}:
        parser.error("The offline dashboard may only bind to localhost")
    if not 1 <= arguments.port <= 65535:
        parser.error("port must be between 1 and 65535")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    serve(arguments.host, arguments.port)


if __name__ == "__main__":
    main()
