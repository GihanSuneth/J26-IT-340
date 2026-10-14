// Render the synthetic store map and drive its local graph-navigation API.
"use strict";

const state = {
  map: null,
  sim: null,
  selected: new Set(),
  busy: false,
  pollBusy: false,
  connectionLost: false,
  playbackSteps: 1,
};
const byId = (id) => document.getElementById(id);

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    state.connectionLost = true;
    throw new Error(
      `Cannot reach the local simulator at ${window.location.origin}. ` +
      "Start it with `python3 -B -m component3.simulations.navigation_dashboard.dashboard`, " +
      "and this page will reconnect automatically. The server may have stopped. " +
      `Details: ${error.message || "network connection failed"}`
    );
  }
  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    state.connectionLost = true;
    throw new Error(
      `The local simulator returned an unreadable response (HTTP ${response.status}). ` +
      `Check the server log. Details: ${error.message}`
    );
  }
  if (!response.ok) {
    state.connectionLost = response.status >= 500;
    throw new Error(payload.error || `Local simulator request failed (HTTP ${response.status}).`);
  }
  state.connectionLost = false;
  return payload;
}

function showError(message) {
  const banner = byId("connection-error");
  banner.textContent = message;
  banner.hidden = false;
}

function showNotice(message) {
  byId("connection-error").textContent = message;
  byId("connection-error").hidden = !message;
}

function svgNode(name, attributes = {}, label = "") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  if (label) node.textContent = label;
  return node;
}

function renderProducts() {
  if (!state.map || !state.sim) return;
  const products = state.map.products;
  const form = byId("product-list");
  if (!form.childElementCount) {
    products.forEach((product) => {
      const label = document.createElement("label");
      label.className = "product-option";
      const input = document.createElement("input");
      input.type = "checkbox";
      input.value = product.demo_product_id;
      input.addEventListener("change", () => {
        if (input.checked) state.selected.add(input.value);
        else state.selected.delete(input.value);
      });
      const copy = document.createElement("span");
      const name = document.createElement("strong");
      name.textContent = product.name;
      const description = document.createElement("small");
      description.textContent =
        `${product.demo_product_id} · ${product.category} · ${product.shelf_id}`;
      copy.append(name, description);
      label.append(input, copy);
      form.append(label);
    });
  }
  form.querySelectorAll("input").forEach((input) => {
    input.checked = state.selected.has(input.value);
    input.disabled = state.sim.guided_demo.active ||
      !["ready", "complete"].includes(state.sim.status);
  });
}

function appendPath(svg, coordinates, className, height) {
  if (!Array.isArray(coordinates) || coordinates.length < 2) return;
  svg.append(svgNode("polyline", {
    class: className,
    points: coordinates.map((point) => `${point.x_m},${height - point.y_m}`).join(" "),
  }));
}

