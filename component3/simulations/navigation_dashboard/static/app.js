// Render the offline navigation simulator and send fixed-step local controls.
"use strict";

const state = {
  map: null,
  simulation: null,
  selected: new Set(),
  busy: false,
  playbackRate: 1,
  pollBusy: false,
  connectionLost: false,
};

const element = (id) => document.getElementById(id);
const dom = {
  destinationList: element("destination-list"),
  mapContainer: element("map-container"),
  mapSize: element("map-size"),
  status: element("route-status"),
  distance: element("route-distance"),
  visitOrder: element("visit-order"),
  routePath: element("route-path"),
  mappingNotice: element("mapping-notice"),
  eventLog: element("event-log"),
  statusPill: element("status-pill"),
};

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function svgElement(name, attributes = {}, text = "") {
  const svgNode = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => svgNode.setAttribute(key, value));
  if (text) svgNode.textContent = text;
  return svgNode;
}

function showStatus(message, error = false) {
  dom.status.textContent = message;
  dom.status.classList.toggle("error", error);
}

async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (error) {
    state.connectionLost = true;
    throw new Error(
      `Cannot reach the local simulator at ${window.location.origin}. ` +
      "Start it with `python3 -B -m component3.simulations.navigation_dashboard.dashboard`, " +
      `and this page will reconnect automatically. The server may have stopped. Details: ${error.message || "network connection failed"}`
    );
  }
  let result;
  try {
    result = await response.json();
  } catch (error) {
    state.connectionLost = true;
    throw new Error(
      `The local simulator returned an unreadable response (HTTP ${response.status}). ` +
      `Check the server log. Details: ${error.message}`
    );
  }
  if (!response.ok) {
    state.connectionLost = response.status >= 500;
    throw new Error(result.error || `Local simulator request failed (HTTP ${response.status}).`);
  }
  state.connectionLost = false;
  return result;
}

async function postControl(action, values = {}) {
  const result = await requestJson("/api/simulation/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action, ...values }),
  });
  state.simulation = result;
  renderSimulation();
  return result;
}

function renderDestinations() {
  dom.destinationList.innerHTML = state.map.destinations.map((destination) => {
    const checked = state.selected.has(destination.node_id) ? " checked" : "";
    return `<label class="destination-option">
      <input type="checkbox" value="${escapeHtml(destination.node_id)}"${checked}>
      <span class="destination-copy">
        <strong>${escapeHtml(destination.section_name)}</strong>
        <small>${escapeHtml(destination.node_id)} · ${escapeHtml(destination.node_name)}</small>
      </span>
    </label>`;
  }).join("");
  dom.destinationList.querySelectorAll("input").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) state.selected.add(input.value);
      else state.selected.delete(input.value);
      showStatus("Selection changed. Apply selections and plan before starting.");
    });
  });
}

function appendPolyline(svg, points, className, height) {
  if (!Array.isArray(points) || points.length < 2) return;
  const coordinates = points.map((point) =>
    `${point.x_m},${height - point.y_m}`
  ).join(" ");
  svg.append(svgElement("polyline", { class: className, points: coordinates }));
}

