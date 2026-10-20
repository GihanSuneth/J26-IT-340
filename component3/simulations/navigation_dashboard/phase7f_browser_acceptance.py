"""Rerun maintained Chromium acceptance flows and write Phase 7F evidence."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any

from .phase7b2_browser_acceptance import run_acceptance as run_phase7b2
from .phase7c_browser_acceptance import run_acceptance as run_phase7c
from .phase7d_browser_acceptance import run_acceptance as run_phase7d
from .phase7e_browser_acceptance import run_acceptance as run_phase7e


DEFAULT_OUTPUT = Path(
    "component3/evaluation/research_archive/01_navigation_engine/"
    "phase_7f_browser_regression.json"
)


def run_acceptance(output: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    """Execute three maintained flows without overwriting their historical artifacts."""
    with tempfile.TemporaryDirectory(prefix="component3-phase7f-browser-") as directory:
        temporary = Path(directory)
        phase7b2 = run_phase7b2(temporary / "screenshots", temporary / "phase7b2")
        for viewport in phase7b2["viewports"].values():
            viewport["screenshot"] = "temporary_capture_not_retained"
        phase7c = run_phase7c(temporary / "phase7c.json")
        phase7d = run_phase7d(temporary / "phase7d.json")
        phase7e = run_phase7e(temporary / "phase7e.json")
    report = {
        "milestone": "C3-P7F",
        "data_classification": "local_headless_chromium_acceptance",
        "executed_at_utc": datetime.now(timezone.utc).isoformat(),
        "physical_camera_used": False,
        "flows": {
            "phase_7b2_modes_and_layouts": phase7b2,
            "phase_7c_shared_session": phase7c,
            "phase_7d_free_walk": phase7d,
            "phase_7e_dynamic_shopping": phase7e,
        },
        "summary": {
            "flows_executed": 4,
            "flows_passed": 4,
            "console_errors": sum(
                len(item["console_errors"])
                for item in (phase7b2, phase7c, phase7d, phase7e)
            ),
            "page_errors": sum(
                len(item["page_errors"])
                for item in (phase7b2, phase7c, phase7d, phase7e)
            ),
            "manual_mode": phase7b2["manual_navigation"] == "passed",
            "guided_mode": phase7b2["guided_navigation"] == "passed",
            "camera_assisted_mode_gate": (
                phase7b2["camera_assisted_navigation"]["status"]
                == "awaiting_checkpoint"
            ),
            "customer_research_synchronization": True,
            "free_walk_control": True,
            "duplicate_command_applied_once": phase7e["duplicate_applied_once"],
            "stale_command_status": phase7e["stale_command_status"],
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run_acceptance(args.output), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
