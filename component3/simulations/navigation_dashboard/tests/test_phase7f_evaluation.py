"""Regression checks for the Phase 7F research evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from component3.simulations.navigation_dashboard.phase7f_evaluation import (
    _baseline_trials,
    _journey_trials,
    _localization_trials,
    run_evaluation,
)


class Phase7FEvaluationTests(unittest.TestCase):
    def test_paired_route_trials_include_improvements_ties_and_oracle_matches(self) -> None:
        rows = _baseline_trials()
        self.assertTrue(any(row["outcome"] == "improvement" for row in rows))
        self.assertTrue(any(row["outcome"] == "tie" for row in rows))
        self.assertTrue(all(row["oracle_match"] for row in rows))
        self.assertTrue(any(row["anchor"]["anchor_type"] == "edge" for row in rows))

    def test_localization_labels_cover_required_outcomes_without_truth_input(self) -> None:
        rows = _localization_trials()
        scenarios = {row["scenario"] for row in rows}
        self.assertEqual(len(rows), 50)
        self.assertTrue({"TP", "TN"}.issubset({row["decision"] for row in rows}))
        self.assertNotIn("FP", {row["decision"] for row in rows})
        self.assertNotIn("FN", {row["decision"] for row in rows})
        self.assertIn("missed_checkpoint", scenarios)
        self.assertIn("delayed_observation", scenarios)
        self.assertIn("dead_reckoning_drift_correction", scenarios)
        self.assertTrue(all(not row["ground_truth_used_as_localization_input"] for row in rows))

    def test_complete_journeys_pass_and_use_explicit_pickup(self) -> None:
        rows = _journey_trials()
        self.assertTrue(all(row["passed"] for row in rows))
        planned = next(row for row in rows if row["scenario"] == "planned_route_shopping_and_checkout")
        self.assertEqual(planned["pickup_events"], planned["requested_units"])
        self.assertFalse(planned["unauthorized_checkout"])
        unexpected = next(
            row for row in rows
            if row["scenario"] == "unexpected_checkpoint_correction_and_replan"
        )
        self.assertEqual(
            unexpected["classification"],
            "unexpected_but_plausible_mapped_checkpoint",
        )

    def test_runner_writes_machine_readable_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory, patch(
            "component3.simulations.navigation_dashboard.phase7f_evaluation.WARMUP_REPETITIONS", 1
        ), patch(
            "component3.simulations.navigation_dashboard.phase7f_evaluation.MEASURED_REPETITIONS", 2
        ):
            result = run_evaluation(Path(directory))
            for path in result["paths"].values():
                self.assertTrue(Path(path).is_file())
            aggregate = json.loads(Path(result["paths"]["aggregate"]).read_text())
            self.assertEqual(aggregate["localization"]["fp"], 0)
            self.assertEqual(aggregate["localization"]["fn"], 0)
            self.assertTrue(aggregate["complete_journeys"]["all_passed"])


if __name__ == "__main__":
    unittest.main()
