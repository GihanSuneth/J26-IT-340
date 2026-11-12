"""Generate customer-safe recommendation evidence from preserved archives."""

from __future__ import annotations

import csv
import json
from pathlib import Path


COMPONENT_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = COMPONENT_ROOT / "evaluation/research_archive/02_recommendation_engine"
DEFAULT_OUTPUT = COMPONENT_ROOT / "frontend/recommendation/dashboard/reco_evidence.json"


def build_payload(archive: Path = ARCHIVE) -> dict[str, object]:
    frozen_path = archive / "phase_8b_frozen_test_results.json"
    validation_path = archive / "phase_8b_validation_results.json"
    comparison_path = archive / "phase_8b1_baseline_posthoc_test_comparison.csv"
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    with comparison_path.open(newline="", encoding="utf-8") as handle:
        comparison = {row["model"]: row for row in csv.DictReader(handle)}

    test = frozen["metrics"]
    association_validation = validation["association_rules"]
    association_test = comparison["association_rules"]
    popularity_test = comparison["global_popularity"]
    if float(popularity_test["posthoc_test_hit_rate@5"]) <= float(
        association_test["posthoc_test_hit_rate@5"]
    ):
        raise ValueError("Archived popularity comparison does not support the disclosure")

    hit_rate_percent = float(test["hit_rate@5"]) * 100
    ci = [float(value) * 100 for value in test["hit_rate@5_bootstrap_95_ci"]]
    validation_percent = float(association_validation["hit_rate@5"]) * 100
    wording = (
        "Experimental baseline; offline HitRate@5 "
        f"{hit_rate_percent:.1f}% (CI ~{ci[0]:.0f}-{ci[1]:.0f}%) on "
        f"{int(test['basket_count'])} held-out baskets; validation "
        f"{validation_percent:.1f}%; popularity baseline scored higher on test"
    )
    return {
        "wording": wording,
        "selected_model": frozen["selected_model"],
        "selection_frozen_before_test": frozen["selection_frozen_before_test"],
        "offline_test": {
            "basket_count": test["basket_count"],
            "hit_rate_at_5": test["hit_rate@5"],
            "hit_rate_at_5_bootstrap_95_ci": test["hit_rate@5_bootstrap_95_ci"],
        },
        "validation": {"hit_rate_at_5": association_validation["hit_rate@5"]},
        "posthoc_test_comparison": {
            "association_rules_hit_rate_at_5": float(association_test["posthoc_test_hit_rate@5"]),
            "global_popularity_hit_rate_at_5": float(popularity_test["posthoc_test_hit_rate@5"]),
            "diagnostic_only": popularity_test["posthoc_diagnostic_only"].lower() == "true",
            "eligible_for_model_selection": popularity_test["eligible_for_model_selection"].lower() == "true",
        },
        "sources": [
            str(frozen_path.relative_to(COMPONENT_ROOT.parent)),
            str(validation_path.relative_to(COMPONENT_ROOT.parent)),
            str(comparison_path.relative_to(COMPONENT_ROOT.parent)),
        ],
    }


def main() -> int:
    DEFAULT_OUTPUT.write_text(
        json.dumps(build_payload(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
