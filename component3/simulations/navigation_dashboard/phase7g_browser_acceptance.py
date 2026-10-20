"""Headless Chromium acceptance for the Phase 7G tablet customer workflow."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer

from .dashboard import make_handler


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "component3/evaluation/navigation_simulation/phase7g_browser_acceptance.json"
SCREENSHOT = ROOT / "component3/docs/research_evidence/04_navigation_algorithms/screenshots/C3-DASH-7G-customer-tablet.png"


def run_acceptance() -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    handler = make_handler()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1024, "height": 768})
            customer = context.new_page()
            customer.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
            customer.on("pageerror", lambda error: page_errors.append(str(error)))
            customer.goto(f"http://127.0.0.1:{server.server_port}/customer", wait_until="networkidle")
            customer.wait_for_selector("#map svg")
            layout = customer.evaluate("""({
                horizontalOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                verticalPageOverflow: document.documentElement.scrollHeight > window.innerHeight + 2,
                mapVisible: document.querySelector('#map').getBoundingClientRect().height > 250,
                productPanelVisible: document.querySelector('.products-panel').getBoundingClientRect().width > 200
            })""")
            SCREENSHOT.parent.mkdir(parents=True, exist_ok=True)
            customer.screenshot(path=SCREENSHOT, full_page=True)
            initial = customer.evaluate("window.fetch('/api/session/state').then(r => r.json())")
            customer.click("#start")
            customer.wait_for_function("fetch('/api/session/state').then(r => r.json()).then(s => s.simulation_time_s > 0)")
            customer.wait_for_function("fetch('/api/session/state').then(r => r.json()).then(s => s.status === 'awaiting_product_confirmation')", timeout=30000)
            arrived = customer.evaluate("window.fetch('/api/session/state').then(r => r.json())")
            customer.click("#skip")
            customer.click("#skip-later")
            customer.wait_for_function("fetch('/api/session/state').then(r => r.json()).then(s => s.status === 'navigating')")
            deferred = customer.evaluate("window.fetch('/api/session/state').then(r => r.json())")
            operator = context.new_page()
            operator.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="networkidle")
            operator_state = operator.evaluate("window.fetch('/api/session/state').then(r => r.json())")
            browser.close()
    finally:
        handler.stop_background()  # type: ignore[attr-defined]
        handler.camera_scanner.stop()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    report = {
        "milestone": "C3-P7G", "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "viewport": {"width": 1024, "height": 768}, "layout": layout,
        "initial_state": initial["navigation_state"],
        "arrival_state": arrived["navigation_state"],
        "autoplay_backend_owned": arrived["simulation_clock"]["owner"] == "backend_singleton",
        "deferred_event_recorded": any(event["event_type"] == "product_skipped_deferred" for event in deferred["events"]),
        "shared_session_across_views": deferred["session_id"] == operator_state["session_id"],
        "console_errors": console_errors, "page_errors": page_errors,
        "screenshot": str(SCREENSHOT.relative_to(ROOT)),
    }
    if any((layout["horizontalOverflow"], layout["verticalPageOverflow"], not layout["mapVisible"],
            not layout["productPanelVisible"], console_errors, page_errors,
            not report["autoplay_backend_owned"], not report["deferred_event_recorded"],
            not report["shared_session_across_views"])):
        raise RuntimeError(f"Phase 7G browser acceptance failed: {report}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run_acceptance(), indent=2))
