// Render the synthetic store map and drive its local graph-navigation API.
"use strict";

const state = {
  map: null,
  sim: null,
  camera: null,
  selected: new Set(),
  busy: false,
  pollBusy: false,
  connectionLost: false,
  playbackSteps: 1,
  resumeAutoplay: false,
  displayedGuidanceEvents: new Set(),
  previewSequence: -1,
  selectedCameraIndex: null,
  showCheckpoints: true,
  lastRouteRevision: null,
  clientId: sessionStorage.getItem("comp3-navigation-client-id") ||
    `research-${crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)}`,
  commandSequence: 0,
};
sessionStorage.setItem("comp3-navigation-client-id", state.clientId);
const byId = (id) => document.getElementById(id);

function commandPayload(action, values = {}) {
  state.commandSequence += 1;
  return {
    action,
    ...values,
    client_id: state.clientId,
    command_id: `${state.clientId}:${state.commandSequence}`,
  };
}

class VoiceNavigator {
  constructor(synth = window.speechSynthesis, Utterance = window.SpeechSynthesisUtterance) {
    this.synth = synth || null;
    this.Utterance = Utterance || null;
    this.enabled = false;
    this.spoken = new Set();
    this.voice = null;
    this.volume = 0.8;
  }
  get supported() { return Boolean(this.synth && this.Utterance); }
  setEnabled(enabled) {
    this.enabled = Boolean(enabled && this.supported);
    if (!this.enabled && this.synth) this.synth.cancel();
    this.updateStatus();
  }
  resetRoute() {
    if (this.synth) this.synth.cancel();
    this.spoken.clear();
    this.updateStatus();
  }
  speak(eventId, text, { replace = false } = {}) {
    if (!this.enabled || !this.supported || !eventId || this.spoken.has(eventId)) return false;
    this.spoken.add(eventId);
    if (replace || this.synth.speaking || this.synth.pending) this.synth.cancel();
    const utterance = new this.Utterance(text);
    utterance.volume = this.volume;
    if (this.voice) utterance.voice = this.voice;
    utterance.onstart = () => this.updateStatus("Speaking");
    utterance.onend = () => this.updateStatus();
    utterance.onerror = () => this.updateStatus("Unavailable");
    this.synth.speak(utterance);
    return true;
  }
  updateStatus(forced = null) {
    const node = byId("voice-status");
    if (!node) return;
    node.textContent = forced || (!this.supported ? "Unavailable" : this.enabled ? "Ready · on" : "Ready · off");
  }
}
const voice = new VoiceNavigator(
  "speechSynthesis" in window ? window.speechSynthesis : null,
  "SpeechSynthesisUtterance" in window ? window.SpeechSynthesisUtterance : null,
);
window.dashboardVoice = voice;

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

const directionIcons = {
  START: "●", STRAIGHT: "↑", TURN_LEFT: "↰", TURN_RIGHT: "↱", U_TURN: "↶",
  APPROACH_CHECKPOINT: "◇", CHECKPOINT_CONFIRMED: "✓", APPROACH_PRODUCT: "⌖",
  PRODUCT_REACHED: "★", WAIT_FOR_PICKUP: "☝", PICKUP_CONFIRMED: "✓",
  REROUTING: "⟳", LOCALIZATION_UNCERTAIN: "!", PROCEED_TO_CHECKOUT: "↑",
  ARRIVED_CHECKOUT: "✓", SCAN_CHECKPOINT: "⌾",
  FREE_WALK: "◇",
};
const popupTypes = new Set([
  "TURN_LEFT", "TURN_RIGHT", "U_TURN", "CHECKPOINT_CONFIRMED", "PRODUCT_REACHED",
  "PICKUP_CONFIRMED", "REROUTING", "LOCALIZATION_UNCERTAIN", "ARRIVED_CHECKOUT",
]);