function renderMap() {
  if (!state.map || !state.sim) return;
  const { width, height } = state.map.boundary_m;
  const lanes = state.map.walkable_lanes;
  const half = lanes.width_m / 2;
  const svg = svgNode("svg", {
    viewBox: `-0.5 -0.5 ${width + 1} ${height + 1}`,
    preserveAspectRatio: "xMidYMid meet",
    role: "img",
    "aria-label": "Synthetic supermarket map with aisles, shelf obstacles, products, route, and trolley positions",
  });
  svg.append(svgNode("rect", {
    class: "boundary", x: 0, y: 0, width, height,
  }));
  lanes.horizontal_corridors.forEach((corridor) => {
    svg.append(svgNode("rect", {
      class: "lane-area",
      x: lanes.columns_x_m[0] - half,
      y: height - corridor.y_m - corridor.width_m / 2,
      width: lanes.columns_x_m.at(-1) - lanes.columns_x_m[0] + lanes.width_m,
      height: corridor.width_m,
    }));
  });
  lanes.cross_aisle_corridors.forEach((corridor) => {
    svg.append(svgNode("rect", {
      class: "lane-area",
      x: corridor.x_m - corridor.width_m / 2,
      y: height - lanes.rows_y_m.at(-1) - half,
      width: corridor.width_m,
      height: lanes.rows_y_m.at(-1) - lanes.rows_y_m[0] + lanes.width_m,
    }));
  });
  const nodeById = new Map(state.map.nodes.map((node) => [node.id, node]));
  state.map.shelves.forEach((shelf) => {
    const [left, bottom, right, top] = shelf.bounds_m;
    svg.append(svgNode("rect", {
      class: "shelf",
      x: left,
      y: height - top,
      width: right - left,
      height: top - bottom,
      rx: 0.08,
    }));
    svg.append(svgNode("text", {
      class: "shelf-label",
      x: (left + right) / 2,
      y: height - (bottom + top) / 2,
    }, shelf.shelf_id.replace("DEMO-SHELF-", "S")));
  });
  state.map.edges.forEach((edge) => {
    const start = nodeById.get(edge.source);
    const end = nodeById.get(edge.target);
    svg.append(svgNode("line", {
      class: "lane-center",
      x1: start.x_m,
      y1: height - start.y_m,
      x2: end.x_m,
      y2: height - end.y_m,
    }));
  });
  const route = state.sim.planned_route.map((id) => nodeById.get(id)).filter(Boolean);
  const previousRoute = (state.sim.previous_planned_route || [])
    .map((id) => nodeById.get(id)).filter(Boolean);
  appendPath(svg, previousRoute, "previous-route", height);
  appendPath(svg, route, "planned", height);
  appendPath(svg, state.sim.travelled_ground_truth, "truth-trail", height);
  appendPath(svg, state.sim.travelled_estimate, "estimate-trail", height);

  state.map.nodes.forEach((node) => {
    svg.append(svgNode("circle", {
      class: node.id === state.map.terminals.entrance_node_id ||
        node.id === state.map.terminals.checkout_node_id ? "terminal" : "intersection",
      cx: node.x_m, cy: height - node.y_m, r: 0.11,
    }));
  });
  state.map.checkpoints.forEach((checkpoint) => {
    const node = nodeById.get(checkpoint.node_id);
    const detected = state.sim.detected_checkpoint_ids.includes(checkpoint.checkpoint_id);
    svg.append(svgNode("rect", {
      class: detected ? "checkpoint detected" : "checkpoint",
      x: node.x_m - 0.18, y: height - node.y_m - 0.18,
      width: 0.36, height: 0.36, rx: 0.04,
    }));
    svg.append(svgNode("text", {
      class: "checkpoint-label", x: node.x_m + 0.22, y: height - node.y_m - 0.1,
    }, `CP${checkpoint.checkpoint_id}`));
  });
  state.map.products.forEach((product) => {
    const node = nodeById.get(product.pickup_node_id);
    svg.append(svgNode("circle", {
      class: state.sim.remaining_products.some(
        (remaining) => remaining.demo_product_id === product.demo_product_id
      ) ? "pickup" : "pickup collected",
      cx: node.x_m, cy: height - node.y_m, r: 0.2,
    }));
  });

  const truth = state.sim.ground_truth;
  const estimate = state.sim.estimate;
  svg.append(svgNode("line", {
    class: "error-line",
    x1: truth.x_m, y1: height - truth.y_m,
    x2: estimate.x_m, y2: height - estimate.y_m,
  }));
  svg.append(svgNode("circle", {
    class: "truth-marker", cx: truth.x_m, cy: height - truth.y_m, r: 0.25,
  }));
  svg.append(svgNode("circle", {
    class: "estimate-marker", cx: estimate.x_m, cy: height - estimate.y_m, r: 0.2,
  }));
  byId("map").replaceChildren(svg);
  byId("map-dimensions").textContent = `${width} m × ${height} m · metric scale`;
}

function appendItems(listId, items, emptyMessage) {
  const list = byId(listId);
  list.replaceChildren();
  if (!items.length) {
    const item = document.createElement("li");
    item.textContent = emptyMessage;
    list.append(item);
    return;
  }
  items.forEach((value) => {
    const item = document.createElement("li");
    item.textContent = value;
    list.append(item);
  });
}

