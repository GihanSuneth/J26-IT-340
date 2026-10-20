"""Phase 8B.1 audit guardrails and evidence-contract tests."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import unittest

from component3.backend.comp3_reco_navigation.recommendation.phase8b1_audit import (
    _catalog_audit,
)


ROOT = Path(__file__).resolve().parents[4]
COMPONENT = ROOT / "component3"
EVIDENCE = COMPONENT / "evaluation/research_archive/02_recommendation_engine"


class Phase8B1EvidenceTests(unittest.TestCase):
    def test_all_68_products_have_audited_mapping_rows(self) -> None:
        rows, summary = _catalog_audit(COMPONENT)
        self.assertEqual(len(rows), 68)
        self.assertEqual(summary["coverage_before_verified_reconciliation"]["count"], 4)
        self.assertEqual(summary["coverage_after_verified_reconciliation"]["count"], 4)
        self.assertEqual(summary["new_mapping_approvals"], 0)
        eligible = [row for row in rows if row["navigation_eligible"]]
        self.assertEqual(len(eligible), 4)
        self.assertTrue(all(row["reference_validation"] == "passed_active_demo_graph" for row in eligible))

    def test_posthoc_comparison_cannot_drive_selection(self) -> None:
        with (EVIDENCE / "phase_8b1_baseline_posthoc_test_comparison.csv").open(
            newline="", encoding="utf-8"
        ) as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 5)
        self.assertTrue(all(row["posthoc_diagnostic_only"] == "True" for row in rows))
        self.assertTrue(all(row["eligible_for_model_selection"] == "False" for row in rows))

    def test_integrity_and_reproduction_evidence_passes(self) -> None:
        report = json.loads((EVIDENCE / "phase_8b1_evaluation_integrity.json").read_text())
        self.assertEqual(report["hidden_target_reconstruction_mismatch_count"], 0)
        self.assertEqual(report["observed_target_overlap_count"], 0)
        self.assertTrue(report["model_artifact_hashes_match_phase8b_manifest"])
        self.assertTrue(report["prediction_reproduction"]["validation"]["reproduced"])
        self.assertTrue(report["prediction_reproduction"]["test"]["reproduced"])

    def test_original_phase8b_finding_is_preserved(self) -> None:
        result = json.loads((EVIDENCE / "phase_8b1_baseline_posthoc_test_results.json").read_text())
        primary = result["original_primary_finding_preserved"]
        self.assertAlmostEqual(primary["validation_ndcg@5"], 0.058074855380056536)
        self.assertAlmostEqual(primary["frozen_test_ndcg@5"], 0.02320118339585382)
        self.assertFalse(result["selection_changed"])
        self.assertFalse(result["models_refit"])


if __name__ == "__main__":
    unittest.main()