function showGuidanceToast(event) {
  const speakable = new Set(["START", "TURN_LEFT", "TURN_RIGHT", "U_TURN", "CHECKPOINT_CONFIRMED", "PRODUCT_REACHED", "PICKUP_CONFIRMED", "REROUTING", "PROCEED_TO_CHECKOUT", "ARRIVED_CHECKOUT"]);
  const syntheticCheckpoint = event.instruction_type === "CHECKPOINT_CONFIRMED" &&
    !state.sim?.camera_evaluation?.active;
  const eventCopy = syntheticCheckpoint
    ? `Synthetic observation. ${event.instruction_text}`
    : event.instruction_text;
  if (speakable.has(event.instruction_type)) {
    voice.speak(event.event_id, eventCopy, { replace: event.instruction_type === "REROUTING" });
  }
  if (!popupTypes.has(event.instruction_type) || state.displayedGuidanceEvents.has(event.event_id)) return;
  state.displayedGuidanceEvents.add(event.event_id);
  const toast = document.createElement("div");
  toast.className = `toast ${["REROUTING", "LOCALIZATION_UNCERTAIN"].includes(event.instruction_type) ? "critical" : ""}`;
  toast.dataset.guidanceType = event.instruction_type;
  const copy = document.createElement("span");
  copy.textContent = `${syntheticCheckpoint ? "SYNTHETIC CHECKPOINT" : event.instruction_type.replaceAll("_", " ")} — ${eventCopy}`;
  const dismiss = document.createElement("button");
  dismiss.type = "button";
  dismiss.setAttribute("aria-label", "Dismiss notification");
  dismiss.textContent = "×";
  dismiss.addEventListener("click", () => toast.remove());
  toast.append(copy, dismiss);
  byId("toast-region").append(toast);
  while (byId("toast-region").children.length > 3) byId("toast-region").firstElementChild.remove();
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
      description.dataset.productQuantity = product.demo_product_id;
      description.textContent =
        `${product.demo_product_id} · ${product.category} · ${product.shelf_section} · level ${product.shelf_level}`;
      copy.append(name, description);
      label.append(input, copy);
      form.append(label);
    });
  }
  form.querySelectorAll("input").forEach((input) => {
    input.checked = state.selected.has(input.value);
    input.disabled = state.sim.guided_demo.active || state.sim.camera_evaluation.active ||
      !["ready", "complete"].includes(state.sim.status);
  });
  form.querySelectorAll("[data-product-quantity]").forEach((description) => {
    const product = products.find((item) => item.demo_product_id === description.dataset.productQuantity);
    const line = state.sim.shopping_session.items.find((item) => item.product_id === description.dataset.productQuantity);
    description.textContent = `${product.demo_product_id} · ${product.category} · ${product.shelf_section} · level ${product.shelf_level}` +
      (line ? ` · requested ${line.requested_quantity}, collected ${line.collected_quantity}, remaining ${line.remaining_quantity}` : " · not requested");
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
  if (state.showCheckpoints) {
    const layout = (state.map.apriltag_layouts || [])[0];
    const health = state.sim.localization_health || {};
    const lastId = health.last_accepted_checkpoint_id;
    const latestId = state.camera?.detected_tag_id ?? state.sim.observed_checkpoint?.tag_id;
    const rejectedId = state.sim.observed_checkpoint?.accepted === false ? state.sim.observed_checkpoint.tag_id : null;
    const candidateIds = new Set((health.candidate_checkpoints || []).map((item) => item.checkpoint_id));
    (layout?.tags || []).forEach((tag) => {
      const tagId = Number(tag.tag_id);
      const y = height - Number(tag.y_m);
      const className = tagId === lastId ? "checkpoint-tag confirmed" : tagId === rejectedId ? "checkpoint-tag rejected" : tagId === latestId ? "checkpoint-tag latest" : candidateIds.has(tagId) ? "checkpoint-tag candidate" : "checkpoint-tag";
      const group = svgNode("g", {class: className});
      group.append(svgNode("circle", {cx: tag.x_m, cy: y, r: .13}));
      group.append(svgNode("text", {x: Number(tag.x_m) + .16, y: y - .12}, String(tagId)));
      group.append(svgNode("title", {}, `AprilTag ${tagId} · ${tag.purpose} · ${tag.anchor.type} anchor`));
      svg.append(group);
    });
  }
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
  svg.append(svgNode("circle", {
    class: "uncertainty-marker", cx: estimate.x_m, cy: height - estimate.y_m,
    r: Math.max(.22, Number(state.sim.position_uncertainty_m || state.sim.localization.uncertainty_m)),
  }));
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
  svg.append(svgNode("text", {class: "position-marker-label", x: estimate.x_m + .28, y: height - estimate.y_m - .2}, "EST"));
  svg.append(svgNode("text", {class: "position-marker-label truth-label", x: truth.x_m + .28, y: height - truth.y_m + .3}, "TRUTH"));
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
  byId("operator-sync").lastChild.textContent = ` Shared · revision ${sim.state_revision}`;
  const health = sim.localization_health || {};
  const camera = state.camera || {};
  byId("health-status").textContent = health.status || "ESTIMATED";
  byId("health-status").dataset.status = health.status || "ESTIMATED";
  byId("health-last-confirmed").textContent = health.last_accepted_checkpoint_id == null
    ? "None" : `CP${health.last_accepted_checkpoint_id} · ${Number(health.last_accepted_checkpoint_timestamp_s || 0).toFixed(2)} s`;
  byId("health-raw-tag").textContent = camera.detected_tag_id == null ? "None" : `Tag ${camera.detected_tag_id}`;
  const observation = sim.observed_checkpoint;
  byId("health-classification").textContent = observation
    ? `${observation.accepted ? "Accepted" : "Rejected"} · ${String(observation.classification || observation.reason).replaceAll("_", " ")}${observation.accepted ? "" : ` · ${String(observation.reason).replaceAll("_", " ")}`}`
    : "None";
  const healthPosition = health.current_estimated_position || sim.estimate;
  byId("health-estimate").textContent = `${Number(healthPosition.x_m).toFixed(2)}, ${Number(healthPosition.y_m).toFixed(2)} m`;
  byId("health-uncertainty").textContent = `±${Number(health.position_uncertainty_m || 0).toFixed(2)} m`;
  byId("health-candidates").textContent = (health.candidate_checkpoints || []).length
    ? health.candidate_checkpoints.map((item) => `CP${item.checkpoint_id} (${Number(item.graph_distance_m).toFixed(1)} m)`).join(", ")
    : "No nearby graph-derived candidates";
  byId("health-camera").textContent = `${camera.connection || "stopped"} · ${camera.scanning ? "frames arriving" : "not scanning"}`;
  byId("health-sync").textContent = sim.last_successful_sync_at ? new Date(sim.last_successful_sync_at).toLocaleTimeString() : "—";
  const warning = byId("localization-warning");
  warning.hidden = !health.warning || health.acknowledged;
  byId("localization-warning-title").textContent = String(health.warning_key || "").startsWith("CORRECTION_REROUTE")
    ? "Accepted correction triggered rerouting"
    : health.status === "OBSERVATION_REJECTED" ? "Implausible observation rejected" : "Localization uncertain";
  byId("localization-warning-copy").textContent = `${health.explanation || ""} ${health.recommended_operator_action || ""}`.trim();
  byId("instruction").textContent = guide.instruction;
  byId("instruction").dataset.guidanceType = guide.instruction_type;
  byId("instruction-type").textContent = guide.instruction_type.replaceAll("_", " ");
  byId("direction-icon").textContent = directionIcons[guide.instruction_type] || "●";
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
    ? `${sim.active_product.shelf_section} · Level ${sim.active_product.shelf_level} · ${sim.active_product.shelf_side || "side pending"}`
    : "Checkout";
  byId("product-distance").textContent = sim.active_product
    ? `${sim.distance_to_active_product_m.toFixed(1)} m` : "—";
  byId("heading").textContent = `${sim.heading_deg.toFixed(1)}°`;
  byId("navigation-progress").textContent =
    `${sim.navigation_progress.collected_products}/${sim.navigation_progress.total_products} · ${sim.navigation_progress.percent.toFixed(0)}%`;
  byId("remaining-count").textContent = String(sim.remaining_products.length);
  byId("localization-status").textContent =
    `${sim.localization.status.replaceAll("_", " ")} · ±${sim.localization.uncertainty_m.toFixed(2)} m`;
  byId("next-checkpoint").textContent = sim.next_checkpoint
    ? `${sim.next_checkpoint.name} · CP${sim.next_checkpoint.checkpoint_id}`
    : "No mapped checkpoint ahead";
  byId("checkpoint-distance").textContent = `${sim.distance_to_checkpoint_m.toFixed(1)} m`;
  byId("observed-checkpoint").textContent = sim.observed_checkpoint
    ? `CP${sim.observed_checkpoint.tag_id} · ${sim.observed_checkpoint.accepted ? "accepted" : sim.observed_checkpoint.reason}`
    : "None";
  byId("observation-classification").textContent = sim.observed_checkpoint?.classification?.replaceAll("_", " ") || "None";
  byId("last-checkpoint").textContent = sim.last_confirmed_checkpoint
    ? `${sim.last_confirmed_checkpoint.node_id} · CP${sim.last_confirmed_checkpoint.checkpoint_id}`
    : "None";
  byId("correction").textContent = sim.last_confirmed_checkpoint
    ? `${sim.last_confirmed_checkpoint.correction_m.toFixed(3)} m (${sim.last_confirmed_checkpoint.detection_source === "mac_camera_opencv" ? "camera" : "simulated"})`
    : "None";
  byId("sim-time").textContent = `${sim.simulation_time_s.toFixed(2)} s`;
  byId("remaining-distance").textContent = `${sim.remaining_distance_m.toFixed(1)} m`;
  const guided = sim.guided_demo;
  const cameraMode = sim.camera_evaluation;
  byId("camera-connection").textContent = camera.connection || "stopped";
  byId("camera-scanning").textContent = camera.scanning ? "Yes · Python detector" : "No";
  byId("camera-scan-state").textContent = camera.scanning ? "LIVE · SCANNING" : "NOT SCANNING";
  byId("camera-expected").textContent = cameraMode.gate?.checkpoint_id == null
    ? "No active gate" : `CP${cameraMode.gate.checkpoint_id}`;
  byId("camera-tag").textContent = camera.detected_tag_id == null
    ? "None" : `ID ${camera.detected_tag_id}`;
  byId("camera-result").textContent = camera.last_result || "None";
  byId("camera-reason").textContent = camera.error || camera.rejection_reason || "—";
  const cameraEvents = (camera.scan_events || []).filter((event) => "accepted" in event);
  const acceptedCount = cameraEvents.filter((event) => event.accepted).length;
  byId("camera-counts").textContent = `${acceptedCount} / ${cameraEvents.length - acceptedCount}`;
  byId("camera-frame").textContent = camera.resolution
    ? `${camera.resolution[0]}×${camera.resolution[1]} · ${camera.capture_backend || "backend unavailable"}`
    : camera.capture_backend || "—";
  byId("camera-device").textContent = camera.device_name || "Not exposed by platform";
  const cameraError = byId("camera-error");
  if (camera.error) {
    cameraError.hidden = false;
    cameraError.textContent = camera.error;
  }
  const preview = byId("camera-preview");
  const placeholder = byId("camera-placeholder");
  preview.hidden = !camera.preview_available;
  placeholder.hidden = Boolean(camera.preview_available);
  if (camera.preview_available && camera.preview_sequence !== state.previewSequence) {
    state.previewSequence = camera.preview_sequence;
    preview.src = `/api/camera/preview.jpg?sequence=${camera.preview_sequence}`;
  }
  const newestCameraEvent = cameraEvents.at(-1);
  if (newestCameraEvent) {
    const cameraEventId = `camera-${newestCameraEvent.detection_timestamp_s}`;
    const checkpoint = newestCameraEvent.detected_tag_id;
    const cameraSpeech = newestCameraEvent.accepted
      ? `Checkpoint ${checkpoint} accepted.`
      : `Incorrect checkpoint ${checkpoint}. ${String(newestCameraEvent.reason || "rejected").replaceAll("_", " ")}.`;
    voice.speak(cameraEventId, cameraSpeech);
  }
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
  byId("shopping-list-revision").textContent = String(sim.shopping_list_revision);
  byId("route-revision").textContent = String(sim.route_revision);
  const recommendation = sim.recommendation_diagnostics || {};
  const modelStatus = byId("recommendation-model-status");
  modelStatus.textContent = recommendation.inference_ready ? "ready" : "disabled";
  modelStatus.dataset.status = recommendation.inference_ready ? "CONFIRMED" : "CAMERA_UNAVAILABLE";
  byId("recommendation-model-version").textContent = recommendation.inference_ready
    ? `${recommendation.model_name} · ${recommendation.model_version}` : "Unavailable";
  byId("recommendation-checksum").textContent = recommendation.artifact_sha256
    ? `${recommendation.artifact_sha256.slice(0, 12)}…` : "—";
  byId("recommendation-revisions").textContent =
    `${sim.shopping_list_revision} / ${sim.route_revision}`;
  byId("recommendation-latency").textContent = recommendation.inference_latency_ms == null
    ? "—" : `${Number(recommendation.inference_latency_ms).toFixed(3)} / ${Number(recommendation.eligibility_filtering_latency_ms).toFixed(3)} / ${Number(recommendation.end_to_end_latency_ms).toFixed(3)} ms`;
  byId("recommendation-input").textContent =
    (recommendation.normalized_basket_input || []).join(", ") || "No mapped input";
  byId("recommendation-counts").textContent = recommendation.candidate_count == null
    ? "—" : `${recommendation.candidate_count} ranked · ${recommendation.eligible_candidate_count} eligible · ${recommendation.filtered_candidate_count} filtered`;
  byId("recommendation-fallback").textContent =
    recommendation.error || recommendation.fallback_state?.replaceAll("_", " ") || "None";
  const recommendationEvent = (sim.recommendation_events || []).at(-1);
  byId("recommendation-latest-event").textContent = recommendationEvent
    ? `${recommendationEvent.event_type} · ${recommendationEvent.recommendation_id}` : "None";
  const candidateList = byId("recommendation-candidates");
  candidateList.replaceChildren(...(recommendation.candidate_ranking || []).slice(0, 12).map((candidate) => {
    const item = document.createElement("li");
    const disposition = candidate.eligible ? "eligible" : candidate.filter_reasons.join(", ");
    item.textContent = `#${candidate.rank} ${candidate.normalized_product} → ${candidate.mapped_demo_product_id || "unmapped"} · score ${Number(candidate.model_score).toFixed(6)} · ${disposition}`;
    return item;
  }));
  if (state.lastRouteRevision !== null && state.lastRouteRevision !== sim.route_revision) {
    document.querySelector(".map-card").classList.remove("route-revised");
    void document.querySelector(".map-card").offsetWidth;
    document.querySelector(".map-card").classList.add("route-revised");
  }
  state.lastRouteRevision = sim.route_revision;
  byId("replanning-reason").textContent = sim.last_replanning_reason?.replaceAll("_", " ") || "None";
  const latestReplan = sim.adaptive_replan_history.at(-1);
  byId("route-cost-change").textContent = latestReplan
    ? `${Number(latestReplan.previous_route_cost_m).toFixed(2)} m → ${Number(latestReplan.new_route_cost_m).toFixed(2)} m`
    : "—";
  byId("optimization-time").textContent = latestReplan
    ? `${Number(latestReplan.replanning_computation_ms).toFixed(3)} ms` : "—";
  byId("route-anchor").textContent = sim.route_anchor
    ? (sim.route_anchor.anchor_type === "node" ? sim.route_anchor.node_id : `${sim.route_anchor.edge_start_node_id}–${sim.route_anchor.edge_end_node_id}`)
    : "—";
  byId("shopping-events").textContent = String(sim.shopping_session.events.length);
  byId("free-walk-state").textContent = sim.free_walk.active
    ? (sim.free_walk.moving ? `moving to ${sim.free_walk.selected_target_node_id}` : "stopped")
    : "inactive";
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
  sim.guidance_events.forEach(showGuidanceToast);
  byId("guided-demo").disabled = state.busy;
  byId("camera-evaluation").disabled = state.busy || !["ready", "complete"].includes(sim.status);
  byId("start-camera").disabled = state.busy || camera.scanning || state.selectedCameraIndex == null;
  byId("stop-camera").disabled = state.busy || !camera.scanning;
  byId("refresh-cameras").disabled = state.busy;
  byId("select-camera").disabled = state.busy || byId("camera-index").value === "";
  byId("camera-index").disabled = state.busy;
  byId("start").disabled = sim.status !== "ready" || guided.active || cameraMode.active;
  byId("pause").disabled = !sim.running || sim.free_walk.active;
  byId("resume").disabled = sim.status !== "paused";
  byId("step").disabled = !["navigating", "paused", "free_walking"].includes(sim.status) || state.busy;
  byId("wrong-turn").disabled = guided.active || cameraMode.active || sim.status !== "navigating" || sim.reroute_count > 0;
  byId("enter-free-walk").disabled = sim.free_walk.active || guided.active || cameraMode.active || !["ready", "navigating", "paused"].includes(sim.status);
  byId("free-walk-stop").disabled = !sim.free_walk.moving;
  byId("free-walk-resume").disabled = !sim.free_walk.active || sim.free_walk.moving || !sim.free_walk.selected_target_node_id;
  byId("request-navigation").disabled = !sim.free_walk.active;
  const freeWalkOptions = byId("free-walk-options");
  freeWalkOptions.replaceChildren();
  sim.free_walk.available_edges.forEach((edge) => {
    const button = document.createElement("button");
    button.type = "button"; button.className = "button secondary";
    button.textContent = `${edge.node_id} · ${edge.distance_m.toFixed(1)} m`;
    button.disabled = sim.free_walk.moving;
    button.addEventListener("click", () => control("choose_free_walk_edge", { target_node_id: edge.node_id }));
    freeWalkOptions.append(button);
  });
  byId("confirm-product").disabled = guided.active || sim.status !== "awaiting_product_confirmation";
  byId("apply-products").disabled = guided.active || cameraMode.active || !["ready", "complete"].includes(sim.status);
  byId("product-list").querySelectorAll("input").forEach((input) => {
    input.disabled = guided.active || cameraMode.active || !["ready", "complete"].includes(sim.status);
  });
  renderProducts();
  renderMap();
}

async function control(action, values = {}) {
  if (state.busy) return;
  state.busy = true;
  try {
    if (["reset", "guided_demo", "set_products"].includes(action)) {
      state.displayedGuidanceEvents.clear();
      byId("toast-region").replaceChildren();
      voice.resetRoute();
    }
    state.sim = await requestJson("/api/session/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(commandPayload(action, values)),
    });
    state.selected = new Set(state.sim.selected_product_ids);
    showNotice("");
    render();
  } catch (error) {
    if (error.message.includes("Only controller")) {
      state.sim = await requestJson("/api/session/state");
      showNotice("");
      render();
    } else {
      showError(error.message);
    }
  } finally {
    state.busy = false;
    if (state.map && state.sim) render();
  }
}

