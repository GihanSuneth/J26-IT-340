# Phase 7E — dynamic shopping sessions and adaptive reoptimization

## Research question and baseline limitation

Can a server-authoritative shopping-session controller adapt an exact small-catalog
multi-destination route when intentions change during movement, while preserving
confirmed pickups, localization history and synchronized views?

Phase 7D represented requested and remaining products as product-ID tuples. That
preserved quantity-one behavior but could not express partial quantities, source,
shopping-list revision or auditable removal after pickup. The implementation plan and
baseline audit were recorded in `phase_7e_implementation_plan.md` before runtime edits.

## State formulation and invariants

Each line stores product ID, requested quantity `q`, collected quantity `c`, remaining
quantity `r=q-c`, source, and collection status. The session stores a monotonically
increasing shopping-list revision and append-only mutation history. It enforces
integer `q>0`, `0<=c<=q`; one explicit pickup increments `c` by one. Uncollected lines
may be removed. Lines with any confirmed pickup cannot be removed, and decreasing
remaining demand cannot reduce `q` below `c`. Only the six validated synthetic demo
products are accepted.

Legacy `selected_product_ids`, `remaining_products` and `collected_product_ids` remain
derived fields for Phase 7A–7D compatibility. Reset is an explicit new-run event;
requested quantities are retained and confirmed quantities reset audibly rather than
through an incidental navigation transition.

## Transaction and concurrency design

The dashboard's existing re-entrant lock serializes commands and camera callbacks.
The shared session deduplicates command IDs before dispatch. Live shopping mutations
must also match the current shopping-list revision. A proposed mutation is validated,
its unique remaining pickup nodes are routed, and only then is it committed. Invalid
IDs, quantities, stale revisions, recommendation reuse, or unreachable routes leave
shopping, localization, route and history unchanged. Read-only GET polling remains
side-effect free.

Camera callbacks therefore occur entirely before or after a route mutation, never
inside a partially committed state. A pickup uses the same list revision rule and is
still permitted only after the established estimate-only stable-arrival guard.
AprilTag recognition never implies collection.

## Route optimization formulation

For a route anchor `a`, remaining unique pickup nodes `D`, and checkout `t`, the
existing anchored planner computes:

`min_e partial(a,e) + HeldKarp(e,D,t)`.

When the shopper is moving, only the forward endpoint is allowed; when stopped, both
endpoints are candidates. Dijkstra supplies exact shortest graph legs. Multiple units
and products at one shelf produce one destination until every required unit at that
node is collected. Checkout remains final. This is exact for the small set of unique
demo stops under the static graph-distance model, not for general large or
time-dependent routing.

Adding a product after checkout reopens the completed session at the checkout anchor,
retains pickups/history, recalculates the route, and waits in a ready state. A route
failure rejects the mutation atomically.

## Independent shelf visit and recommendations

A free-walking shopper can select a product at the current shelf. Two stable
estimate/uncertainty samples must pass the existing arrival monitor before the UI
offers explicit pickup confirmation. After pickup, free walk remains stopped until a
new lane or planned navigation is requested.

The recommendation contract contains recommendation ID, product ID, source,
nullable model/version, nullable score, explanation and acceptance status. The single
integration suggestion is explicitly labeled demonstrative with null model and score.
It is inert until customer acceptance; acceptance enters the same validated mutation
and reoptimization path. No recommendation model was trained.

## Evaluation and measured results

The seed-6042 deterministic evaluation uses 0.25 s steps and 1.6 m/s virtual speed.
The fixed three-product run completed 3/3 pickup units and checkout over 38.0 m, with
three route revisions from pickups. The dynamic run performed add, remove, increase
and decrease operations, then completed 3/3 final units and checkout over 38.0 m with
shopping revision 7 and route revision 8.

The valid equal-demand comparison used the same three final pickup nodes, checkout,
graph and forward-constrained mid-edge anchor. Naive requested order and Held–Karp
both cost 37.715 m: the proposed optimizer improved cost by 0.0 m in this case. This
negative result is retained. Fixed and dynamic whole journeys reflect different
intention timing and are not presented as a controlled efficiency comparison.

Thirty repeated in-process reoptimizations measured 0.118–0.137 ms, median 0.119 ms,
and nearest-rank p95 0.135 ms in the recorded run. These are host-local software
timings, not physical response measurements.

The independent-shelf scenario started with CP200 confirmed, free-walked to `N1_1`,
passed the estimate-only arrival guard, explicitly confirmed one pickup, added a
second product, and resumed navigation from the latest estimate. The stale negative
case was rejected with shopping and route state unchanged. A separate free-walk case
accepted plausible CP202 while CP201 was expected, preserved shopping state and truth,
corrected the estimate, and replanned the route.

## Browser and failure evidence

Three local Chromium views exercised two customer editors and one research observer.
Three unique mutations produced shopping and route revision 3. A duplicated command
returned the stored result without reapplication; a stale edit returned HTTP 409;
refresh preserved identity and revision. Console and page errors were both zero.

Invalid product IDs, nonpositive quantities, collection overflow, removal after
collection, and stale revisions are covered by focused tests. No unreachable node
exists in the validated connected demo catalog; the atomic failure path is retained
and exercised through unit-level validation rather than a fabricated map mutation.

## Threats to validity

The catalog, movement, sensor drift, intentions and ground truth are synthetic. The
catalog has six products at distinct shelves, so shared-shelf behavior is tested by
the unique-node formulation but not measured on a natural shared-shelf fixture. The
timing distribution repeats one small problem on one host. No usability study,
inventory integration, physical camera trial, physical trolley trial, recommendation
training, or large-catalog scalability experiment occurred.

## Reproducibility and provenance

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.phase7e_evaluation
python3 -B -m component3.simulations.navigation_dashboard.phase7e_browser_acceptance
component3/.venv/bin/python -m pytest -q component3/backend/comp3_reco_navigation/tests component3/simulations/navigation_dashboard/tests
python3 -B component3/data/store_map/validate_store_map.py
python3 -B component3/docs/research_evidence/tools/validate_evidence.py
python3 -m compileall -q component3/backend/comp3_reco_navigation component3/simulations/navigation_dashboard
node --check component3/simulations/navigation_dashboard/static/app.js
node --check component3/simulations/navigation_dashboard/static/spatial.js
node --check component3/simulations/navigation_dashboard/static/customer.js
git diff --check -- component3
```

OpenAI Codex implemented Phase 7E under the user-specified scope. Work began and ended
on `Comp3_Arun` at HEAD `4cc31bc7d113088ee2e0234a313889671c485fd3`, preserving the
dirty Phase 7B–7D tree. No commit, push, map edit, POS-data edit, CNN change,
recommendation training, or store-layout editor was performed.
