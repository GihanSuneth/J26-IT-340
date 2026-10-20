"use strict";

const ui = (id) => document.getElementById(id);
const svgNS = "http://www.w3.org/2000/svg";
const clientId = sessionStorage.getItem("comp3-customer-client-id") ||
  `customer-${crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)}`;
sessionStorage.setItem("comp3-customer-client-id", clientId);

let commandNumber = 0;
let map = null;
let session = null;
let selected = new Set();
let selectionDirty = false;
let busy = false;
let spokenVoiceKey = null;
let pendingVoice = null;
let voiceToken = 0;
let mapZoom = 1;
let voiceEnabled = false;
let showCheckpoints = false;
let lastCorrectionKey = null;
let correctionPulseUntil = 0;
let lastProductsRenderKey = null;
let lastRecommendationsRenderKey = null;

async function json(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function command(action, extra = {}) {
  commandNumber += 1;
  return {action, ...extra, client_id: clientId, command_id: `${clientId}:${commandNumber}`};
}

async function control(action, extra = {}) {
  if (busy) return false;
  busy = true;
  const shoppingAction = action.startsWith("shopping_") || action === "accept_recommendation";
  if (shoppingAction) {
    ui("shopping-update-status").textContent = "Updating list and recalculating route…";
    ui("shopping-update-status").dataset.tone = "pending";
  }
  try {
    session = await json("/api/session/control", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(command(action, extra)),
    });
    if (action === "set_products") selectionDirty = false;
    selected = new Set(session.selected_product_ids);
    ui("error").hidden = true;
    if (shoppingAction) {
      ui("shopping-update-status").textContent = `Saved · route revision ${session.route_revision}`;
      ui("shopping-update-status").dataset.tone = "saved";
    }
    render();
    return true;
  } catch (error) {
    ui("sync-status").textContent = "Sync lost";
    if (error.message.includes("Only controller")) {
      session = await json("/api/session/state");
      render();
    } else {
      ui("error").textContent = error.message;
      ui("error").hidden = false;
    }
    if (shoppingAction) {
      ui("shopping-update-status").textContent = `Not saved · ${error.message}`;
      ui("shopping-update-status").dataset.tone = "error";
    }
    return false;
  } finally {
    busy = false;
  }
}

function svgElement(tag, attributes = {}, text = null) {
  const element = document.createElementNS(svgNS, tag);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, value));
  if (text !== null) element.textContent = text;
  return element;
}

function nodeLookup() {
  return new Map((map?.nodes || []).map((node) => [node.id, node]));
}

function mapPoint(x, y) {
  return [Number(x), Number(map.boundary_m.height) - Number(y)];
}

function polylinePoints(nodeIds, nodes) {
  return nodeIds.map((id) => nodes.get(id)).filter(Boolean)
    .map((node) => mapPoint(node.x_m, node.y_m).join(",")).join(" ");
}

