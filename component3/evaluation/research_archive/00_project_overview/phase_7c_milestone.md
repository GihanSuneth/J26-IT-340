# Phase 7C milestone record — shared adaptive-navigation foundation

1. **Milestone and date:** C3-P7C-FOUNDATION, 2026-10-15 (+05:30).
2. **Research question:** Can customer and research interfaces safely observe and
   control one deterministic navigation session without changing the validated
   routing algorithms or confusing camera observations with physical motion?
3. **Previous behavior:** The spatial simulator was server-scoped, but the API did
   not expose a session ID, state revision, command idempotency, or browser control
   ownership. One combined research-oriented interface served `/`.
4. **Limitation:** Multiple polling tabs could each send step requests. Session
   identity and the complete research state contract were implicit.
5. **Approach:** Wrap the existing simulator in an authoritative session that
   serializes actions, deduplicates command IDs, leases clock advancement to one
   browser identity, and exposes read-only snapshots. Add a separate customer UI.
6. **Algorithms/formulation:** Dijkstra and Held–Karp are reused unchanged. The
   discrete simulation clock is `t_(k+1) = t_k + n*0.25 s` for accepted step count
   `n`. A command ID has at-most-once application within the server process.
7. **Architecture/data flow:** Browser → validated session action → existing
   `SpatialNavigationSimulation` → Dijkstra/Held–Karp/localization/guidance → one
   server snapshot → both views.
8. **Implementation:** Added `shared_session.py`, session endpoints, session fields,
   observation history, a customer interface, and HTTP/browser contract tests.
9. **Environment:** macOS host; Python 3.14 project virtual environment; local
   standard-library HTTP server; synthetic map
   `comp3-synthetic-supermarket-demo-v1` schema 1.0.
10. **Test cases:** Pure reads, duplicate command delivery, competing browser step,
    existing spatial navigation, camera lifecycle mocks, UI contracts, Python/JS
    syntax, whitespace. Full results are in the linked JSON artifact.
11. **Baseline:** Pre-Phase-7C server-scoped simulator without explicit command
    ownership or idempotency.
12. **Metrics:** Test pass count/total; failed count; browser acceptance status;
    camera acceptance status. Navigation-accuracy metrics were not re-measured.
13. **Actual results:** Focused suite: 44/44 passed after localhost permission was
    granted. Final full-suite result: see
    `../03_integrated_system/phase_7c_test_results.json`.
14. **Failures/negative results:** Initial sandboxed focused run reported 10/44
    failures because binding an ephemeral localhost socket was denied; 34 non-HTTP
    tests passed. This is retained as an environment constraint, not counted as a
    navigation defect. Physical camera acceptance for this milestone is
    **NOT MEASURED**.
15. **Threats to validity:** Single-process in-memory session; browser identities
    are cooperative, not authenticated; controller release after a crashed tab is
    manual/server-lifetime bounded; synthetic geometry and motion; no physical
    trolley; deterministic fixtures do not estimate real-world accuracy.
16. **Reproducibility:** See `component3/docs/COMP3_CODEX_HANDOFF.md`.
17. **Git state:** Branch `Comp3_Arun`; starting HEAD
    `4cc31bc7d113088ee2e0234a313889671c485fd3`; dirty Phase 7B working tree was
    preserved; no commit or push performed.
18. **AI assistance:** OpenAI Codex assisted with Phase 7C inspection,
    implementation, tests, and documentation in this run. Historical assistant
    identity is recorded as UNKNOWN where not evidenced.
19. **Remaining limitations:** Free walk, off-route mapped-checkpoint acceptance,
    active-journey product changes, mid-edge exact route costs, persistent sessions,
    and recommendation training are not implemented.
20. **Next questions:** Does adaptive mapped-checkpoint correction reduce simulated
    localization error and completion cost versus the fixed-route baseline under a
    preregistered scenario set?

## Status separation

- **Implemented and verified:** shared in-memory session, pure reads, deterministic
  commands, controller lease, synchronized state, separate customer/research views.
- **Implemented but not physically evaluated:** real-camera integration inherited
  from Phase 7B; no new Phase 7C physical-camera run.
- **Designed but not implemented:** adaptive free walk, plausible off-route tag
  acceptance, partial-edge replanning, mid-journey list mutation.
- **Planned:** recommendation engine training/evaluation and integrated evaluation.
