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
from .shared_session import SharedNavigationSession, SessionConflictError
from .shopping_session import ShoppingRevisionConflictError
from .spatial_simulation import SpatialNavigationSimulation
from component3.backend.comp3_reco_navigation.navigation.camera_scanner import (
    CameraScanner,
    enumerate_camera_devices,
)


LOGGER = logging.getLogger("component3.navigation_dashboard")
MAX_REQUEST_BYTES = 64 * 1024
STATIC_FILES = {
    "/": ("spatial.html", "text/html; charset=utf-8"),
    "/customer": ("customer.html", "text/html; charset=utf-8"),
    "/research": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/app.css": ("app.css", "text/css; charset=utf-8"),
    "/spatial.js": ("spatial.js", "text/javascript; charset=utf-8"),
    "/spatial.css": ("spatial.css", "text/css; charset=utf-8"),
    "/customer.js": ("customer.js", "text/javascript; charset=utf-8"),
    "/customer.css": ("customer.css", "text/css; charset=utf-8"),
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
    shared_session = SharedNavigationSession(spatial_simulator)
    spatial_map_data = dict(spatial_simulator.data)
    spatial_map_data["apriltag_layouts"] = [
        spatial_simulator.dense_apriltag_layout
    ] if spatial_simulator.dense_apriltag_layout else []
    spatial_map_data["active_apriltag_layout_id"] = (
        (spatial_simulator.dense_apriltag_layout or {}).get("layout_id")
    )
    simulation_lock = threading.RLock()
    camera_control_lock = threading.Lock()
    camera_inventory: dict[str, Any] = {"devices": [], "attempts": []}
    autoplay_shutdown = threading.Event()
    autoplay_thread: threading.Thread | None = None

    def ensure_autoplay_thread() -> None:
        nonlocal autoplay_thread
        if autoplay_thread is not None and autoplay_thread.is_alive():
            return
        autoplay_thread = threading.Thread(
            target=autoplay_loop, name="component3-autoplay", daemon=True
        )
        autoplay_thread.start()

    def submit_camera_observation(tag_id: int, timestamp_s: float) -> dict[str, Any]:
        with simulation_lock:
            result = spatial_simulator.observe_camera_detection(tag_id, timestamp_s)
            shared_session.external_mutation()
            return shared_session.snapshot(result)

    def camera_disconnected() -> None:
        with simulation_lock:
            spatial_simulator.camera_stopped()
            shared_session.external_mutation()

    camera_scanner = CameraScanner(
        callback=submit_camera_observation,
        disconnect_callback=camera_disconnected,
    )

    def dispatch_spatial_action(
        action: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """Map validated session commands to the existing simulation methods."""
        if action == "start":
            return spatial_simulator.start()
        if action == "autoplay_start":
            if spatial_simulator.status == "ready":
                result = spatial_simulator.start()
            elif spatial_simulator.status == "paused":
                result = spatial_simulator.resume()
            elif spatial_simulator.status == "navigating":
                result = spatial_simulator.snapshot()
            else:
                raise ValueError("Autoplay can start only when ready, paused, or navigating")
            shared_session.set_autoplay(True, payload.get("rate"))
            ensure_autoplay_thread()
            return result
        if action == "camera_evaluation":
            result = spatial_simulator.start_camera_evaluation()
            shared_session.set_autoplay(True, payload.get("rate", 1.0))
            ensure_autoplay_thread()
            return result
        if action == "guided_demo":
            result = spatial_simulator.start_guided_demo()
            shared_session.set_autoplay(True, payload.get("rate", 1.0))
            ensure_autoplay_thread()
            return result
        if action == "pause":
            shared_session.set_autoplay(False)
            return spatial_simulator.pause()
        if action == "autoplay_pause":
            shared_session.set_autoplay(False)
            return spatial_simulator.pause()
        if action == "resume":
            return spatial_simulator.resume()
        if action == "autoplay_resume":
            result = spatial_simulator.resume()
            shared_session.set_autoplay(True, payload.get("rate"))
            ensure_autoplay_thread()
            return result
        if action == "autoplay_stop":
            shared_session.set_autoplay(False)
            return spatial_simulator.pause() if spatial_simulator.status == "navigating" else spatial_simulator.snapshot()
        if action == "autoplay_rate":
            shared_session.set_autoplay(shared_session.autoplay_enabled, payload.get("rate"))
            return spatial_simulator.snapshot()
        if action == "step":
            return spatial_simulator.step(payload.get("count", 1))
        if action == "reset":
            shared_session.set_autoplay(False)
            return spatial_simulator.reset()
        if action == "wrong_turn":
            return spatial_simulator.wrong_turn()
        if action == "confirm_product":
            return spatial_simulator.confirm_product(
                expected_shopping_revision=payload.get("expected_shopping_revision"),
                quantity=payload.get("quantity", 1),
            )
        if action == "skip_product":
            return spatial_simulator.skip_product(
                payload.get("decision"), payload.get("expected_shopping_revision")
            )
        if action == "observe_checkpoint":
            return spatial_simulator.observe_checkpoint(payload.get("observation"))
        if action == "acknowledge_localization_warning":
            return spatial_simulator.acknowledge_localization_warning(
                payload.get("warning_key"), camera_scanner.snapshot()
            )
        if action == "configure":
            return spatial_simulator.configure_speed(payload.get("speed_m_s"))
        if action == "set_products":
            return spatial_simulator.set_products(payload.get("product_ids", []))
        shopping_actions = {
            "shopping_add": "add",
            "shopping_remove": "remove",
            "shopping_increase": "increase",
            "shopping_decrease": "decrease_remaining",
        }
        if action in shopping_actions:
            return spatial_simulator.mutate_shopping_list(
                shopping_actions[action],
                payload.get("product_id"),
                payload.get("quantity", 1),
                payload.get("expected_shopping_revision"),
            )
        if action == "accept_recommendation":
            return spatial_simulator.accept_recommendation(
                payload.get("recommendation_id"),
                payload.get("expected_shopping_revision"),
            )
        if action == "reject_recommendation":
            return spatial_simulator.reject_recommendation(
                payload.get("recommendation_id"),
                payload.get("expected_shopping_revision"),
            )
        if action == "enter_free_walk":
            return spatial_simulator.enter_free_walk()
        if action == "choose_free_walk_edge":
            return spatial_simulator.choose_free_walk_edge(payload.get("target_node_id"))
        if action == "free_walk_stop":
            return spatial_simulator.stop_free_walk()
        if action == "free_walk_resume":
            return spatial_simulator.resume_free_walk()
        if action == "request_navigation":
            return spatial_simulator.request_navigation_from_current_location()
        raise ValueError(f"Unknown spatial simulation action: {action!r}")

    def autoplay_loop() -> None:
        """Own the one playback timer for all connected browser views."""
        while not autoplay_shutdown.wait(0.02):
            with simulation_lock:
                shared_session.autoplay_tick()

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
                    self._send_json(
                        200,
                        shared_session.snapshot(
                            camera_status=camera_scanner.snapshot()
                        ),
                    )
                return
            if parsed_path.path == "/api/session/state":
                with simulation_lock:
                    self._send_json(
                        200,
                        shared_session.snapshot(
                            camera_status=camera_scanner.snapshot()
                        ),
                    )
                return
            if parsed_path.path == "/api/camera/state":
                self._send_json(200, camera_scanner.snapshot())
                return
            if parsed_path.path == "/api/camera/preview.jpg":
                frame, sequence = camera_scanner.preview()
                if frame is None:
                    self.send_response(204)
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Content-Length", str(len(frame)))
                self.send_header("X-Preview-Sequence", str(sequence))
                self.send_header("Cache-Control", "no-store, max-age=0")
                self.end_headers()
                self.wfile.write(frame)
                return
            if parsed_path.path == "/api/camera/export.json":
                body = json.dumps(
                    camera_scanner.snapshot(), allow_nan=False, indent=2
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header(
                    "Content-Disposition",
                    'attachment; filename="component3_camera_scan_log.json"',
                )
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
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
            if parsed_path.path == "/api/camera/control":
                payload = self._read_json_payload()
                if payload is None:
                    return
                try:
                    action = payload.get("action")
                    with camera_control_lock:
                        if action in {"probe", "refresh"}:
                            if camera_scanner.snapshot()["scanning"]:
                                stopped = camera_scanner.stop()
                                if stopped["scanning"]:
                                    self._send_json(409, {"error": "The active camera is still stopping. Retry Refresh Cameras."})
                                    return
                                with simulation_lock:
                                    spatial_simulator.camera_stopped()
                                    shared_session.external_mutation()
                            inventory = enumerate_camera_devices(
                                payload.get("max_camera_index", 5)
                            )
                            camera_inventory.clear()
                            camera_inventory.update(inventory)
                            result = {
                                **inventory,
                                "refresh_message": (
                                    f"Detected {len(inventory['devices'])} frame-verified camera(s)."
                                    if inventory["devices"]
                                    else "No camera produced a readable frame. Connect or unlock the iPhone, close other camera apps, then refresh."
                                ),
                            }
                        elif action in {"start", "switch"}:
                            camera_index = payload.get("camera_index")
                            verified = {
                                device["camera_index"]: device
                                for device in camera_inventory.get("devices", [])
                            }
                            if camera_index not in verified:
                                self._send_json(409, {"error": f"Camera index {camera_index!r} is not in the verified device list. Use Refresh Cameras, then choose an available camera."})
                                return
                            current = camera_scanner.snapshot()
                            if current["scanning"]:
                                if current["camera_index"] == camera_index:
                                    result = current
                                    self._send_json(200, result)
                                    return
                                result = camera_scanner.switch(
                                    camera_index,
                                    verified[camera_index].get("device_name"),
                                )
                            else:
                                result = camera_scanner.start(
                                    camera_index,
                                    verified[camera_index].get("device_name"),
                                )
                            if result.get("connection") == "connected":
                                with simulation_lock:
                                    spatial_simulator.camera_reconnected()
                                    shared_session.external_mutation()
                        elif action == "stop":
                            result = camera_scanner.stop()
                            with simulation_lock:
                                spatial_simulator.camera_stopped()
                                shared_session.external_mutation()
                        else:
                            self._send_json(400, {"error": "Camera action must be 'refresh', 'start', 'switch' or 'stop'"})
                            return
                except (TypeError, ValueError) as exc:
                    self._send_json(400, {"error": str(exc)})
                    return
                self._send_json(200, result)
                return
            if parsed_path.path in {"/api/spatial/control", "/api/session/control"}:
                payload = self._read_json_payload()
                if payload is None:
                    return
                action = payload.get("action")
                try:
                    with simulation_lock:
                        if action == "claim_control":
                            result = shared_session.claim_control(payload.get("client_id"))
                        elif action == "release_control":
                            result = shared_session.release_control(payload.get("client_id"))
                        else:
                            result = shared_session.apply(payload, dispatch_spatial_action)
                        result["camera_status"] = camera_scanner.snapshot()
                        result["localization_health"] = spatial_simulator.localization_health(
                            result["camera_status"]
                        )
                except (SessionConflictError, ShoppingRevisionConflictError) as exc:
                    self._send_json(409, {"error": str(exc)})
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

    DashboardHandler.camera_scanner = camera_scanner  # type: ignore[attr-defined]
    DashboardHandler.shared_session = shared_session  # type: ignore[attr-defined]
    DashboardHandler.stop_background = autoplay_shutdown.set  # type: ignore[attr-defined]
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
        handler.camera_scanner.stop()  # type: ignore[attr-defined]
        handler.stop_background()  # type: ignore[attr-defined]
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
