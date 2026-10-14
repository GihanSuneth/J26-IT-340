"""Serve the offline navigation dashboard and local route-planning API."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
from pathlib import Path
import threading
from typing import Any
from urllib.parse import urlparse

from .adapter import (
    DashboardDataError,
    DashboardRouteError,
    RoutePlan,
    calculate_dashboard_route,
    load_dashboard_data,
)
from .config import DEFAULT_HOST, DEFAULT_PORT, STATIC_ROOT
from .engine import NavigationSimulation
from .spatial_simulation import SpatialNavigationSimulation


LOGGER = logging.getLogger("component3.navigation_dashboard")
MAX_REQUEST_BYTES = 64 * 1024
STATIC_FILES = {
    "/": ("spatial.html", "text/html; charset=utf-8"),
    "/research": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/spatial.js": ("spatial.js", "text/javascript; charset=utf-8"),
    "/spatial.css": ("spatial.css", "text/css; charset=utf-8"),
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


def make_handler(
    simulation: NavigationSimulation | None = None,
    spatial_simulation: SpatialNavigationSimulation | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Create an HTTP handler bound to validated map data for this server."""
    map_data = load_dashboard_data()
    simulator = simulation or NavigationSimulation()
    spatial_simulator = spatial_simulation or SpatialNavigationSimulation()
    spatial_map_data = spatial_simulator.data
    simulation_lock = threading.RLock()

    class DashboardHandler(BaseHTTPRequestHandler):
        """Serve only bundled assets and local map, route, and simulation APIs."""

        server_version = "Component3NavigationDashboard/1.0"

        def do_GET(self) -> None:
            """Return dashboard assets or actual store-map metadata."""
            parsed_path = urlparse(self.path)
            if parsed_path.path == "/api/spatial/map":
                self._send_json(200, spatial_map_data)
                return
            if parsed_path.path == "/api/spatial/state":
                with simulation_lock:
                    self._send_json(200, spatial_simulator.snapshot())
                return
            if parsed_path.path == "/api/spatial/export.json":
                with simulation_lock:
                    body = json.dumps(
                        spatial_simulator.snapshot(), allow_nan=False, indent=2
                    ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="synthetic_store_navigation_log.json"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed_path.path == "/api/map":
                self._send_json(200, map_data)
                return
            if parsed_path.path == "/api/simulation":
                with simulation_lock:
                    self._send_json(200, simulator.snapshot())
                return
            if parsed_path.path == "/api/simulation/export.csv":
                with simulation_lock:
                    body = simulator.export_csv().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="component3_navigation_simulation.csv"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            if parsed_path.path == "/api/simulation/export.json":
                with simulation_lock:
                    body = json.dumps(
                        simulator.snapshot(), allow_nan=False, indent=2
                    ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="component3_navigation_simulation.json"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            asset = STATIC_FILES.get(parsed_path.path)
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
            """Validate local route and simulation control requests."""
            parsed_path = urlparse(self.path)
            if parsed_path.path == "/api/spatial/control":
                payload = self._read_json_payload()
                if payload is None:
                    return
                action = payload.get("action")
                try:
                    with simulation_lock:
                        if action == "start":
                            result = spatial_simulator.start()
                        elif action == "guided_demo":
                            result = spatial_simulator.start_guided_demo()
                        elif action == "pause":
                            result = spatial_simulator.pause()
                        elif action == "resume":
                            result = spatial_simulator.resume()
                        elif action == "step":
                            result = spatial_simulator.step(payload.get("count", 1))
                        elif action == "reset":
                            result = spatial_simulator.reset()
                        elif action == "wrong_turn":
                            result = spatial_simulator.wrong_turn()
                        elif action == "confirm_product":
                            result = spatial_simulator.confirm_product()
                        elif action == "observe_checkpoint":
                            result = spatial_simulator.observe_checkpoint(
                                payload.get("observation")
                            )
                        elif action == "configure":
                            result = spatial_simulator.configure_speed(
                                payload.get("speed_m_s")
                            )
                        elif action == "set_products":
                            result = spatial_simulator.set_products(
                                payload.get("product_ids", [])
                            )
                        else:
                            self._send_json(
                                400,
                                {"error": f"Unknown spatial simulation action: {action!r}"},
                            )
                            return
                except (TypeError, ValueError, KeyError) as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(200, result)
                return
            if parsed_path.path == "/api/simulation/control":
                payload = self._read_json_payload()
                if payload is None:
                    return
                action = payload.get("action")
                try:
                    with simulation_lock:
                        if action == "start":
                            result = simulator.start()
                        elif action == "pause":
                            result = simulator.pause()
                        elif action == "resume":
                            result = simulator.resume()
                        elif action == "step":
                            result = simulator.step(payload.get("count", 1))
                        elif action == "reset":
                            result = simulator.reset()
                        elif action == "wrong_turn":
                            result = simulator.trigger_wrong_turn()
                        elif action == "confirm_stop":
                            result = simulator.confirm_current_stop()
                        elif action == "guided_demo":
                            result = simulator.guided_start()
                        elif action == "configure":
                            result = simulator.configure(
                                speed_m_s=payload.get("speed_m_s"),
                                encoder_noise_std_m=payload.get(
                                    "encoder_noise_std_m"
                                ),
                                imu_yaw_noise_std_rad=payload.get(
                                    "imu_yaw_noise_std_rad"
                                ),
                            )
                        elif action == "set_destinations":
                            result = simulator.set_destinations(
                                payload.get("destinations", [])
                            )
                        else:
                            self._send_json(
                                400,
                                {"error": f"Unknown simulation action: {action!r}"},
                            )
                            return
                except (TypeError, ValueError, KeyError) as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(200, result)
                return
            if parsed_path.path != "/api/route":
                self._send_json(404, {"error": "Not found"})
                return
            payload = self._read_json_payload()
            if payload is None:
                return
            if not isinstance(payload, dict) or not isinstance(
                payload.get("selected_destination_ids"), list
            ):
                self._send_json(
                    400, {"error": "selected_destination_ids must be a JSON array"}
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

        def _read_json_payload(self) -> dict[str, Any] | None:
            """Read and validate a bounded object JSON request body."""
            raw_length = self.headers.get("Content-Length")
            try:
                length = int(raw_length or "")
            except ValueError:
                self._send_json(400, {"error": "A valid Content-Length is required"})
                return None
            if length < 0 or length > MAX_REQUEST_BYTES:
                self._send_json(413, {"error": "Request body is too large"})
                return None
            try:
                payload = json.loads(self.rfile.read(length))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                self._send_json(400, {"error": f"Invalid JSON request: {exc}"})
                return None
            if not isinstance(payload, dict):
                self._send_json(400, {"error": "Request body must be a JSON object"})
                return None
            return payload

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
