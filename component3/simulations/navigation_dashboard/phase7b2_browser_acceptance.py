"""Chromium acceptance for the Phase 7B.2 dashboard, voice, and layouts."""

from __future__ import annotations

import argparse
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
import threading
from typing import Any

from .dashboard import make_handler
from .spatial_simulation import SpatialNavigationSimulation


DEFAULT_SCREENSHOT_ROOT = Path(
    "component3/docs/research_evidence/04_navigation_algorithms/screenshots"
)
DEFAULT_EVALUATION_ROOT = Path("component3/evaluation/navigation_simulation")
VIEWPORTS = (
    ("1366x768", 1366, 768),
    ("1920x1080", 1920, 1080),
    ("mobile_390x844", 390, 844),
)


def run_acceptance(
    screenshot_root: Path = DEFAULT_SCREENSHOT_ROOT,
    evaluation_root: Path = DEFAULT_EVALUATION_ROOT,
) -> dict[str, Any]:
    """Exercise layouts and voice behavior against the real local dashboard."""
    from playwright.sync_api import sync_playwright

    screenshot_root.mkdir(parents=True, exist_ok=True)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    handler = make_handler(spatial_simulation=SpatialNavigationSimulation())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    report: dict[str, Any] = {"viewports": {}, "console_errors": [], "page_errors": []}
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            page.add_init_script(
                """
                window.__speechCalls = [];
                window.SpeechSynthesisUtterance = function(text) { this.text = text; };
                Object.defineProperty(window, 'speechSynthesis', {value: {
                  speaking: false, pending: false,
                  speak(u) { window.__speechCalls.push(u.text); if (u.onstart) u.onstart(); if (u.onend) u.onend(); },
                  cancel() {}, getVoices() { return [{name: 'Acceptance Voice', lang: 'en-US'}]; },
                  onvoiceschanged: null
                }, configurable: true});
                """
            )
            page.on("console", lambda message: report["console_errors"].append(message.text) if message.type == "error" else None)
            page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
            page.goto(f"http://127.0.0.1:{server.server_port}/", wait_until="domcontentloaded")
            page.wait_for_selector("#map svg")

            for name, width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(100)
                no_overflow = page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
                sections = page.locator(".shopping-panel, .map-card, .camera-panel, .guidance-panel, .results-panel").count()
                screenshot = screenshot_root / f"C3-DASH-7B2-{name}.png"
                page.screenshot(path=screenshot, full_page=True)
                report["viewports"][name] = {
                    "horizontal_overflow": not no_overflow,
                    "required_sections": sections,
                    "screenshot": str(screenshot),
                }

            page.click("#voice-toggle")
            first = page.evaluate("window.dashboardVoice.speak('stable-event', 'Turn left')")
            duplicate = page.evaluate("window.dashboardVoice.speak('stable-event', 'Turn left')")
            calls_after_duplicate = page.evaluate("window.__speechCalls.slice()")
            page.click("#voice-toggle")
            disabled_call = page.evaluate("window.dashboardVoice.speak('disabled-event', 'Should not speak')")
            report["voice"] = {
                "first_event_spoken": first,
                "duplicate_event_spoken": duplicate,
                "calls_after_duplicate": calls_after_duplicate,
                "disabled_event_spoken": disabled_call,
            }

            page.set_viewport_size({"width": 1366, "height": 768})
            page.click("#start")
            page.wait_for_function("document.querySelector('#sim-status').textContent.includes('navigating')")
            report["manual_navigation"] = "passed"
            page.click("#reset")
            page.click("#guided-demo")
            page.wait_for_function("document.querySelector('#guided-stage').textContent.includes('Stage 1/9')")
            report["guided_navigation"] = "passed"
            page.click("#reset")
            page.wait_for_function("document.querySelector('#sim-status').textContent.includes('ready')")
            camera_response = page.request.post(
                f"http://127.0.0.1:{server.server_port}/api/spatial/control",
                data={"action": "camera_evaluation"},
            )
            camera_state = camera_response.json()
            report["camera_assisted_navigation"] = {
                "status": camera_state["status"],
                "expected_checkpoint": camera_state["camera_evaluation"]["gate"]["checkpoint_id"],
            }
            browser.close()
    finally:
        handler.camera_scanner.stop()  # type: ignore[attr-defined]
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    if report["console_errors"] or report["page_errors"]:
        raise RuntimeError(f"Browser errors: {report['console_errors']} {report['page_errors']}")
    if any(item["horizontal_overflow"] for item in report["viewports"].values()):
        raise RuntimeError("Responsive acceptance found horizontal overflow")
    output = evaluation_root / "phase7b2_browser_acceptance.json"
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=DEFAULT_SCREENSHOT_ROOT)
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION_ROOT)
    arguments = parser.parse_args()
    print(json.dumps(run_acceptance(arguments.screenshots, arguments.evaluation), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