function render() {
  if (!state.map || !state.sim) return;
  const sim = state.sim;
  const guide = sim.guidance;
  byId("instruction").textContent = guide.instruction;
  byId("maneuver-distance").textContent = `${guide.distance_to_maneuver_m.toFixed(1)} m`;
  byId("route-distance").textContent = `${sim.route_distance_m.toFixed(2)} m`;
  byId("planned-route").textContent = sim.planned_route.join(" → ");
  byId("position").textContent =
    `${sim.current_location} · ${sim.ground_truth.x_m.toFixed(2)}, ${sim.ground_truth.y_m.toFixed(2)} m`;
  byId("position-error").textContent = `${sim.position_error_m.toFixed(3)} m`;
  byId("aisle").textContent = sim.current_aisle || sim.active_product?.shelf_section || "Main aisle";
  byId("deviation").textContent = sim.deviation
    ? `${sim.deviation.distance_m.toFixed(2)} m · ${
      sim.deviation.is_deviated
        ? "confirmed"
        : sim.deviation.consecutive_enter_samples
          ? `confirming ${sim.deviation.consecutive_enter_samples}/3`
          : "monitoring"
    }`
    : "On route";
  byId("active-product").textContent = sim.active_product
    ? `${sim.active_product.name} (${sim.active_product.demo_product_id})`
    : "Checkout";
  byId("target-shelf").textContent = sim.active_product
    ? `${sim.active_product.shelf_id} · ${sim.active_product.shelf_section}`
    : "Checkout";
  byId("next-checkpoint").textContent = sim.next_checkpoint
    ? `${sim.next_checkpoint.name} · CP${sim.next_checkpoint.checkpoint_id}`
    : "No mapped checkpoint ahead";
  byId("checkpoint-distance").textContent = `${sim.distance_to_checkpoint_m.toFixed(1)} m`;
  byId("last-checkpoint").textContent = sim.last_confirmed_checkpoint
    ? `${sim.last_confirmed_checkpoint.node_id} · CP${sim.last_confirmed_checkpoint.checkpoint_id}`
    : "None";
  byId("correction").textContent = sim.last_confirmed_checkpoint
    ? `${sim.last_confirmed_checkpoint.correction_m.toFixed(3)} m (simulated)`
    : "None";
  byId("sim-time").textContent = `${sim.simulation_time_s.toFixed(2)} s`;
  byId("remaining-distance").textContent = `${sim.remaining_distance_m.toFixed(1)} m`;
  const guided = sim.guided_demo;
  const stageCard = byId("guided-stage-card");
  stageCard.hidden = !guided.active;
  byId("guided-stage").textContent =
    `Stage ${guided.stage}/${guided.stage_count} — ${guided.stage_title}`;
  const pickupNotice = byId("pickup-notice");
  const atGuidedPickup = guided.active && [4, 7].includes(guided.stage);
  pickupNotice.hidden = !atGuidedPickup;
  pickupNotice.textContent = atGuidedPickup && sim.active_product
    ? `Simulated pickup: ${sim.active_product.name} reached. Automatic guided-demo confirmation pending.`
    : "";
  const lastEvent = sim.events.at(-1);
  const eventIsCurrent = lastEvent &&
    sim.simulation_time_s - lastEvent.timestamp_s <= sim.fixed_timestep_s;
  byId("sim-status").textContent = sim.status === "ready"
    ? "ready"
    : sim.status === "complete"
      ? "Navigation complete"
    : eventIsCurrent && lastEvent.event_type === "reroute_success"
      ? "Rerouting"
      : sim.deviation?.is_deviated
        ? "Deviation confirmed"
        : sim.deviation?.consecutive_enter_samples
          ? "Deviation suspected"
          : eventIsCurrent && lastEvent.event_type === "checkpoint_detected"
            ? "Checkpoint corrected"
            : sim.status.replaceAll("_", " ");
  byId("reroutes").textContent = String(sim.reroute_count);
  byId("speed-value").textContent = `${Number(sim.speed_m_s || 0.8).toFixed(1)} m/s`;
  appendItems("collected", sim.collected_product_ids, "No products collected.");
  appendItems("remaining", sim.remaining_products.map(
    (product) => `${product.name} · ${product.shelf_id}`
  ), "All products collected.");
  const events = byId("events");
  events.replaceChildren();
  sim.events.forEach((event) => {
    const item = document.createElement("li");
    const time = document.createElement("strong");
    time.textContent = `${event.timestamp_s.toFixed(2)} s `;
    item.append(time, document.createTextNode(event.message));
    events.append(item);
  });
  events.scrollTop = events.scrollHeight;
  const completion = guided.completion_summary;
  byId("completion-summary").hidden = !completion;
  byId("completion-copy").textContent = completion
    ? `${completion.products_collected.length} products · checkpoints ${completion.checkpoint_sequence.join(" → ")} · ${completion.reroute_count} reroute · ${completion.simulation_time_s.toFixed(2)} s.`
    : "";
  byId("guided-demo").disabled = state.busy;
  byId("start").disabled = sim.status !== "ready" || guided.active;
  byId("pause").disabled = !sim.running;
  byId("resume").disabled = sim.status !== "paused";
  byId("step").disabled = !["navigating", "paused"].includes(sim.status) || state.busy;
  byId("wrong-turn").disabled = guided.active || sim.status !== "navigating" || sim.reroute_count > 0;
  byId("confirm-product").disabled = guided.active || sim.status !== "awaiting_product_confirmation";
  byId("apply-products").disabled = guided.active || !["ready", "complete"].includes(sim.status);
  byId("product-list").querySelectorAll("input").forEach((input) => {
    input.disabled = guided.active || !["ready", "complete"].includes(sim.status);
  });
  renderProducts();
  renderMap();
}

