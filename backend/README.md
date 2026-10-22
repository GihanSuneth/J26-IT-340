# Backend services

The root backend contains the shared gateway boundary and the Component 1, 2,
and 4 Python packages. Component 3 is intentionally isolated under
`component3/backend/comp3_reco_navigation/` with its research dashboard under
`component3/simulations/navigation_dashboard/`.

## Packages

| Package | Responsibility |
| --- | --- |
| `gateway/` | Intended shared API routing, CORS, health, and startup boundary |
| `comp1_trigger_validation/` | Weight/camera trigger and item validation |
| `comp2_recognition_tracking/` | Product recognition and live-cart tracking |
| `comp4_pattern_billing/` | Purchase patterns, billing, and mobile synchronization |
| `../component3/backend/comp3_reco_navigation/` | Recommendation, route planning, localisation, and AprilTag processing |

The root gateway and several Component 1, 2, and 4 modules are currently
research scaffolds. Their module boundaries, tests, and training code are
preserved, but this repository does not claim a runnable combined gateway or
container deployment. The obsolete empty Docker definitions were removed.

## Development rules

- A component may use `shared/` contracts and helpers but must not import another
  component's internal modules.
- Cross-component messages must conform to `shared/contracts/events.schema.json`.
- Training notebooks and model code remain component-owned.
- Hardware-dependent code must degrade to a skip or explicit pending result when
  the required device is unavailable.

## Tests

Use the preserved Component 3 environment from the repository root:

```bash
# Root backend packages, Component 3 backend, and contract tests
component3/.venv/bin/python -m pytest -p no:cacheprovider \
  backend component3/backend tests/contract -q

# Complete Component 3 backend and dashboard regressions
component3/.venv/bin/python -m pytest -p no:cacheprovider \
  component3/backend/comp3_reco_navigation/tests \
  component3/simulations/navigation_dashboard/tests -q
```

The active Component 3 dashboard entry point is:

```bash
component3/run/start_dashboard.sh
```

See `component3/README.md` for recommendation experiments, frozen-model policy,
datasets, map validation, camera checks, and research-evidence commands.
