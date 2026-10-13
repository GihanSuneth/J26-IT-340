# Component 3 research evidence

This directory maintains the reproducible evidence trail for Component 3:
recommendation, navigation, position tracking, AprilTag checkpoints, and the
optional CNN aisle classifier.

Deterministic navigation methods such as Dijkstra and Held-Karp are algorithms,
not trained machine-learning models. CNN aisle recognition is a separate,
optional trained model. Recommendation experiments use population-level POS
baskets and TF-IDF/KNN-based methods.

## Evidence phases

| Directory | Scope | Suggested evidence prefix |
| --- | --- | --- |
| `01_architecture/` | Architecture and component boundaries | `C3-ARCH` |
| `02_store_map/` | Store graph and map validation | `C3-MAP` |
| `03_apriltag_detection/` | Camera-based AprilTag detection | `C3-TAG` |
| `04_navigation_algorithms/` | Dijkstra, Held-Karp, and the offline navigation dashboard | `C3-NAV`, `C3-DASH` |
| `05_position_tracking/` | Encoder/IMU localization | `C3-POS` |
| `06_recommendation_engine/` | POS, TF-IDF, KNN, and fusion | `C3-REC` |
| `07_cnn_training/` | Optional aisle-classifier training | `C3-CNN` |
| `08_integration_testing/` | Component and system integration | `C3-INT` |
| `09_final_evaluation/` | Final metrics and report evidence | `C3-EVAL` |

## Reproducible evidence workflow

1. Run the test or experiment from a known Git commit. Record the exact command,
   configuration path, parameters, dataset version, and relevant environment
   details in the phase `notes.md`.
2. Save complete terminal logs under `component3/evaluation/logs/`. Save structured
   results under `component3/evaluation/test_results/` and computed metrics under
   `component3/evaluation/metrics/`. Result artifacts should record the commit hash
   and configuration used.
3. Capture a useful screenshot only after the result exists. Crop out unrelated
   material and verify that no credentials, personal data, or secrets appear.
4. Save the screenshot in the matching phase's `screenshots/` directory using a
   descriptive filename, for example `held_karp_known_graph_2026-10-13.png`.
5. Register the existing artifact in `evidence_index.csv`. From the repository
   root, the optional helper is:

   ```bash
   python component3/docs/research_evidence/tools/register_evidence.py \
     --evidence-id C3-NAV-001 \
     --date 2026-10-13 \
     --phase 04_navigation_algorithms \
     --title "Held-Karp known-graph test" \
     --description "Terminal capture and saved test output for a known graph" \
     --file-path component3/docs/research_evidence/04_navigation_algorithms/screenshots/held_karp_known_graph_2026-10-13.png \
     --related-code component3/backend/comp3_reco_navigation/navigation/held_karp.py \
     --test-result component3/evaluation/test_results/held_karp_known_graph.json \
     --capture-method "Manual screenshot after running the recorded command" \
     --status verified
   ```

   The helper refuses duplicate IDs and paths that do not exist. It never
   creates screenshots or test results.
6. Update the matching phase `notes.md` with the procedure, observed result,
   limitations, and evidence ID.
7. Add a dated entry to `progress_log.md`, linking the evidence ID and paths.
8. Validate the index and required structure:

   ```bash
   python component3/docs/research_evidence/tools/validate_evidence.py
   ```

## Manual screenshot fallback

If an automatic capture is unavailable, run the recorded command, open the
relevant terminal or application view, and use the operating system screenshot
tool to capture only the evidence-bearing area. Save it under the correct phase
directory and verify the file exists before indexing it. Until then, write the
planned filename in the phase notes as **Pending** and do not add an index row.

## Evidence rules

- Record only work, commands, outputs, and observations that were verified.
- Never invent screenshots, results, dates, metrics, or successful tests.
- Add an index row only after its `file_path` exists.
- Prefer machine-readable test output alongside human-readable screenshots.
- Keep raw datasets, credentials, personal data, and large model artifacts out
  of this documentation tree.
- Do not overwrite prior evidence. Use a new unique evidence ID and filename.
