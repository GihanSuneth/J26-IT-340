# Component 3 offline navigation dashboard

This directory contains the browser dashboard, its local Python HTTP server,
the adapter to Component 3's existing store-map and routing algorithms, and
standard-library adapter tests.

## Launch

From the repository root:

```bash
python3 -B -m component3.simulations.navigation_dashboard.dashboard
```

Open `http://127.0.0.1:8765/`. Stop the server with Ctrl-C. To use another
loopback port:

```bash
python3 -B -m component3.simulations.navigation_dashboard.dashboard \
  --port 8766
```

The server only permits `127.0.0.1` or `localhost`. The UI, map JSON, and route
API are bundled and served locally; no cloud service, external API, package
installation, or internet connection is required after the project is
available locally.

## Behavior and data

- The map is loaded from `component3/data/store_map/store_graph.json` and
  `component3/data/store_map/apriltag_layout.json`.
- Graph node coordinates and connections are the only source for the displayed
  24 m by 18 m geometry and planned path. The SVG preserves equal x/y scale.
- The selector offers the existing section access nodes B1–B6. The map has no
  product-to-location mappings, so selections are aisle/category destinations,
  not generated product IDs.
- The default selection is B1, B3, and B5. The existing Held-Karp optimizer
  orders selected stops; Dijkstra expands each leg. Checkout remains the final
  destination.
- Empty selection plans directly from entrance to checkout. Duplicate
  selections are stably deduplicated; invalid or unreachable destinations are
  reported instead of displaying a fabricated route.
- This is a static route-planning foundation. It does not simulate trolley
  movement, stream sensor data, or animate deviation-triggered reroutes.

## Dependencies and tests

The dashboard server and adapter use Python's standard library and the
Component 3 navigation modules. The browser UI uses bundled HTML, CSS,
JavaScript, and SVG; it does not load third-party assets. Streamlit and Plotly
were absent from the existing environment, and no packages were installed.

Run the adapter tests from the repository root:

```bash
python3 -B -m unittest -v \
  component3.simulations.navigation_dashboard.tests.test_adapter
```

The project venv can be used instead by replacing `python3` with
`component3/.venv/bin/python`.
