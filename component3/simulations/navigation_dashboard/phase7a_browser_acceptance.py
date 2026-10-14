"""Capture Phase 7A structured guidance states in a real local Chromium run."""

from __future__ import annotations

import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any

from .dashboard import make_handler
from .spatial_simulation import SpatialNavigationSimulation


ROOT = Path(__file__).resolve().parents[3]
SCREENSHOT_ROOT = ROOT / "component3/docs/research_evidence/04_navigation_algorithms/screenshots"
EVALUATION_ROOT = ROOT / "component3/evaluation/navigation_simulation"
SCREENSHOTS = {
    "automatic_start": "C3-DASH-053_phase7a_automatic_start.png",
    "straight": "C3-DASH-054_phase7a_straight_guidance.png",
    "left": "C3-DASH-055_phase7a_left_guidance.png",
    "right": "C3-DASH-056_phase7a_right_guidance.png",
    "next_checkpoint": "C3-DASH-057_phase7a_next_checkpoint.png",
    "checkpoint_correction": "C3-DASH-058_phase7a_checkpoint_correction.png",
    "shelf_arrival": "C3-DASH-059_phase7a_shelf_arrival.png",
    "shelf_popup": "C3-DASH-060_phase7a_shelf_level_side_popup.png",
    "pickup_confirmed": "C3-DASH-061_phase7a_pickup_confirmed.png",
    "wrong_turn": "C3-DASH-062_phase7a_wrong_turn.png",
    "updated_route": "C3-DASH-063_phase7a_updated_route.png",
    "checkout": "C3-DASH-064_phase7a_checkout.png",
    "evaluation_summary": "C3-DASH-065_phase7a_evaluation_summary.png",
}


def run() -> dict[str, Any]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for browser acceptance") from exc
    SCREENSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    EVALUATION_ROOT.mkdir(parents=True, exist_ok=True)
    simulation = SpatialNavigationSimulation()
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(spatial_simulation=simulation))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="networkidle")
            page.click("#guided-demo")
            page.wait_for_function("document.querySelector('#guided-stage').textContent.includes('Stage 1/9')")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["automatic_start"], full_page=True)

            def capture_guidance(kind: str, key: str, timeout: int = 30000) -> None:
                page.wait_for_function(
                    "kind => document.querySelector('#instruction').dataset.guidanceType === kind",
                    arg=kind,
                    timeout=timeout,
                )
                page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS[key], full_page=True)

            capture_guidance("TURN_LEFT", "left")
            capture_guidance("STRAIGHT", "straight")
            capture_guidance("TURN_RIGHT", "right")
            page.wait_for_function("document.querySelector('#instruction').dataset.guidanceType === 'PRODUCT_REACHED' || document.querySelector('[data-guidance-type=\"PRODUCT_REACHED\"]')")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["shelf_arrival"], full_page=True)
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["shelf_popup"], full_page=True)
            page.wait_for_function("document.querySelector('#events').textContent.includes('Automated simulated pickup confirmation: Bananas')")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["pickup_confirmed"], full_page=True)
            page.wait_for_function("document.querySelector('#events').textContent.includes('N1_3 → N0_3')")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["wrong_turn"], full_page=True)
            page.wait_for_function("document.querySelector('#guided-stage').textContent.includes('Stage 6/9')")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["updated_route"], full_page=True)
            page.wait_for_function("document.querySelector('#instruction').dataset.guidanceType === 'APPROACH_CHECKPOINT'")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["next_checkpoint"], full_page=True)
            page.wait_for_function("document.querySelector('#last-checkpoint').textContent.includes('CP201')")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["checkpoint_correction"], full_page=True)
            page.locator("#playback").evaluate("element => { element.value = 8; element.dispatchEvent(new Event('input', {bubbles: true})); }")
            page.wait_for_function("document.querySelector('#guided-stage').textContent.includes('Stage 9/9')")
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["checkout"], full_page=True)
            page.screenshot(path=SCREENSHOT_ROOT / SCREENSHOTS["evaluation_summary"], full_page=True)
            response = page.request.get(f"http://127.0.0.1:{server.server_port}/api/spatial/export.json")
            if not response.ok:
                raise RuntimeError(f"browser export failed: HTTP {response.status}")
            snapshot = response.json()
            viewport_checks: dict[str, Any] = {}
            for width, height in ((1366, 768), (1920, 1080)):
                page.set_viewport_size({"width": width, "height": height})
                viewport_checks[f"{width}x{height}"] = page.evaluate(
                    """() => ({
                      noHorizontalOverflow: document.documentElement.scrollWidth <= window.innerWidth,
                      mapWidth: Math.round(document.querySelector('#map').getBoundingClientRect().width),
                      guidanceWidth: Math.round(document.querySelector('.primary-guidance').getBoundingClientRect().width)
                    })"""
                )
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
    report = {
        "schema_version": "1.0",
        "source": "real headless Chromium using the localhost Phase 7A dashboard",
        "synthetic_simulation_only": True,
        "console_or_page_errors": errors,
        "status": snapshot["status"],
        "products": snapshot["collected_product_ids"],
        "checkpoints": snapshot["detected_checkpoint_ids"],
        "reroute_count": snapshot["reroute_count"],
        "guidance_event_count": len(snapshot["guidance_events"]),
        "viewport_checks": viewport_checks,
        "screenshots": SCREENSHOTS,
    }
    (EVALUATION_ROOT / "phase7a_browser_run.json").write_text(json.dumps(snapshot, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (EVALUATION_ROOT / "phase7a_browser_summary.json").write_text(json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    if (
        errors
        or snapshot["status"] != "complete"
        or not all(item["noHorizontalOverflow"] for item in viewport_checks.values())
    ):
        raise RuntimeError(f"Phase 7A browser acceptance failed: {report}")
    return report


def main() -> int:
    print(json.dumps(run(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
