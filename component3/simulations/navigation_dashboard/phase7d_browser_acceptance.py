"""Chromium acceptance for synchronized Phase 7D free-walk controls."""

from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any

from .dashboard import make_handler
from .spatial_simulation import SpatialNavigationSimulation


DEFAULT_OUTPUT = Path(
    "component3/evaluation/research_archive/01_navigation_engine/"
    "phase_7d_browser_acceptance.json"
)


def run_acceptance(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    handler = make_handler(spatial_simulation=SpatialNavigationSimulation())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    report: dict[str, Any] = {"console_errors": [], "page_errors": []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1366, "height": 900})
            research = context.new_page()
            customer = context.new_page()
            for name, page in (("research", research), ("customer", customer)):
                page.on(
                    "console",
                    lambda message, view=name: report["console_errors"].append(
                        {"view": view, "message": message.text}
                    ) if message.type == "error" else None,
                )
                page.on(
                    "pageerror",
                    lambda error, view=name: report["page_errors"].append(
                        {"view": view, "message": str(error)}
                    ),
                )
            research.goto(base + "/", wait_until="domcontentloaded")
            customer.goto(base + "/customer", wait_until="domcontentloaded")
            research.wait_for_selector("#map svg")
            customer.wait_for_function(
                "document.querySelector('#session').textContent.startsWith('nav-')"
            )
            initial = context.request.get(base + "/api/session/state").json()
            customer.click("#enter-free-walk")
            customer.wait_for_function(
                "document.querySelector('#connection').textContent.includes('free walk stopped')"
            )
            research.wait_for_function(
                "document.querySelector('#free-walk-state').textContent === 'stopped'"
            )
            customer.wait_for_selector("#free-walk-options button")
            options = customer.locator("#free-walk-options button").count()
            customer.locator("#free-walk-options button").first.click()
            customer.wait_for_timeout(650)
            moving = context.request.get(base + "/api/session/state").json()
            customer.click("#free-walk-stop")
            customer.wait_for_function(
                "document.querySelector('#connection').textContent.includes('free walk stopped')"
            )
            stopped = context.request.get(base + "/api/session/state").json()
            customer.click("#request-navigation")
            customer.wait_for_function(
                "document.querySelector('#connection').textContent.includes('navigating')"
            )
            replanned = context.request.get(base + "/api/session/state").json()
            research.wait_for_function(
                "Number(document.querySelector('#route-revision').textContent) >= 1"
            )
            research.wait_for_function(
                "document.querySelector('#free-walk-state').textContent === 'inactive'"
            )
            report.update(
                {
                    "session_id": initial["session_id"],
                    "same_session_in_both_views": (
                        customer.locator("#session").inner_text() == initial["session_id"]
                    ),
                    "free_walk_edge_options": options,
                    "simulation_time_before_s": initial["simulation_time_s"],
                    "simulation_time_after_move_s": moving["simulation_time_s"],
                    "ground_truth_changed_on_step": moving["ground_truth"] != initial["ground_truth"],
                    "stop_preserved_time_s": stopped["simulation_time_s"],
                    "route_revision_after_navigation_request": replanned["route_revision"],
                    "partial_edge_distance_m": replanned["adaptive_replan_history"][-1]["partial_edge_distance_m"],
                    "research_view_synchronized": research.locator("#free-walk-state").text_content() == "inactive",
                }
            )
            browser.close()
    finally:
        handler.camera_scanner.stop()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    if report["console_errors"] or report["page_errors"]:
        raise RuntimeError(f"Browser errors: {report['console_errors']} {report['page_errors']}")
    if not report.get("ground_truth_changed_on_step"):
        raise RuntimeError("Free-walk browser command did not move on a deterministic step")
    if not report.get("research_view_synchronized"):
        raise RuntimeError("Research view did not synchronize the navigation transition")
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