function renderMap() {
  if (!map || !session) return;
  const width = Number(map.boundary_m.width);
  const height = Number(map.boundary_m.height);
  const nodes = nodeLookup();
  const svg = svgElement("svg", {viewBox: `-0.5 -0.5 ${width + 1} ${height + 1}`, preserveAspectRatio: "xMidYMid meet", "aria-hidden": "true"});
  svg.style.transform = `scale(${mapZoom})`;
  svg.append(svgElement("rect", {class: "map-ground", x: 0, y: 0, width, height}));

  const lanes = svgElement("g");
  (map.edges || []).forEach((edge) => {
    const start = nodes.get(edge.source); const end = nodes.get(edge.target);
    if (!start || !end) return;
    const [x1, y1] = mapPoint(start.x_m, start.y_m); const [x2, y2] = mapPoint(end.x_m, end.y_m);
    lanes.append(svgElement("line", {class: "map-lane", x1, y1, x2, y2}));
    lanes.append(svgElement("line", {class: "map-lane-edge", x1, y1, x2, y2}));
  });
  svg.append(lanes);

  const activeShelf = session.active_product?.shelf_id;
  (map.shelves || []).forEach((shelf) => {
    const [left, bottom, right, top] = shelf.bounds_m;
    const y = height - top;
    svg.append(svgElement("rect", {
      class: `map-block${shelf.shelf_id === activeShelf ? " active" : ""}`,
      x: left, y, width: right - left, height: top - bottom, rx: .18,
    }));
    svg.append(svgElement("text", {class: "map-label", x: (left + right) / 2, y: y + (top - bottom) / 2 + .12}, shelf.section));
  });

  const travelled = session.travelled_estimate || [];
  if (travelled.length > 1) {
    const points = travelled.map((point) => mapPoint(point.x_m, point.y_m).join(",")).join(" ");
    svg.append(svgElement("polyline", {class: "travelled-line", points}));
  }
  const routePoints = polylinePoints(session.remaining_route || session.planned_route || [], nodes);
  if (routePoints) {
    svg.append(svgElement("polyline", {class: "route-shadow", points: routePoints}));
    svg.append(svgElement("polyline", {class: "route-line", points: routePoints}));
  }

  const activeNode = session.active_product?.pickup_node_id;
  (map.products || []).filter((product) => selected.has(product.demo_product_id)).forEach((product) => {
    const node = nodes.get(product.pickup_node_id); if (!node) return;
    const [x, y] = mapPoint(node.x_m, node.y_m);
    svg.append(svgElement("circle", {class: `pickup-marker${product.pickup_node_id === activeNode ? " active" : ""}`, cx: x, cy: y, r: .22}));
  });

  const verified = new Set(session.detected_checkpoint_ids || []);
  const expected = session.next_checkpoint?.checkpoint_id;
  (map.checkpoints || []).forEach((checkpoint) => {
    const node = nodes.get(checkpoint.node_id); if (!node) return;
    const [x, y] = mapPoint(node.x_m, node.y_m);
    const stateClass = verified.has(checkpoint.checkpoint_id) ? " verified" : checkpoint.checkpoint_id === expected ? " expected" : "";
    const group = svgElement("g", {class: `checkpoint-marker${stateClass}`});
    group.append(svgElement("circle", {class: "checkpoint-halo", cx: x, cy: y, r: .38}));
    group.append(svgElement("text", {x, y: y + .11}, String(checkpoint.checkpoint_id)));
    svg.append(group);
  });

  if (showCheckpoints) {
    const layout = (map.apriltag_layouts || [])[0];
    const lastId = session.localization_health?.last_accepted_checkpoint_id;
    const latestId = session.observed_checkpoint?.tag_id;
    const candidateIds = new Set((session.localization_health?.candidate_checkpoints || []).map((item) => item.checkpoint_id));
    (layout?.tags || []).forEach((tag) => {
      const [x, y] = mapPoint(tag.x_m, tag.y_m);
      const stateClass = Number(tag.tag_id) === lastId ? " confirmed" : Number(tag.tag_id) === latestId ? " observed" : candidateIds.has(Number(tag.tag_id)) ? " candidate" : "";
      const group = svgElement("g", {class: `dense-tag${stateClass}`});
      group.append(svgElement("circle", {cx: x, cy: y, r: .13}));
      group.append(svgElement("text", {x: x + .16, y: y - .12}, String(tag.tag_id)));
      group.append(svgElement("title", {}, `AprilTag ${tag.tag_id} · ${tag.purpose} · ${tag.anchor.type} anchor`));
      svg.append(group);
    });
  }

  const estimate = session.current_estimated_position || session.estimate;
  if (estimate) {
    const [x, y] = mapPoint(estimate.x_m, estimate.y_m);
    const heading = -(session.heading_deg || 0);
    const correction = session.localization_correction_event;
    const correctionKey = correction ? `${correction.checkpoint_id}:${correction.timestamp_s ?? session.state_revision}` : null;
    if (correctionKey && correctionKey !== lastCorrectionKey) {
      lastCorrectionKey = correctionKey;
      correctionPulseUntil = Date.now() + 2200;
    }
    const user = svgElement("g", {class: Date.now() < correctionPulseUntil ? "user-position corrected" : "user-position", transform: `translate(${x} ${y}) rotate(${heading})`});
    user.append(svgElement("circle", {class: "user-halo", cx: 0, cy: 0, r: .55}));
    user.append(svgElement("circle", {class: "user-dot", cx: 0, cy: 0, r: .3}));
    user.append(svgElement("path", {class: "user-arrow", d: "M .12 0 L -.1 -.12 L -.1 .12 Z"}));
    svg.append(user);
    svg.append(svgElement("text", {class: "you-are-here", x, y: y - .52}, "YOU ARE HERE"));
  }
  svg.append(svgElement("text", {class: "map-attribution", x: .35, y: height - .32}, "Indoor route · live estimated position"));
  ui("map").replaceChildren(svg);
}