async function cameraControl(action) {
  if (state.busy) return;
  state.busy = true;
  try {
    state.camera = await requestJson("/api/camera/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        camera_index: state.selectedCameraIndex,
      }),
    });
    byId("camera-error").hidden = true;
    byId("camera-error").textContent = "";
    showNotice(state.camera.error || "");
  } catch (error) {
    byId("camera-error").hidden = false;
    byId("camera-error").textContent = error.message;
    showError(error.message);
  } finally {
    state.busy = false;
    if (state.map && state.sim) render();
  }
}

async function refreshCameras() {
  if (state.busy) return;
  state.busy = true;
  const results = byId("camera-probe-results");
  results.textContent = "Refreshing frame-verified AVFoundation cameras…";
  try {
    const payload = await requestJson("/api/camera/control", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "refresh", max_camera_index: 5 }),
    });
    const select = byId("camera-index");
    const previous = state.selectedCameraIndex;
    select.replaceChildren();
    if (!payload.devices.length) select.append(new Option("No readable cameras detected", ""));
    payload.devices.forEach((device) => {
      const resolution = device.frame_dimensions.join("×");
      select.append(new Option(`${device.label} · ${resolution} · ${device.backend || payload.capture_backend}`, String(device.camera_index)));
    });
    const preserved = payload.devices.some((device) => device.camera_index === previous);
    state.selectedCameraIndex = preserved ? previous : payload.devices[0]?.camera_index ?? null;
    select.value = state.selectedCameraIndex == null ? "" : String(state.selectedCameraIndex);
    results.replaceChildren();
    const summary = document.createElement("div");
    summary.className = "probe-device";
    summary.textContent = payload.refresh_message;
    results.append(summary);
    payload.devices.forEach((device) => {
      const item = document.createElement("div");
      item.className = "probe-device";
      item.textContent = `${device.label} · verified frame ${device.frame_dimensions.join("×")} · ${device.backend || payload.capture_backend}`;
      results.append(item);
    });
    const failedCount = payload.attempts.length - payload.devices.length;
    if (failedCount) {
      const note = document.createElement("div");
      note.className = "probe-device";
      note.textContent = `${failedCount} probed index/indices did not return a readable frame and were excluded.`;
      results.append(note);
    }
    state.camera = await requestJson("/api/camera/state");
    byId("camera-error").hidden = true;
    byId("camera-error").textContent = "";
    showNotice("");
  } catch (error) {
    results.textContent = error.message;
    byId("camera-error").hidden = false;
    byId("camera-error").textContent = error.message;
    showError(error.message);
  } finally {
    state.busy = false;
    render();
  }
}