function renderMap() {
  if (!state.map) return;
  const { width, height } = state.map.dimensions_m;
  const sim = state.simulation;
  const svg = svgElement("svg", {
    class: "map-svg",
    viewBox: `-0.8 -0.8 ${width + 1.6} ${height + 1.6}`,
    preserveAspectRatio: "xMidYMid meet",
    role: "img",
    "aria-label": "Mapped store graph with planned route and separate trolley truth and estimate",
  });
  const byId = new Map(state.map.nodes.map((node) => [node.node_id, node]));
  svg.append(svgElement("rect", {
    class: "boundary", x: 0, y: 0, width, height, rx: 0.12,
  }));
  state.map.edges.forEach((edge) => {
    const start = byId.get(edge.source);
    const end = byId.get(edge.target);
    svg.append(svgElement("line", {
      class: "edge",
      x1: start.x_m,
      y1: height - start.y_m,
      x2: end.x_m,
      y2: height - end.y_m,
    }));
  });

  const route = sim ? sim.planned_route : [];
  for (let index = 0; index < route.length - 1; index += 1) {
    const start = byId.get(route[index]);
    const end = byId.get(route[index + 1]);
    if (!start || !end) continue;
    svg.append(svgElement("line", {
      class: "route-edge",
      x1: start.x_m,
      y1: height - start.y_m,
      x2: end.x_m,
      y2: height - end.y_m,
    }));
  }

  state.map.sections.forEach((section) => {
    const node = byId.get(section.node_id);
    svg.append(svgElement("text", {
      class: "section-label",
      x: node.x_m,
      y: height - node.y_m - 0.48,
    }, section.section_name));
  });
  state.map.tags.forEach((tag) => {
    const y = height - tag.y_m;
    svg.append(svgElement("rect", {
      class: "tag-mark", x: tag.x_m - 0.19, y: y - 0.19,
      width: 0.38, height: 0.38, rx: 0.06,
    }));
    svg.append(svgElement("text", {
      class: "tag-label", x: tag.x_m, y,
    }, String(tag.tag_id)));
  });
  const visited = new Set(sim ? sim.visited_destinations : []);
  state.map.nodes.forEach((node) => {
    const selected = state.selected.has(node.node_id);
    const completed = visited.has(node.node_id);
    const className = completed ? "node-circle node-completed" : selected
      ? "node-circle node-selected"
      : `node-circle node-${node.node_type}`;
    const y = height - node.y_m;
    svg.append(svgElement("circle", {
      class: className,
      cx: node.x_m,
      cy: y,
      r: selected || completed ? 0.22 : 0.14,
    }));
    if (["entrance", "checkout"].includes(node.node_type) || selected || completed) {
      svg.append(svgElement("text", {
        class: "node-label", x: node.x_m + 0.22, y: y - 0.18,
      }, node.node_id));
    }
  });

  if (sim) {
    appendPolyline(svg, sim.trajectory_ground_truth, "truth-trail", height);
    appendPolyline(svg, sim.trajectory_estimated, "estimate-trail", height);
    (sim.checkpoint_events || []).forEach((checkpoint) => {
      const node = byId.get(checkpoint.node_id);
      if (node) svg.append(svgElement("circle", {
        class: "correction-ring",
        cx: node.x_m,
        cy: height - node.y_m,
        r: 0.38,
      }));
    });
    const truth = sim.ground_truth;
    const estimate = sim.estimate;
    svg.append(svgElement("line", {
      class: "position-error-line",
      x1: truth.x_m,
      y1: height - truth.y_m,
      x2: estimate.x_m,
      y2: height - estimate.y_m,
    }));
    svg.append(svgElement("circle", {
      class: "truth-marker", cx: truth.x_m, cy: height - truth.y_m, r: 0.29,
    }));
    svg.append(svgElement("text", {
      class: "marker-label", x: truth.x_m + 0.35, y: height - truth.y_m + 0.1,
    }, "TRUE"));
    svg.append(svgElement("circle", {
      class: "estimate-marker",
      cx: estimate.x_m,
      cy: height - estimate.y_m,
      r: 0.22,
    }));
  }
  dom.mapContainer.replaceChildren(svg);
  dom.mapSize.textContent = `${width} m × ${height} m · equal x/y scale`;
}

function renderEvents(events) {
  const recent = (events || []).slice(-14).reverse();
  dom.eventLog.replaceChildren();
  if (recent.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No simulation events yet.";
    dom.eventLog.append(item);
    return;
  }
  recent.forEach((event) => {
    const item = document.createElement("li");
    const time = document.createElement("time");
    time.textContent = `${event.timestamp_s.toFixed(2)} s`;
    const message = document.createElement("span");
    message.textContent = event.message;
    item.append(time, message);
    dom.eventLog.append(item);
  });
}

function renderSimulation() {
  const sim = state.simulation;
  if (!state.map || !sim) return;
  const names = new Map(state.map.destinations.map((item) => [item.node_id, item.section_name]));
  element("time-value").textContent = `${sim.simulation_time_s.toFixed(2)} s`;
  element("location-value").textContent = sim.current_location;
  element("error-value").textContent = `${sim.position_error_m.toFixed(3)} m`;
  const deviation = sim.deviation;
  element("deviation-value").textContent = deviation
    ? `${deviation.distance_m.toFixed(2)} m · ${deviation.is_deviated ? "confirmed" :
      deviation.instantaneous_deviation ? `${deviation.consecutive_enter_samples}/3 samples` : "on route"}`
    : "—";
  element("heading-value").textContent =
    `${(sim.estimate.heading_rad * 180 / Math.PI).toFixed(1)}°`;
  element("remaining-value").textContent =
    sim.remaining_destinations.map((nodeId) => nodeId).join(" · ") || "None";
  element("remaining-distance-value").textContent =
    `${sim.remaining_distance_m.toFixed(2)} m`;
  const checkpoint = sim.last_checkpoint_correction;
  element("checkpoint-value").textContent = checkpoint
    ? `Tag ${checkpoint.tag_id} · ${checkpoint.node_id} · ${checkpoint.correction_m.toFixed(2)} m`
    : "None yet";
  element("reroute-value").textContent = String(sim.reroute_count);
  element("mean-error-value").textContent =
    `${sim.metrics.mean_position_error_m.toFixed(3)} m`;
  element("rmse-error-value").textContent =
    `${sim.metrics.rmse_position_error_m.toFixed(3)} m`;
  element("max-error-value").textContent =
    `${sim.metrics.max_position_error_m.toFixed(3)} m`;
  element("sample-count-value").textContent =
    String(sim.metrics.sample_count);
  element("checkpoint-count-value").textContent =
    String(sim.metrics.checkpoint_corrections);
  element("route-distance").innerHTML =
    `${sim.planned_distance_m.toFixed(2)} <small>m</small>`;
  dom.visitOrder.replaceChildren();
  const stops = [...sim.visited_destinations.map((id) => ({ id, done: true })),
    ...sim.remaining_destinations.map((id) => ({ id, done: false }))];
  if (!stops.length) {
    const empty = document.createElement("li");
    empty.className = "empty-list";
    empty.textContent = "No remaining shopping stops.";
    dom.visitOrder.append(empty);
  } else {
    stops.forEach((stop) => {
      const item = document.createElement("li");
      item.classList.toggle("stop-completed", stop.done);
      item.textContent = `${stop.done ? "✓ " : ""}${names.get(stop.id) || stop.id} (${stop.id})`;
      dom.visitOrder.append(item);
    });
  }
  dom.routePath.textContent = sim.planned_route.join("  →  ");
  dom.statusPill.lastChild.textContent = ` ${sim.status.replaceAll("_", " ")} · Offline`;
  dom.statusPill.classList.toggle("is-running", sim.running);
  renderEvents(sim.events);
  renderMap();

  element("start-button").disabled = sim.status !== "ready";
  element("guided-button").disabled = sim.status !== "ready";
  element("pause-button").disabled = !sim.can_pause;
  element("resume-button").disabled = sim.status !== "paused";
  element("step-button").disabled = !sim.can_step || state.busy;
  element("confirm-stop-button").disabled = !sim.can_confirm_stop;
  element("wrong-turn-button").disabled = !sim.can_trigger_wrong_turn;
  element("calculate-button").disabled = sim.status !== "ready" || state.busy;
}