function renderProducts() {
  if (!map || !session) return;
  const search = ui("catalog-search").value.trim().toLowerCase();
  const renderKey = [session.shopping_list_revision, session.status, search, [...selected].sort().join(",")].join("|");
  if (renderKey === lastProductsRenderKey) return;
  lastProductsRenderKey = renderKey;
  const products = map.products.filter((product) => !search || `${product.name} ${product.category} ${product.shelf_section}`.toLowerCase().includes(search));
  ui("products").replaceChildren();
  products.forEach((product) => {
    const label = document.createElement("label"); label.className = "product";
    const input = document.createElement("input"); input.type = "checkbox"; input.value = product.demo_product_id;
    input.checked = selected.has(input.value);
    const copy = document.createElement("span"); copy.className = "product-copy";
    const title = document.createElement("span"); title.className = "product-name-line";
    const strong = document.createElement("strong"); strong.textContent = product.name;
    const aisle = document.createElement("em"); aisle.textContent = product.shelf_section;
    const meta = document.createElement("small"); meta.className = "product-meta"; meta.textContent = `Bay ${product.shelf_bay} · shelf ${product.shelf_level}`;
    const line = session.shopping_session.items.find((item) => item.product_id === product.demo_product_id);
    const controls = document.createElement("span"); controls.className = "quantity-controls";
    const add = document.createElement("button"); add.type = "button"; add.textContent = line ? "+" : "Add";
    add.setAttribute("aria-label", line ? `Add one ${product.name}` : `Add ${product.name}`);
    add.addEventListener("click", (event) => { event.preventDefault(); control(line ? "shopping_increase" : "shopping_add", {product_id: product.demo_product_id, quantity: 1, expected_shopping_revision: session.shopping_list_revision}); });
    const decrease = document.createElement("button"); decrease.type = "button"; decrease.textContent = "−";
    decrease.disabled = !line || line.remaining_quantity < 1;
    decrease.setAttribute("aria-label", `Remove one ${product.name}`);
    decrease.addEventListener("click", (event) => { event.preventDefault(); control("shopping_decrease", {product_id: product.demo_product_id, quantity: 1, expected_shopping_revision: session.shopping_list_revision}); });
    const remove = document.createElement("button"); remove.type = "button"; remove.textContent = "Remove";
    remove.disabled = !line || line.collected_quantity > 0;
    remove.addEventListener("click", (event) => { event.preventDefault(); control("shopping_remove", {product_id: product.demo_product_id, quantity: 1, expected_shopping_revision: session.shopping_list_revision}); });
    controls.append(add, decrease, remove); title.append(strong, aisle); copy.append(title, meta, controls); label.append(input, copy); ui("products").append(label);
    input.addEventListener("change", async () => {
      const checked = input.checked;
      selectionDirty = true;
      checked ? selected.add(input.value) : selected.delete(input.value);
      ui("item-count").textContent = selected.size;
      input.disabled = true;
      const ok = await control(checked ? "shopping_add" : "shopping_remove", {
        product_id: input.value,
        quantity: 1,
        expected_shopping_revision: session.shopping_list_revision,
      });
      if (!ok) input.checked = !checked;
      selectionDirty = false;
    });
  });
  const editable = ["ready", "complete"].includes(session.status);
  ui("products").dataset.mode = editable ? "planning" : "live";
  ui("products").querySelectorAll("input").forEach((input) => { input.disabled = !editable; });
  ui("list-note").textContent = editable ? "Select products; confirmed changes replan the route automatically." : "Use the quantity controls to update the active route safely.";
}