function loadVoices() {
  if (!voice.supported) {
    byId("voice-toggle").disabled = true;
    byId("voice-test").disabled = true;
    byId("voice-select").disabled = true;
    voice.updateStatus();
    return;
  }
  const select = byId("voice-select");
  const previous = select.value;
  select.replaceChildren(new Option("System default", ""));
  voice.synth.getVoices().forEach((item, index) => {
    const option = new Option(`${item.name} · ${item.lang}`, String(index));
    select.append(option);
  });
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  voice.updateStatus();
}

async function startCameraEvaluation() {
  if (state.selectedCameraIndex == null) {
    showError("Refresh Cameras and choose a verified camera before starting camera evaluation.");
    return;
  }
  await control("camera_evaluation");
  if (state.sim?.camera_evaluation.active) await cameraControl("start");
}

async function poll() {
  if (state.pollBusy) return;
  state.pollBusy = true;
  try {
    if (state.connectionLost) {
      if (!state.map) {
        [state.map, state.sim] = await Promise.all([
          requestJson("/api/spatial/map"),
          requestJson("/api/session/state"),
        ]);
      } else {
        state.sim = await requestJson("/api/session/state");
      }
      state.selected = new Set(state.sim.selected_product_ids);
      showNotice("");
      render();
      return;
    }
    state.sim = await requestJson("/api/session/state");
    state.camera = await requestJson("/api/camera/state");
    showNotice("");
    render();
  } catch (error) {
    if (error.message.includes("Only controller")) {
      state.sim = await requestJson("/api/session/state");
      showNotice("");
      render();
    } else {
      showError(error.message);
    }
  } finally {
    state.pollBusy = false;
  }
}