async function control(action, values = {}) {
  if (state.busy) return;
  state.busy = true;
  try {
    state.sim = await requestJson("/api/spatial/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...values }),
    });
    state.selected = new Set(state.sim.selected_product_ids);
    showNotice("");
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    state.busy = false;
    if (state.map && state.sim) render();
  }
}

async function poll() {
  if (state.pollBusy || (!state.connectionLost && (!state.sim || !state.sim.running))) return;
  state.pollBusy = true;
  try {
    if (state.connectionLost) {
      if (!state.map) {
        [state.map, state.sim] = await Promise.all([
          requestJson("/api/spatial/map"),
          requestJson("/api/spatial/state"),
        ]);
      } else {
        state.sim = await requestJson("/api/spatial/state");
      }
      state.selected = new Set(state.sim.selected_product_ids);
      showNotice("");
      render();
      return;
    }
    state.sim = await requestJson("/api/spatial/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "step", count: state.playbackSteps }),
    });
    showNotice("");
    render();
  } catch (error) {
    showError(error.message);
  } finally {
    state.pollBusy = false;
  }
}

async function initialize() {
  try {
    [state.map, state.sim] = await Promise.all([
      requestJson("/api/spatial/map"),
      requestJson("/api/spatial/state"),
    ]);
    state.selected = new Set(state.sim.selected_product_ids);
    render();
    showNotice("");
  } catch (error) {
    state.connectionLost = true;
    showError(error.message);
    byId("map").textContent = "The synthetic map could not be loaded.";
  }
}

byId("apply-products").addEventListener("click", () =>
  control("set_products", { product_ids: [...state.selected] })
);
byId("start").addEventListener("click", () => control("start"));
byId("guided-demo").addEventListener("click", () => control("guided_demo"));
byId("pause").addEventListener("click", () => control("pause"));
byId("resume").addEventListener("click", () => control("resume"));
byId("step").addEventListener("click", () => control("step"));
byId("reset").addEventListener("click", () => control("reset"));
byId("wrong-turn").addEventListener("click", () => control("wrong_turn"));
byId("confirm-product").addEventListener("click", () => control("confirm_product"));
byId("speed").addEventListener("input", (event) => {
  byId("speed-value").textContent = `${Number(event.target.value).toFixed(1)} m/s`;
});
byId("speed").addEventListener("change", (event) =>
  control("configure", { speed_m_s: Number(event.target.value) })
);
byId("playback").addEventListener("input", (event) => {
  state.playbackSteps = Number(event.target.value);
  byId("playback-value").textContent = `${state.playbackSteps}×`;
});
initialize();
window.setInterval(poll, 200);