function renderStops() {
  const items = session.shopping_session.items.filter((item) => item.remaining_quantity > 0);
  const route = session.remaining_route || [];
  items.sort((a, b) => {
    const aProduct = map.products.find((product) => product.demo_product_id === a.product_id);
    const bProduct = map.products.find((product) => product.demo_product_id === b.product_id);
    return route.indexOf(aProduct?.pickup_node_id) - route.indexOf(bProduct?.pickup_node_id);
  });
  ui("remaining-items").replaceChildren(...items.map((item, index) => {
    const product = map.products.find((candidate) => candidate.demo_product_id === item.product_id);
    const li = document.createElement("li"); li.className = `stop-item${item.product_id === session.active_product?.product_id ? " active" : ""}`;
    const number = document.createElement("span"); number.className = "stop-number"; number.textContent = index + 1;
    const copy = document.createElement("span"); copy.className = "stop-copy";
    const name = document.createElement("strong"); name.textContent = item.name;
    const location = document.createElement("small"); location.textContent = `${product?.shelf_section || "Mapped aisle"} · bay ${product?.shelf_bay || "—"} · shelf ${product?.shelf_level || "—"}`;
    const qty = document.createElement("span"); qty.className = "stop-qty"; qty.textContent = `×${item.remaining_quantity}`;
    copy.append(name, location); li.append(number, copy, qty); return li;
  }));
  const collected = session.shopping_session.items.filter((item) => item.collected_quantity > 0);
  ui("collected-items").replaceChildren(...collected.map((item) => { const li = document.createElement("li"); li.textContent = `${item.name} ×${item.collected_quantity}`; return li; }));
  ui("item-count").textContent = session.shopping_session.remaining_units;
  ui("route-summary").textContent = `${items.length} stops · ${session.remaining_distance_m.toFixed(1)} m`;
}

function checkpointAreaCopy(checkpoint) {
  if (checkpoint.checkpoint_id === 200) return "Entrance · route starts here";
  if (checkpoint.checkpoint_id === 201) return "Central cross-aisle · Pantry, Cereal and Frozen ahead";
  return "Checkout · journey complete";
}

function renderCheckpoints() {
  const verified = new Set(session.detected_checkpoint_ids || []);
  const expected = session.camera_evaluation?.gate?.checkpoint_id || session.next_checkpoint?.checkpoint_id;
  ui("checkpoint-timeline").replaceChildren(...map.checkpoints.map((checkpoint) => {
    const li = document.createElement("li");
    li.className = `checkpoint-step${verified.has(checkpoint.checkpoint_id) ? " verified" : checkpoint.checkpoint_id === expected ? " expected" : ""}`;
    const node = document.createElement("span"); node.className = "checkpoint-node"; node.textContent = "✓";
    const copy = document.createElement("span"); copy.className = "checkpoint-copy";
    const title = document.createElement("strong"); title.textContent = `CP${checkpoint.checkpoint_id} · ${checkpoint.name}`;
    const detail = document.createElement("small"); detail.textContent = verified.has(checkpoint.checkpoint_id) ? "Verified and passed" : checkpoint.checkpoint_id === expected ? `Expected now · ${checkpointAreaCopy(checkpoint)}` : checkpointAreaCopy(checkpoint);
    copy.append(title, detail); li.append(node, copy); return li;
  }));
  ui("checkpoint-count").textContent = `${verified.size} / ${map.checkpoints.length}`;
}

function guidanceIcon() {
  const text = `${session.guidance.instruction_type} ${session.guidance.maneuver || ""}`.toLowerCase();
  if (text.includes("left")) return "↰";
  if (text.includes("right")) return "↱";
  if (text.includes("u-turn")) return "↶";
  if (text.includes("arriv") || text.includes("pickup")) return "●";
  if (text.includes("complete") || text.includes("checkout")) return "✓";
  return "↑";
}

function renderCheckpointStatus() {
  const camera = session.camera_status || {};
  const observation = session.observed_checkpoint;
  const cameraActive = Boolean(camera.scanning);
  ui("scanner-dot").classList.toggle("active", cameraActive);
  if (session.camera_evaluation?.waiting_for_checkpoint) {
    ui("checkpoint-status").textContent = "Checking location…";
  } else if (cameraActive) {
    ui("checkpoint-status").textContent = "Location tracking on";
  } else if (session.last_verified_checkpoint) {
    ui("checkpoint-status").textContent = "Location confirmed";
  } else {
    ui("checkpoint-status").textContent = "Route ready";
  }
  const notice = ui("map-notice");
  if (observation && observation.accepted === false && !["checkpoint_gate_not_active", "duplicate_observation"].includes(observation.reason)) {
    const tag = observation.tag_id === undefined ? "Tag" : `CP${observation.tag_id}`;
    notice.textContent = `${tag} rejected · ${String(observation.reason).replaceAll("_", " ")}. Your position was not changed.`;
    notice.hidden = false;
  } else {
    notice.hidden = true;
  }
}

