# Phase 7F complete-journey acceptance

**Evidence class:** deterministic synthetic software execution plus separately
recorded local Chromium acceptance. No physical trolley or camera result is claimed.

The canonical runner completed five scenario groups. Planned shopping collected two
of two requested units and reached checkout. Independent free walk reached `N1_1`,
then add, increase, two explicit pickup confirmations, remove, labeled demonstration
recommendation acceptance, current-location resume, remaining pickup, and checkout
completed with four of four final units. The recommendation score and model version
remain null. A graph-valid wrong turn completed with two reroutes. A simulated camera
stop/reconnect resumed and completed after explicitly supplied mapped gate events.
An unexpected but plausible CP202 observation was accepted while CP201 was expected,
left truth unchanged, preserved history, and incremented the route revision.

All recorded ground-truth samples lay on validated graph edges, so the evaluated
journeys did not cross shelf footprints or make impossible virtual jumps. Product
collection occurred only through explicit confirmation (except pre-existing guided
demo automation, tested separately and labeled as simulated). Checkout completion was
observed only after remaining demand reached zero. The independent free-walk scenario
resumed from `N1_1`, not the entrance. Quantity totals and append-only shopping events
survived every route revision.

Browser behavior is assessed by rerunning the Phase 7B.2, 7C, 7D, and 7E Chromium
acceptance scripts. Phase 7B.2 covers three viewports plus manual, guided and
camera-gate modes. Phase 7E opens two customer tabs plus Research Execution, applies
three unique mutations, checks one duplicate is applied once, rejects a stale command
with HTTP 409, and verifies refresh/session preservation. Browser evidence is separate
from the synthetic journey metrics.

Detailed fields are in `phase_7f_raw_results.json` under
`complete_journey_trials`. This report does not infer physical movement from browser
or synthetic state.