async function applySelections() {
  try {
    const result = await postControl("set_destinations", {
      destinations: Array.from(state.selected),
    });
    showStatus(`Route planned from the mapped graph: ${result.planned_route.join(" → ")}`);
  } catch (error) {
    showStatus(error.message, true);
  }
}

async function execute(action, values = {}) {
  if (state.busy) return;
  state.busy = true;
  renderSimulation();
  try {
    await postControl(action, values);
    showStatus(`Simulation ${state.simulation.status.replaceAll("_", " ")}.`);
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    state.busy = false;
    renderSimulation();
  }
}

async function pollAndAdvance() {
  if (state.pollBusy) return;
  state.pollBusy = true;
  const wasDisconnected = state.connectionLost;
  try {
    if (state.connectionLost || !state.map || !state.simulation) {
      [state.map, state.simulation] = await Promise.all([
        requestJson("/api/map"),
        requestJson("/api/simulation"),
      ]);
      state.selected = new Set(state.simulation.remaining_destinations);
      renderDestinations();
      renderSimulation();
    } else if (state.simulation.running) {
      await postControl("step", { count: state.playbackRate });
    } else {
      state.simulation = await requestJson("/api/simulation");
      renderSimulation();
    }
    if (wasDisconnected) showStatus("Connection to the local simulator restored.");
  } catch (error) {
    showStatus(error.message, true);
  } finally {
    state.pollBusy = false;
  }
}

async function initialize() {
  try {
    const [mapData, simulationData] = await Promise.all([
      requestJson("/api/map"),
      requestJson("/api/simulation"),
    ]);
    state.map = mapData;
    state.simulation = simulationData;
    state.selected = new Set(state.simulation.remaining_destinations);
    if (state.map.product_location_count === 0) {
      dom.mappingNotice.textContent =
        "No product-to-location mappings exist. Select mapped aisle access nodes instead.";
      dom.mappingNotice.classList.remove("hidden");
    }
    renderDestinations();
    renderSimulation();
    showStatus("Actual store graph loaded; simulation is ready.");
  } catch (error) {
    showStatus(error.message, true);
    dom.mapContainer.textContent = "Store-map data could not be loaded.";
  }
}

element("calculate-button").addEventListener("click", applySelections);
element("guided-button").addEventListener("click", () => execute("guided_demo"));
element("start-button").addEventListener("click", () => execute("start"));
element("pause-button").addEventListener("click", () => execute("pause"));
element("resume-button").addEventListener("click", () => execute("resume"));
element("step-button").addEventListener("click", () => execute("step"));
element("reset-button").addEventListener("click", () => execute("reset"));
element("wrong-turn-button").addEventListener("click", () => execute("wrong_turn"));
element("confirm-stop-button").addEventListener("click", () => execute("confirm_stop"));
element("speed-control").addEventListener("input", (event) => {
  const speed = Number(event.target.value);
  element("speed-value").textContent = `${speed.toFixed(1)} m/s`;
  postControl("configure", { speed_m_s: speed }).catch((error) => showStatus(error.message, true));
});
element("playback-control").addEventListener("input", (event) => {
  state.playbackRate = Number(event.target.value);
  element("playback-value").textContent = `${state.playbackRate}×`;
});
element("noise-control").addEventListener("input", (event) => {
  const noise = Number(event.target.value) / 1000;
  element("noise-value").textContent = `${event.target.value} mm`;
  postControl("configure", {
    encoder_noise_std_m: noise,
    imu_yaw_noise_std_rad: noise * Math.PI / 180,
  }).catch((error) => showStatus(error.message, true));
});

initialize();
window.setInterval(pollAndAdvance, 200);