function setVoiceStatus(message, tone = "") {
  ui("voice-status").textContent = message;
  ui("voice-status").dataset.tone = tone;
  ui("voice-repeat").disabled = !voiceEnabled;
}

function voiceAnnouncement() {
  const event = session?.guidance;
  if (!event) return null;
  const type = String(event.instruction_type || "").toUpperCase();
  const distance = Number(event.distance_to_maneuver_m || 0);
  let words;
  if (session.status === "awaiting_product_confirmation" && session.active_product) {
    const product = session.active_product;
    words = `You have reached ${product.name}. It is in ${product.shelf_section}, bay ${product.shelf_bay}, shelf level ${product.shelf_level}. Tap picked up when it is in your cart.`;
  } else if (type.includes("LEFT")) {
    words = distance > 1 ? `In ${distance.toFixed(0)} meters, turn left.` : "Turn left now.";
  } else if (type.includes("RIGHT")) {
    words = distance > 1 ? `In ${distance.toFixed(0)} meters, turn right.` : "Turn right now.";
  } else if (session.status === "awaiting_checkpoint") {
    words = "Pause here while your location is checked.";
  } else if (session.status === "ready") {
    words = "Your shopping route is ready. Tap start to begin.";
  } else if (session.status === "complete") {
    words = "Shopping complete. Please proceed to checkout.";
  } else if (type.includes("STRAIGHT") || type.includes("CONTINUE")) {
    words = distance > 1 ? `Continue straight for ${distance.toFixed(0)} meters.` : "Continue straight.";
  } else {
    words = event.instruction;
  }
  const targetNode = event.target_node_id || event.target_node || "";
  const key = [session.route_revision, session.status, type, targetNode, session.active_product?.product_id || ""].join(":");
  return {key, words};
}

function playVoice(announcement, force = false) {
  if (!voiceEnabled || !announcement) return;
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
    voiceEnabled = false;
    ui("voice").checked = false;
    ui("voice-button").setAttribute("aria-pressed", "false");
    setVoiceStatus("Voice unavailable", "error");
    return;
  }
  if (speechSynthesis.speaking && !force) {
    pendingVoice = announcement;
    setVoiceStatus("Voice queued", "active");
    return;
  }
  const token = ++voiceToken;
  if (force && speechSynthesis.speaking) speechSynthesis.cancel();
  pendingVoice = null;
  const utterance = new SpeechSynthesisUtterance(announcement.words);
  utterance.rate = 0.95;
  utterance.volume = 1;
  utterance.onstart = () => { if (token === voiceToken) setVoiceStatus("Speaking…", "active"); };
  utterance.onend = () => {
    if (token !== voiceToken) return;
    setVoiceStatus("Voice on · synced", "active");
    const next = pendingVoice;
    pendingVoice = null;
    if (next && next.key !== announcement.key) playVoice(next);
  };
  utterance.onerror = (event) => {
    if (token === voiceToken && event.error !== "canceled") setVoiceStatus("Voice could not play", "error");
  };
  speechSynthesis.speak(utterance);
  spokenVoiceKey = announcement.key;
}

function speakGuidance(force = false) {
  const announcement = voiceAnnouncement();
  if (!announcement || (!force && announcement.key === spokenVoiceKey)) return;
  playVoice(announcement, force);
}

