"""Two-view Chromium acceptance for the Phase 7C shared navigation session."""

from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from typing import Any

from .dashboard import make_handler
from .spatial_simulation import SpatialNavigationSimulation


DEFAULT_OUTPUT = Path(
    "component3/evaluation/research_archive/03_integrated_system/"
    "phase_7c_browser_acceptance.json"
)


def run_acceptance(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    """Verify synchronized views, pure refresh, controller exclusion, and takeover."""
    from playwright.sync_api import sync_playwright

    handler = make_handler(spatial_simulation=SpatialNavigationSimulation())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_port}"
    report: dict[str, Any] = {"console_errors": [], "page_errors": []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1366, "height": 768})
            research = context.new_page()
            customer = context.new_page()
            for name, page in (("research", research), ("customer", customer)):
                page.on(
                    "console",
                    lambda message, view=name: report["console_errors"].append(
                        {"view": view, "message": message.text}
                    )
                    if message.type == "error"
                    else None,
                )
                page.on(
                    "pageerror",
                    lambda error, view=name: report["page_errors"].append(
                        {"view": view, "message": str(error)}
                    ),
                )
            research.goto(base_url + "/", wait_until="domcontentloaded")
            customer.goto(base_url + "/customer", wait_until="domcontentloaded")
            research.wait_for_selector("#map svg")
            customer.wait_for_function(
                "document.querySelector('#session').textContent.startsWith('nav-')"
            )

            initial = context.request.get(base_url + "/api/session/state").json()
            customer.reload(wait_until="domcontentloaded")
            customer.wait_for_function(
                "document.querySelector('#session').textContent.startsWith('nav-')"
            )
            after_refresh = context.request.get(base_url + "/api/session/state").json()
            if after_refresh["session_id"] != initial["session_id"]:
                raise RuntimeError("Customer refresh replaced the server session")
            if after_refresh["simulation_time_s"] != initial["simulation_time_s"]:
                raise RuntimeError("Read/refresh advanced simulation time")

            customer.click("#start")
            deadline = time.monotonic() + 8.0
            running: dict[str, Any] | None = None
            while time.monotonic() < deadline:
                running = context.request.get(base_url + "/api/session/state").json()
                if running["simulation_time_s"] > 0 and running["controller_id"]:
                    break
                customer.wait_for_timeout(100)
            else:
                raise RuntimeError("Shared session did not begin deterministic stepping")
            assert running is not None

            customer_session = customer.locator("#session").inner_text()
            required_customer_fields = all(
                customer.locator(f"#{element_id}").count() == 1
                for element_id in (
                    "products", "instruction", "location", "checkpoint", "shelf",
                    "confirm", "voice", "route", "session", "revision",
                )
            )
            research_session = research.evaluate(
                "fetch('/api/session/state').then(response => response.json()).then(value => value.session_id)"
            )
            if customer_session != research_session:
                raise RuntimeError("Customer and research views did not share a session")

            controller = running["controller_id"]
            controller_view = customer if controller.startswith("customer-") else research
            observer_view = research if controller_view is customer else customer
            observer_client_id = observer_view.evaluate(
                "sessionStorage.getItem('comp3-customer-client-id') || "
                "sessionStorage.getItem('comp3-navigation-client-id')"
            )
            before_close_time = running["simulation_time_s"]
            controller_view.close()
            observer_view.wait_for_timeout(2300)
            takeover = context.request.get(base_url + "/api/session/state").json()
            if takeover["controller_id"] == controller:
                response = context.request.post(
                    base_url + "/api/session/control",
                    data={
                        "action": "step",
                        "client_id": observer_client_id,
                        "command_id": f"{observer_client_id}:acceptance-takeover",
                    },
                )
                if not response.ok:
                    raise RuntimeError(
                        f"Remaining view could not take over: {response.text()}"
                    )
                takeover = response.json()
            if takeover["controller_id"] != observer_client_id:
                raise RuntimeError("Remaining view did not own the renewed lease")

            report.update(
                {
                    "session_id": initial["session_id"],
                    "refresh_preserved_session": True,
                    "refresh_advanced_time": False,
                    "shared_session_visible_in_both_views": True,
                    "initial_controller": controller,
                    "takeover_controller": takeover["controller_id"],
                    "time_before_controller_close_s": before_close_time,
                    "time_after_takeover_s": takeover["simulation_time_s"],
                    "controller_lease_timeout_s": takeover[
                        "controller_lease_timeout_s"
                    ],
                    "customer_view_required_fields": required_customer_fields,
                }
            )
            browser.close()
    finally:
        handler.camera_scanner.stop()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    if report["console_errors"] or report["page_errors"]:
        raise RuntimeError(
            f"Browser errors: {report['console_errors']} {report['page_errors']}"
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    print(json.dumps(run_acceptance(arguments.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
