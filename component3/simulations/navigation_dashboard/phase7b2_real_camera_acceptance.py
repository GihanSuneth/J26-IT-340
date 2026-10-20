"""Privacy-preserving live-preview acceptance; no camera frame is saved."""

from __future__ import annotations

import json
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "component3/evaluation/camera_assisted/phase7b2_real_preview_2026-10-15.json"


def free_port() -> int:
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 0))
        return int(candidate.getsockname()[1])


def main() -> int:
    from playwright.sync_api import sync_playwright

    port = free_port()
    server = subprocess.Popen(
        [
            str(ROOT / "component3/.venv/bin/python"),
            "-m", "component3.simulations.navigation_dashboard.dashboard",
            "--port", str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    result = {
        "camera_index": 0,
        "real_camera": True,
        "frame_saved": False,
        "preview_loaded": False,
        "preview_dimensions": None,
        "selector_options": [],
        "scanner_state": None,
        "error": None,
    }
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/camera/state", timeout=1):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise RuntimeError("Local dashboard did not start")
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1366, "height": 768})
            page.goto(f"http://127.0.0.1:{port}/", wait_until="networkidle")
            page.click("#refresh-cameras")
            page.wait_for_function("document.querySelector('#camera-index').value !== ''")
            result["selector_options"] = page.locator("#camera-index option").all_text_contents()
            page.select_option("#camera-index", "0")
            page.click("#select-camera")
            page.click("#start-camera")
            page.wait_for_function(
                """() => {
                  const image = document.querySelector('#camera-preview');
                  return !image.hidden && image.complete && image.naturalWidth > 0;
                }""",
                timeout=15000,
            )
            result["preview_loaded"] = True
            result["preview_dimensions"] = page.locator("#camera-preview").evaluate(
                "image => [image.naturalWidth, image.naturalHeight]"
            )
            result["scanner_state"] = page.request.get(
                f"http://127.0.0.1:{port}/api/camera/state"
            ).json()
            page.click("#stop-camera")
            browser.close()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["preview_loaded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