function renderRecommendations() {
  const container = ui("recommendations");
  const section = ui("recommendations-section");
  const diagnostics = session.recommendation_diagnostics || {};
  const suggestions = session.recommendations || [];
  const renderKey = JSON.stringify([
    session.shopping_list_revision, diagnostics.inference_ready, diagnostics.fallback_state,
    diagnostics.error, suggestions.map((item) => item.recommendation_id), busy,
  ]);
  if (renderKey === lastRecommendationsRenderKey) return;
  lastRecommendationsRenderKey = renderKey;
  section.hidden = false;
  if (!diagnostics.inference_ready) {
    const message = document.createElement("p");
    message.className = "recommendation-neutral";
    message.textContent = "Experimental suggestions are unavailable. Navigation is not affected.";
    container.replaceChildren(message);
    return;
  }
  if (suggestions.length === 0) {
    const message = document.createElement("p");
    message.className = "recommendation-neutral";
    message.textContent = diagnostics.customer_message || "No eligible suggestion right now.";
    container.replaceChildren(message);
    return;
  }
  container.replaceChildren(...suggestions.map((suggestion) => {
    const item = document.createElement("div");
    item.className = "recommendation-item";
    const copy = document.createElement("span");
    const detour = suggestion.route_detour_cost_m == null
      ? "" : ` · +${Number(suggestion.route_detour_cost_m).toFixed(1)} m route`;
    copy.textContent = `${suggestion.product_name} · ${suggestion.shelf_section}, shelf ${suggestion.shelf_id}${detour}`;
    const actions = document.createElement("span");
    const accept = document.createElement("button");
    accept.type = "button";
    accept.className = "button primary";
    accept.textContent = suggestion.acceptance_status === "pending" ? "＋ Add" : "✓ Added";
    accept.disabled = suggestion.acceptance_status !== "pending";
    accept.addEventListener("click", () => control("accept_recommendation", {
      recommendation_id: suggestion.recommendation_id,
      expected_shopping_revision: session.shopping_list_revision,
    }));
    const reject = document.createElement("button");
    reject.type = "button";
    reject.className = "button secondary";
    reject.textContent = suggestion.acceptance_status === "rejected" ? "Rejected" : "No thanks";
    reject.disabled = suggestion.acceptance_status !== "pending";
    reject.addEventListener("click", () => control("reject_recommendation", {
      recommendation_id: suggestion.recommendation_id,
      expected_shopping_revision: session.shopping_list_revision,
    }));
    actions.append(accept, reject); item.append(copy, actions);
    return item;
  }));
}