async function initialize() {
  try {
    [state.map, state.sim, state.camera] = await Promise.all([
      requestJson("/api/spatial/map"),
      requestJson("/api/session/state"),
      requestJson("/api/camera/state"),
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
byId("camera-evaluation").addEventListener("click", startCameraEvaluation);
byId("refresh-cameras").addEventListener("click", refreshCameras);
byId("select-camera").addEventListener("click", async () => {
  state.selectedCameraIndex = Number(byId("camera-index").value);
  byId("camera-probe-results").textContent = `Selected verified camera index ${state.selectedCameraIndex}.`;
  if (state.camera?.scanning && state.camera.camera_index !== state.selectedCameraIndex) {
    await cameraControl("switch");
  }
});
byId("start-camera").addEventListener("click", () => cameraControl("start"));
byId("stop-camera").addEventListener("click", () => cameraControl("stop"));
byId("pause").addEventListener("click", () => {
  state.resumeAutoplay = Boolean(state.sim.simulation_clock?.autoplay_enabled);
  control(state.resumeAutoplay ? "autoplay_pause" : "pause");
});
byId("resume").addEventListener("click", () =>
  control(state.resumeAutoplay ? "autoplay_resume" : "resume", { rate: state.playbackSteps })
);
byId("step").addEventListener("click", () => control("step"));
byId("reset").addEventListener("click", () => { state.resumeAutoplay = false; control("reset"); });
byId("wrong-turn").addEventListener("click", () => control("wrong_turn"));
byId("confirm-product").addEventListener("click", () => control("confirm_product", {
  expected_shopping_revision: state.sim.shopping_list_revision,
}));
byId("enter-free-walk").addEventListener("click", () => control("enter_free_walk"));
byId("free-walk-stop").addEventListener("click", () => control("free_walk_stop"));
byId("free-walk-resume").addEventListener("click", () => control("free_walk_resume"));
byId("request-navigation").addEventListener("click", () => control("request_navigation"));
byId("show-checkpoints").addEventListener("change", (event) => {
  state.showCheckpoints = event.target.checked;
  renderMap();
});
byId("acknowledge-localization").addEventListener("click", () => control(
  "acknowledge_localization_warning",
  {warning_key: state.sim.localization_health.warning_key},
));
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
byId("playback").addEventListener("change", (event) =>
  control("autoplay_rate", { rate: Number(event.target.value) })
);
byId("voice-toggle").addEventListener("click", () => {
  voice.setEnabled(!voice.enabled);
  byId("speech-enabled").checked = voice.enabled;
  byId("voice-toggle").textContent = voice.enabled ? "Disable Voice" : "Enable Voice";
  byId("voice-toggle").setAttribute("aria-pressed", String(voice.enabled));
});
byId("voice-test").addEventListener("click", () => {
  if (!voice.enabled) voice.setEnabled(true);
  byId("speech-enabled").checked = voice.enabled;
  byId("voice-toggle").textContent = voice.enabled ? "Disable Voice" : "Enable Voice";
  voice.speak(`voice-test-${Date.now()}`, "Voice navigation is ready.", { replace: true });
});
byId("voice-volume").addEventListener("input", (event) => {
  voice.volume = Number(event.target.value);
  byId("voice-volume-value").textContent = `${Math.round(voice.volume * 100)}%`;
});
byId("voice-select").addEventListener("change", (event) => {
  const voices = voice.synth?.getVoices() || [];
  voice.voice = event.target.value === "" ? null : voices[Number(event.target.value)] || null;
});
loadVoices();
if (voice.supported) voice.synth.onvoiceschanged = loadVoices;

// Keep customer-facing information on /customer and make this view explicitly
// operational: controls, landmarks, detector processing, error codes and audit.
const operatorSections = [
  [".shopping-panel", "01 · SESSION CONTROL", "Products & operating mode"],
  [".map-card", "02 · LANDMARKS & ROUTE", "Live store position"],
  [".camera-panel", "03 · TAG DETECTION & PROCESSING", "AprilTag scanner"],
  [".guidance-panel", "04 · VALIDATION & ERROR CODES", "Localization diagnostics"],
  [".results-panel", "05 · EVENTS & AUDIT LOG", "Session evidence"],
];
operatorSections.forEach(([selector, label, title]) => {
  const section = document.querySelector(selector);
  const eyebrow = section?.querySelector(".section-heading .eyebrow");
  const heading = section?.querySelector(".section-heading h2");
  if (eyebrow) eyebrow.textContent = label;
  if (heading) heading.textContent = title;
});
const navigationDiagnostics = document.querySelector(".guidance-panel details.diagnostics");
if (navigationDiagnostics) navigationDiagnostics.open = true;
initialize();
window.setInterval(poll, 200);
