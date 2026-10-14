"""Capture a genuine one-click guided-demo run in a local Chromium browser."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import threading
from http.server import ThreadingHTTPServer
from typing import Any

from .dashboard import make_handler
from .spatial_simulation import SpatialNavigationSimulation


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SCREENSHOT_ROOT = (
    REPOSITORY_ROOT
    / "component3/docs/research_evidence/04_navigation_algorithms/screenshots"
)
DEFAULT_EVALUATION_ROOT = REPOSITORY_ROOT / "component3/evaluation/navigation_simulation"
SCREENSHOTS = {
    "initial_route": "C3-DASH-042_guided_initial_route.png",
    "first_turn": "C3-DASH-043_guided_first_turn.png",
    "first_checkpoint": "C3-DASH-044_guided_first_checkpoint.png",
    "first_product_pickup": "C3-DASH-045_guided_first_product_pickup.png",
    "wrong_turn": "C3-DASH-046_guided_wrong_turn.png",
    "confirmed_deviation": "C3-DASH-047_guided_confirmed_deviation.png",
    "replacement_route": "C3-DASH-048_guided_replacement_route.png",
    "second_product_pickup": "C3-DASH-049_guided_second_product_pickup.png",
    "checkout_completion": "C3-DASH-050_guided_checkout_completion.png",
}


def _metrics(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Calculate summary values from the browser-exported authoritative state."""
    truth = snapshot["travelled_ground_truth"]
    estimates = snapshot["travelled_estimate"]
    errors = [
        math.hypot(estimated["x_m"] - actual["x_m"], estimated["y_m"] - actual["y_m"])
        for actual, estimated in zip(truth, estimates, strict=True)
    ]
    events = snapshot["events"]
    return {
        "schema_version": "1.0",
        "source": "real Chromium browser using the localhost spatial dashboard",
        "synthetic_simulation_only": True,
        "status": snapshot["status"],
        "guided_demo": snapshot["guided_demo"],
        "selected_product_ids": snapshot["selected_product_ids"],
        "collected_product_ids": snapshot["collected_product_ids"],
        "detected_checkpoint_ids": snapshot["detected_checkpoint_ids"],
        "reroute_count": snapshot["reroute_count"],
        "simulation_time_s": snapshot["simulation_time_s"],
        "sample_count": len(errors),
        "position_error_m": {
            "mean": sum(errors) / len(errors),
            "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
            "maximum": max(errors),
        },
        "event_types": [event["event_type"] for event in events],
        "screenshots": SCREENSHOTS,
    }


def run_browser_acceptance(
    screenshot_root: Path = DEFAULT_SCREENSHOT_ROOT,
    evaluation_root: Path = DEFAULT_EVALUATION_ROOT,
) -> dict[str, Any]:
    """Start the local app, click once, capture required states, and export results."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:  # pragma: no cover - environment diagnostic
        raise RuntimeError("Playwright is required for browser acceptance") from exc

    screenshot_root.mkdir(parents=True, exist_ok=True)
    evaluation_root.mkdir(parents=True, exist_ok=True)
    simulation = SpatialNavigationSimulation()
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), make_handler(spatial_simulation=simulation)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    console_errors: list[str] = []
    page_errors: list[str] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            page.on(
                "console",
                lambda message: console_errors.append(message.text)
                if message.type == "error"
                else None,
            )
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.goto(
                f"http://127.0.0.1:{server.server_port}/",
                wait_until="networkidle",
            )
            page.click("#guided-demo")
            page.wait_for_function(
                "document.querySelector('#guided-stage').textContent.includes('Stage 1/9')"
            )
            page.screenshot(path=screenshot_root / SCREENSHOTS["initial_route"], full_page=True)
            page.screenshot(path=screenshot_root / SCREENSHOTS["first_checkpoint"], full_page=True)

            page.wait_for_function(
                "document.querySelector('#guided-stage').textContent.includes('Stage 2/9')"
            )
            page.screenshot(path=screenshot_root / SCREENSHOTS["first_turn"], full_page=True)

            page.wait_for_function(
                "document.querySelector('#guided-stage').textContent.includes('Stage 4/9')"
            )
            page.screenshot(
                path=screenshot_root / SCREENSHOTS["first_product_pickup"], full_page=True
            )

            page.wait_for_function(
                "document.querySelector('#events').textContent.includes('takes valid lane edge')",
                timeout=30000,
            )
            page.screenshot(path=screenshot_root / SCREENSHOTS["wrong_turn"], full_page=True)

            page.wait_for_function(
                "document.querySelector('#events').textContent.includes('confirmed the trolley')",
                timeout=30000,
            )
            page.screenshot(
                path=screenshot_root / SCREENSHOTS["confirmed_deviation"], full_page=True
            )
            page.wait_for_function(
                "document.querySelector('#guided-stage').textContent.includes('Stage 6/9')"
            )
            page.screenshot(
                path=screenshot_root / SCREENSHOTS["replacement_route"], full_page=True
            )

            page.wait_for_function(
                "document.querySelector('#guided-stage').textContent.includes('Stage 7/9')",
                timeout=30000,
            )
            page.screenshot(
                path=screenshot_root / SCREENSHOTS["second_product_pickup"], full_page=True
            )
            page.wait_for_function(
                "document.querySelector('#guided-stage').textContent.includes('Stage 9/9')",
                timeout=30000,
            )
            page.screenshot(
                path=screenshot_root / SCREENSHOTS["checkout_completion"], full_page=True
            )
            response = page.request.get(
                f"http://127.0.0.1:{server.server_port}/api/spatial/export.json"
            )
            if not response.ok:
                raise RuntimeError(f"Dashboard export failed with HTTP {response.status}")
            snapshot = response.json()
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)

    export_path = evaluation_root / "guided_demo_panel_browser_run.json"
    metrics_path = evaluation_root / "guided_demo_panel_summary.json"
    export_path.write_text(
        json.dumps(snapshot, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    report = _metrics(snapshot)
    report["console_errors"] = console_errors
    report["page_errors"] = page_errors
    metrics_path.write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    if console_errors or page_errors:
        raise RuntimeError(
            f"Browser acceptance recorded errors: console={console_errors}, page={page_errors}"
        )
    return report


def main() -> int:
    """Run acceptance with optional output overrides and print the summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screenshots", type=Path, default=DEFAULT_SCREENSHOT_ROOT)
    parser.add_argument("--evaluation", type=Path, default=DEFAULT_EVALUATION_ROOT)
    arguments = parser.parse_args()
    print(
        json.dumps(
            run_browser_acceptance(arguments.screenshots, arguments.evaluation),
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