function render() {
  if (!session || !map) return;
  const customerStatus = {
    ready: "Ready", navigating: "Navigating", paused: "Paused",
    awaiting_product_confirmation: "Pick up item", awaiting_checkpoint: "Checking location",
    camera_stopped: "Location check paused", complete: "Trip complete",
  }[session.status] || session.status.replaceAll("_", " ");
  ui("connection").classList.add("connected");
  ui("connection").lastChild.textContent = ` ${customerStatus}`;
  ui("sync-status").textContent = `Synced · revision ${session.state_revision}`;
  ui("instruction-type").textContent = session.guidance.instruction_type.replaceAll("_", " ");
  const product = session.active_product;
  const customerInstruction = session.status === "awaiting_product_confirmation" && product
    ? `You've reached ${product.name}`
    : session.status === "awaiting_checkpoint"
      ? "Pause for a quick location check"
      : session.status === "ready"
        ? "Your shopping route is ready"
        : session.status === "complete"
          ? "Shopping complete — proceed to checkout"
          : session.guidance.instruction;
  ui("instruction").textContent = customerInstruction;
  ui("direction-icon").textContent = guidanceIcon();
  const maneuver = Number(session.guidance.distance_to_maneuver_m || 0);
  ui("maneuver-distance").textContent = maneuver > 0 ? `${maneuver.toFixed(1)} m` : "Now";
  ui("instruction-context").textContent = session.status === "awaiting_product_confirmation"
    ? " · Tap Picked up when the item is in your cart"
    : session.status === "ready" ? " · Tap Start to begin" : " to the next turn";
  const friendlyLocation = session.current_checkpoint?.name
    || (session.status === "ready" ? "Entrance"
      : session.status === "awaiting_product_confirmation" && product ? `${product.shelf_section} aisle`
        : product ? `On the way to ${product.name}` : "Checkout route");
  ui("location").textContent = friendlyLocation;
  ui("checkpoint").textContent = session.next_checkpoint ? session.next_checkpoint.name : "Checkout ahead";
  ui("distance").textContent = `${session.remaining_distance_m.toFixed(1)} m left`;

  ui("product").textContent = product?.name || (session.status === "complete" ? "Journey complete" : "Proceed to checkout");
  ui("product-category").textContent = product?.category || (session.status === "complete" ? "All items collected" : "Follow the highlighted route");
  ui("product-quantity").textContent = product ? `${product.remaining_quantity} remaining of ${product.requested_quantity}` : "—";
  ui("aisle").textContent = product?.shelf_section || "Checkout";
  ui("bay").textContent = product?.shelf_bay ?? "—";
  ui("level").textContent = product ? `Level ${product.shelf_level}` : "—";
  ui("shelf").textContent = product ? `${product.shelf_section} aisle · bay ${product.shelf_bay} · shelf level ${product.shelf_level}` : "Continue along the blue route.";
  ui("product-distance").textContent = product ? `${session.distance_to_active_product_m.toFixed(1)} m` : "—";
  ui("progress").style.width = `${session.navigation_progress.percent}%`;
  ui("progress-copy").textContent = `${session.navigation_progress.collected_products} of ${session.navigation_progress.total_products} products collected`;
  ui("route").replaceChildren(...session.remaining_route.map((node) => { const li = document.createElement("li"); li.textContent = node; return li; }));
  ui("session").textContent = session.session_id; ui("revision").textContent = session.state_revision; ui("shopping-revision").textContent = session.shopping_list_revision;

  ui("start").disabled = !["ready", "navigating"].includes(session.status) || session.simulation_clock.autoplay_enabled;
  ui("start").textContent = session.status === "navigating" ? "▶ Continue" : "▶ Start";
  ui("pause").disabled = !session.simulation_clock.autoplay_enabled || !session.running || session.free_walk.active;
  ui("resume").disabled = session.status !== "paused";
  ui("confirm").disabled = session.status !== "awaiting_product_confirmation";
  ui("confirm").textContent = session.status === "awaiting_product_confirmation" ? "✓ I picked up this item" : "Pick up at shelf";
  ui("skip").disabled = session.status !== "awaiting_product_confirmation";
  ui("stop").disabled = !session.simulation_clock.autoplay_enabled;
  ui("camera-navigation").disabled = !["ready", "complete"].includes(session.status);
  const freeWalk = session.free_walk || {active: false, moving: false, available_edges: []};
  ui("enter-free-walk").disabled = freeWalk.active || !["ready", "navigating", "paused"].includes(session.status);
  ui("free-walk-stop").disabled = !freeWalk.moving;
  ui("free-walk-resume").disabled = !freeWalk.active || freeWalk.moving || !freeWalk.selected_target_node_id;
  ui("request-navigation").disabled = !freeWalk.active;
  ui("replanning").textContent = session.last_replanning_reason ? `Route updated · ${session.last_replanning_reason.replaceAll("_", " ")}` : "Following the shortest route to your remaining items.";
  const options = ui("free-walk-options"); options.replaceChildren();
  freeWalk.available_edges.forEach((edge) => {
    const button = document.createElement("button"); button.type = "button"; button.textContent = `${edge.node_id} · ${Number(edge.distance_m).toFixed(1)} m`; button.disabled = freeWalk.moving;
    button.addEventListener("click", () => control("choose_free_walk_edge", {target_node_id: edge.node_id})); options.append(button);
  });
  renderProducts(); renderStops(); renderCheckpoints(); renderCheckpointStatus(); renderRecommendations(); renderMap(); speakGuidance();
}

async function poll() {
  if (busy) return;
  try {
    session = await json("/api/session/state");
    if (!selectionDirty) selected = new Set(session.selected_product_ids);
    render();
  } catch (error) {
    ui("sync-status").textContent = "Sync lost";
    ui("connection").classList.remove("connected");
    ui("connection").lastChild.textContent = " Reconnecting";
    ui("error").textContent = error.message; ui("error").hidden = false;
  }
}

