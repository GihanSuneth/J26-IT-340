"""Chromium acceptance for synchronized Phase 7E shopping mutations."""

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
    "phase_7e_browser_acceptance.json"
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
            customer_a = context.new_page()
            customer_b = context.new_page()
            research = context.new_page()
            for name, page in (("customer_a", customer_a), ("customer_b", customer_b), ("research", research)):
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
            customer_a.goto(base + "/customer", wait_until="domcontentloaded")
            customer_b.goto(base + "/customer", wait_until="domcontentloaded")
            research.goto(base + "/", wait_until="domcontentloaded")
            customer_a.wait_for_selector('[data-product-id="SIM-P-001"][data-shopping-action="increase"]')
            initial = context.request.get(base + "/api/session/state").json()
            customer_a.click('[data-product-id="SIM-P-001"][data-shopping-action="increase"]')
            customer_a.wait_for_function("document.querySelector('#shopping-revision').textContent === '1'")
            customer_b.wait_for_function("document.querySelector('#shopping-revision').textContent === '1'")
            customer_b.click('[data-product-id="SIM-P-002"][data-shopping-action="increase"]')
            customer_b.wait_for_function("document.querySelector('#shopping-revision').textContent === '2'")
            research.wait_for_function("document.querySelector('#shopping-list-revision').textContent === '2'")

            duplicate_payload = {
                "action": "shopping_increase",
                "product_id": "SIM-P-003",
                "quantity": 1,
                "expected_shopping_revision": 2,
                "client_id": "acceptance-api",
                "command_id": "phase7e-duplicate",
            }
            first = context.request.post(base + "/api/session/control", data=duplicate_payload)
            duplicate = context.request.post(base + "/api/session/control", data=duplicate_payload)
            stale = context.request.post(
                base + "/api/session/control",
                data={
                    "action": "shopping_remove",
                    "product_id": "SIM-P-004",
                    "quantity": 1,
                    "expected_shopping_revision": 1,
                    "client_id": "stale-tab",
                    "command_id": "phase7e-stale",
                },
            )
            final_state = context.request.get(base + "/api/session/state").json()
            research.wait_for_function("document.querySelector('#shopping-list-revision').textContent === '3'")
            customer_a.reload(wait_until="domcontentloaded")
            customer_a.wait_for_function("document.querySelector('#shopping-revision').textContent === '3'")
            report.update(
                {
                    "session_id": initial["session_id"],
                    "two_customer_tabs_synchronized": True,
                    "research_view_synchronized": research.locator("#shopping-list-revision").text_content() == "3",
                    "shopping_revision_after_three_mutations": final_state["shopping_list_revision"],
                    "route_revision_after_three_mutations": final_state["route_revision"],
                    "duplicate_command_statuses": [first.status, duplicate.status],
                    "duplicate_applied_once": first.json()["shopping_session"] == duplicate.json()["shopping_session"],
                    "stale_command_status": stale.status,
                    "refresh_preserved_session": customer_a.locator("#session").text_content() == initial["session_id"],
                    "refresh_preserved_revision": customer_a.locator("#shopping-revision").text_content() == "3",
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
    if report.get("shopping_revision_after_three_mutations") != 3:
        raise RuntimeError("Three unique mutations did not produce shopping revision 3")
    if report.get("stale_command_status") != 409 or not report.get("duplicate_applied_once"):
        raise RuntimeError("Stale or duplicate command contract failed")
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
