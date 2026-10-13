// Client-side selection and rendering for the offline navigation dashboard.
"use strict";

const state = {
  map: null,
  selected: new Set(),
  route: null,
  requestInProgress: false,
};

const elements = {
  destinationList: document.getElementById("destination-list"),
  mapContainer: document.getElementById("map-container"),
  mapSize: document.getElementById("map-size"),
  routeStatus: document.getElementById("route-status"),
  routeDistance: document.getElementById("route-distance"),
  visitOrder: document.getElementById("visit-order"),
  routePath: document.getElementById("route-path"),
  checkoutNode: document.getElementById("checkout-node"),
  mappingNotice: document.getElementById("mapping-notice"),
  calculateButton: document.getElementById("calculate-button"),
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

function selectedIds() {
  return Array.from(state.selected);
}

function renderDestinations() {
  elements.destinationList.innerHTML = state.map.destinations.map((destination) => {
    const checked = state.selected.has(destination.node_id) ? " checked" : "";
    return `<label class="destination-option">
      <input type="checkbox" value="${escapeHtml(destination.node_id)}"${checked}>
      <span class="destination-copy">
        <strong>${escapeHtml(destination.section_name)}</strong>
        <small>${escapeHtml(destination.node_id)} · ${escapeHtml(destination.node_name)}</small>
      </span>
    </label>`;
  }).join("");
  elements.destinationList.querySelectorAll("input").forEach((input) => {
    input.addEventListener("change", () => {
      if (input.checked) state.selected.add(input.value);
      else state.selected.delete(input.value);
      state.route = null;
      renderSummary();
      renderMap();
      elements.routeStatus.textContent = "Selection updated. Calculate the route to refresh the result.";
      elements.routeStatus.classList.remove("error");
    });
  });
}

function svgElement(name, attributes = {}, text = "") {
  const element = document.createElementNS("http://www.w3.org/2000/svg", name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  if (text) element.textContent = text;
  return element;
}

function renderMap() {
  const { width, height } = state.map.dimensions_m;
  const svg = svgElement("svg", {
    class: "map-svg",
    viewBox: `-0.8 -0.8 ${width + 1.6} ${height + 1.6}`,
    preserveAspectRatio: "xMidYMid meet",
    role: "img",
    "aria-label": "Store graph, mapped aisle destinations, checkpoints, and planned route",
  });
  svg.append(svgElement("rect", {
    class: "boundary",
    x: 0,
    y: 0,
    width,
    height,
    rx: 0.12,
  }));

  state.map.edges.forEach((edge) => {
    const start = state.map.nodes.find((node) => node.node_id === edge.source);
    const end = state.map.nodes.find((node) => node.node_id === edge.target);
    svg.append(svgElement("line", {
      class: "edge",
      x1: start.x_m,
      y1: height - start.y_m,
      x2: end.x_m,
      y2: height - end.y_m,
    }));
  });

  if (state.route) {
    const byId = new Map(state.map.nodes.map((node) => [node.node_id, node]));
    for (let index = 0; index < state.route.route_node_ids.length - 1; index += 1) {
      const start = byId.get(state.route.route_node_ids[index]);
      const end = byId.get(state.route.route_node_ids[index + 1]);
      svg.append(svgElement("line", {
        class: "route-edge",
        x1: start.x_m,
        y1: height - start.y_m,
        x2: end.x_m,
        y2: height - end.y_m,
      }));
    }
  }

  state.map.sections.forEach((section) => {
    const node = state.map.nodes.find((item) => item.node_id === section.node_id);
    const label = svgElement("text", {
      class: "section-label",
      x: node.x_m,
      y: height - node.y_m - 0.48,
      "aria-label": `${section.section_name}, ${section.section_id}`,
    }, section.section_name);
    svg.append(label);
  });

  state.map.tags.forEach((tag) => {
    const y = height - tag.y_m;
    svg.append(svgElement("rect", {
      class: "tag-mark",
      x: tag.x_m - 0.19,
      y: y - 0.19,
      width: 0.38,
      height: 0.38,
      rx: 0.06,
    }));
    svg.append(svgElement("text", {
      class: "tag-label",
      x: tag.x_m,
      y,
    }, String(tag.tag_id)));
  });

  state.map.nodes.forEach((node) => {
    const selected = state.selected.has(node.node_id);
    const className = selected
      ? "node-circle node-selected"
      : `node-circle node-${node.node_type}`;
    const y = height - node.y_m;
    svg.append(svgElement("circle", {
      class: className,
      cx: node.x_m,
      cy: y,
      r: selected ? 0.22 : 0.14,
    }));
    if (["entrance", "checkout"].includes(node.node_type) || selected) {
      svg.append(svgElement("text", {
        class: "node-label",
        x: node.x_m + 0.22,
        y: y - 0.18,
      }, node.node_id));
    }
  });

  elements.mapContainer.replaceChildren(svg);
  elements.mapSize.textContent = `${width} m × ${height} m · equal x/y scale`;
}

function renderSummary() {
  if (!state.route) {
    elements.routeDistance.innerHTML = `— <small>m</small>`;
    elements.visitOrder.innerHTML = '<li class="empty-list">Calculate a route to see the visit order.</li>';
    elements.routePath.textContent = "—";
    return;
  }
  elements.routeDistance.innerHTML = `${state.route.total_distance_m.toFixed(2)} <small>m</small>`;
  if (state.route.optimized_visit_order.length === 0) {
    elements.visitOrder.innerHTML = '<li class="empty-list">No shopping stops selected.</li>';
  } else {
    const names = new Map(state.map.destinations.map((item) => [item.node_id, item.section_name]));
    elements.visitOrder.innerHTML = state.route.optimized_visit_order.map((nodeId) =>
      `<li><span>${escapeHtml(names.get(nodeId) || nodeId)} <small>(${escapeHtml(nodeId)})</small></span></li>`
    ).join("");
  }
  elements.routePath.textContent = state.route.route_node_ids.join("  →  ");
}

async function calculateRoute() {
  if (state.requestInProgress) return;
  state.requestInProgress = true;
  elements.calculateButton.disabled = true;
  elements.routeStatus.textContent = "Calculating with Held-Karp and Dijkstra…";
  elements.routeStatus.classList.remove("error");
  try {
    const response = await fetch("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_destination_ids: selectedIds() }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Route calculation failed.");
    state.route = result;
    renderSummary();
    renderMap();
    elements.routeStatus.textContent = "Route calculated from the mapped graph.";
  } catch (error) {
    state.route = null;
    renderSummary();
    renderMap();
    elements.routeStatus.textContent = error.message;
    elements.routeStatus.classList.add("error");
  } finally {
    state.requestInProgress = false;
    elements.calculateButton.disabled = false;
  }
}

function updateSelectionNotice() {
  if (state.map.product_location_count === 0) {
    elements.mappingNotice.textContent =
      "The store map has no product-to-location mappings. Select mapped aisle/category access nodes instead.";
    elements.mappingNotice.classList.remove("hidden");
  }
}

async function initializeDashboard() {
  try {
    const response = await fetch("/api/map");
    if (!response.ok) throw new Error("Could not load Component 3 store-map data.");
    state.map = await response.json();
    state.selected = new Set(state.map.default_destination_ids);
    elements.checkoutNode.textContent = state.map.checkout_node_id;
    updateSelectionNotice();
    renderDestinations();
    renderSummary();
    renderMap();
    await calculateRoute();
  } catch (error) {
    elements.routeStatus.textContent = error.message;
    elements.routeStatus.classList.add("error");
    elements.destinationList.innerHTML = "";
    elements.mapContainer.textContent = "Store-map data could not be loaded.";
  }
}

document.getElementById("calculate-button").addEventListener("click", calculateRoute);
document.getElementById("clear-button").addEventListener("click", () => {
  state.selected.clear();
  state.route = null;
  renderDestinations();
  renderSummary();
  renderMap();
  elements.routeStatus.textContent = "Selection cleared. An empty route goes directly to checkout.";
  elements.routeStatus.classList.remove("error");
});
document.getElementById("reset-button").addEventListener("click", async () => {
  if (!state.map) return;
  state.selected = new Set(state.map.default_destination_ids);
  state.route = null;
  renderDestinations();
  renderSummary();
  renderMap();
  elements.routeStatus.textContent = "Demonstration reset to the deterministic default scenario.";
  elements.routeStatus.classList.remove("error");
  await calculateRoute();
});

initializeDashboard();