ui("start").addEventListener("click", () => control("autoplay_start", {rate: Number(ui("demo-speed").value)}));
ui("camera-navigation").addEventListener("click", () => control("camera_evaluation"));
ui("pause").addEventListener("click", () => control("autoplay_pause"));
ui("resume").addEventListener("click", () => control("autoplay_resume", {rate: Number(ui("demo-speed").value)}));
ui("stop").addEventListener("click", () => control("autoplay_stop"));
ui("confirm").addEventListener("click", () => control("confirm_product", {expected_shopping_revision: session.shopping_list_revision}));
ui("skip").addEventListener("click", () => ui("skip-dialog").showModal());
ui("skip-later").addEventListener("click", () => { ui("skip-dialog").close(); control("skip_product", {decision: "keep_for_later", expected_shopping_revision: session.shopping_list_revision}); });
ui("skip-remove").addEventListener("click", () => { ui("skip-dialog").close(); control("skip_product", {decision: "remove_remaining", expected_shopping_revision: session.shopping_list_revision}); });
ui("catalog-search").addEventListener("input", renderProducts);
ui("enter-free-walk").addEventListener("click", () => control("enter_free_walk"));
ui("free-walk-stop").addEventListener("click", () => control("free_walk_stop"));
ui("free-walk-resume").addEventListener("click", () => control("free_walk_resume"));
ui("request-navigation").addEventListener("click", () => control("request_navigation"));
ui("voice-button").addEventListener("click", () => {
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
    setVoiceStatus("Voice unavailable", "error");
    return;
  }
  voiceEnabled = !voiceEnabled;
  ui("voice").checked = voiceEnabled;
  ui("voice-button").setAttribute("aria-pressed", String(voiceEnabled));
  if (voiceEnabled) {
    spokenVoiceKey = null;
    setVoiceStatus("Voice on", "active");
    speakGuidance(true);
  } else {
    voiceToken += 1;
    pendingVoice = null;
    speechSynthesis.cancel();
    setVoiceStatus("Voice off");
  }
});
ui("voice-repeat").addEventListener("click", () => speakGuidance(true));
ui("demo-speed").addEventListener("change", () => {
  if (session?.simulation_clock?.autoplay_enabled) control("autoplay_rate", {rate: Number(ui("demo-speed").value)});
});
ui("edit-items-button").addEventListener("click", () => {
  const editor = ui("edit-shopping");
  editor.open = !editor.open;
  ui("edit-items-button").setAttribute("aria-expanded", String(editor.open));
  if (editor.open) ui("catalog-search").focus();
});
ui("edit-shopping").addEventListener("toggle", () => {
  ui("edit-items-button").setAttribute("aria-expanded", String(ui("edit-shopping").open));
});
ui("zoom-in").addEventListener("click", () => { mapZoom = Math.min(1.6, mapZoom + .15); renderMap(); });
ui("zoom-out").addEventListener("click", () => { mapZoom = Math.max(.8, mapZoom - .15); renderMap(); });
ui("recenter").addEventListener("click", () => { mapZoom = 1; renderMap(); });
ui("toggle-checkpoints").addEventListener("click", () => {
  showCheckpoints = !showCheckpoints;
  ui("toggle-checkpoints").setAttribute("aria-pressed", String(showCheckpoints));
  ui("toggle-checkpoints").textContent = showCheckpoints ? "Hide tags" : "Tags";
  renderMap();
});
ui("overview-button").addEventListener("click", () => { mapZoom = 1; renderMap(); ui("overview-button").textContent = "Route centered"; setTimeout(() => { ui("overview-button").textContent = "Route overview"; }, 1200); });
document.querySelector("[data-toggle='collected-items']").addEventListener("click", (event) => { const list = ui("collected-items"); list.hidden = !list.hidden; event.currentTarget.setAttribute("aria-expanded", String(!list.hidden)); });

/* Drawer backward-compat stubs (drawer removed; panel is now always visible) */
function setItemsDrawer(open) { /* no-op: products panel is always inline */ }
ui("items-button").addEventListener("click", () => {});
ui("drawer-close").addEventListener("click", () => {});
ui("drawer-backdrop").addEventListener("click", () => {});
document.addEventListener("keydown", (event) => { if (event.key === "Escape") setItemsDrawer(false); });

Promise.all([json("/api/spatial/map"), json("/api/session/state")])
  .then(([mapData, sessionData]) => { map = mapData; session = sessionData; selected = new Set(session.selected_product_ids); render(); })
  .catch((error) => { ui("error").textContent = error.message; ui("error").hidden = false; });
setInterval(poll, 500);
