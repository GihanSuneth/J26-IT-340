# Component 3 Demonstration Script

Run every command from the repository root. Both browser launchers bind only to `127.0.0.1`, use an existing `component3/.venv` when available, and set the customer suggestion gate to three distinct items.

## 1. Navigation sub-component

Start the synchronized customer and operator application:

```bash
component3/run/start_navigation_demo.sh
```

The launcher opens `http://127.0.0.1:8765/`. Use the **Operator Console** chip for technical checkpoint, route, camera and error diagnostics.

For the terminal algorithm segment, run the existing demonstrations:

```bash
component3/.venv/bin/python -B -m component3.backend.navigation.held_karp_demo
component3/.venv/bin/python -B -m component3.backend.navigation.dijkstra_demo
```

Ask the panel:

1. Is the turn-by-turn route and checkpoint feedback clear enough to follow without reading a floor plan?
2. Which navigation status or recovery message would you want made more prominent?

Leave this server running while starting the second sub-component in another terminal to demonstrate session independence.

## 2. Recommendation sub-component

Start the shared-session recommendation application:

```bash
component3/run/start_recommendation_demo.sh
```

The launcher opens `http://127.0.0.1:8766/recommendations`. Add at least three simulated confirmed products, inspect **Backend Analysis**, then accept or dismiss the one passive suggestion. Acceptance saves the suggestion to this standalone recommendation demo's local wishlist; it does not claim physical collection and does not alter the Navigation dashboard.

For the read-only terminal engine segment:

```bash
component3/.venv/bin/python -B -m component3.simulations.navigation_dashboard.reco_cli_demo --basket Bananas "Bread loaf" Pasta
```

This prints the frozen ranking, mapping eligibility, filter reasons, route detour, model version and checksum status. It does not train or write files.

Ask the panel:

1. Is the distinction between the experimental analysis ranking and the single customer suggestion understandable?
2. Does explicit accept/dismiss control feel appropriate before a suggestion is saved for later consideration?
