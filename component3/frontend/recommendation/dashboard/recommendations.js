"use strict";

const byId = (id) => document.getElementById(id);
const clientId = sessionStorage.getItem("comp3-reco-client-id") || `reco-${crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)}`;
sessionStorage.setItem("comp3-reco-client-id", clientId);
let commandNumber = 0;
let state = null;
let map = null;
let busy = false;

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function setActionStatus(message) { byId("action-status").textContent = message; }

async function control(action, extra = {}) {
  if (busy) return false;
  busy = true;
  try {
    commandNumber += 1;
    state = await request("/api/session/control", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({action, ...extra, client_id: clientId, command_id: `${clientId}:${commandNumber}`, session_generation: state?.session_generation}),
    });
    byId("error").hidden = true;
    render();
    return true;
  } catch (error) {
    byId("error").textContent = error.message;
    byId("error").hidden = false;
    return false;
  } finally { busy = false; }
}

function populateProductPicker() {
  const picker = byId("product-picker");
  const priorValue = picker.value;
  const products = Array.isArray(map?.products) ? map.products : [];
  const placeholder = new Option("Select a verified demo product…", "", true, true);
  placeholder.disabled = true;
  picker.replaceChildren(placeholder);
  products.forEach((product) => picker.append(new Option(
    `${product.name} · ${product.shelf_section || "verified aisle"}`,
    product.demo_product_id,
  )));
  if ([...picker.options].some((option) => option.value === priorValue)) picker.value = priorValue;
  picker.disabled = products.length === 0;
  byId("confirm-cart").disabled = !picker.value;
  byId("picker-hint").textContent = products.length
    ? `${products.length} verified products are available for this offline demonstration.`
    : "No verified demo products are available.";
}

function renderCart() {
  const cart = state.confirmed_cart_items || [];
  byId("confirmed-cart").replaceChildren(...cart.map((item) => {
    const li = document.createElement("li");
    const copy = document.createElement("span");
    const remove = document.createElement("button");
    copy.textContent = `${item.name} ×${item.confirmed_quantity}`;
    remove.className = "secondary compact";
    remove.type = "button";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => control("confirmed_cart_remove", {product_id: item.product_id}));
    li.append(copy, remove);
    return li;
  }));
  byId("recommendation-wishlist").replaceChildren(...(state.recommendation_wishlist_items || []).map((item) => {
    const li = document.createElement("li");
    li.textContent = item.name;
    return li;
  }));
}

function renderSuggestion() {
  const diagnostics = state.recommendation_diagnostics || {};
  const policy = diagnostics.policy || {};
  const suggestions = state.recommendations || [];
  byId("gate-message").textContent = policy.gate_message || "Recommendation policy unavailable";
  const open = Number(policy.distinct_items || 0) >= Number(policy.min_distinct_items || 0);
  byId("gate-state").textContent = open ? "Gate open" : "Gate closed";
  byId("gate-state").className = `pill ${open ? "open" : "closed"}`;
  byId("mapping-summary").textContent = `${diagnostics.distinct_cart_item_count || 0} confirmed items count toward the gate · ${diagnostics.mapped_model_input_count || 0} verified mapped items reached the model · ${(diagnostics.unmapped_demo_product_ids || []).length} unmapped items were excluded.`;
  const host = byId("suggestion");
  if (!suggestions.length) {
    host.className = "suggestion-empty";
    host.textContent = open ? "No customer-facing suggestion is currently allowed by the policy." : "No customer card is displayed while the gate is closed.";
    return;
  }
  const suggestion = suggestions[0];
  const card = document.createElement("div");
  const tag = document.createElement("p");
  const title = document.createElement("h3");
  const copy = document.createElement("p");
  const actions = document.createElement("div");
  const accept = document.createElement("button");
  const wishlist = document.createElement("button");
  const dismiss = document.createElement("button");
  card.className = "suggestion-card";
  tag.className = "eyebrow";
  tag.textContent = "ONE PASSIVE EXPERIMENTAL SUGGESTION";
  title.textContent = suggestion.product_name;
  copy.textContent = "Accepting does not mark this product as physically collected.";
  actions.className = "actions";
  accept.className = "primary";
  accept.type = "button";
  accept.textContent = "Accept suggestion";
  accept.addEventListener("click", () => control("standalone_accept_recommendation", {recommendation_id: suggestion.recommendation_id, expected_shopping_revision: state.shopping_list_revision}));
  wishlist.className = "secondary";
  wishlist.type = "button";
  wishlist.textContent = "Add to Wishlist";
  wishlist.addEventListener("click", () => control("recommendation_add_wishlist", {recommendation_id: suggestion.recommendation_id, expected_shopping_revision: state.shopping_list_revision}));
  dismiss.className = "secondary";
  dismiss.type = "button";
  dismiss.textContent = "Dismiss";
  dismiss.addEventListener("click", () => control("reject_recommendation", {recommendation_id: suggestion.recommendation_id, expected_shopping_revision: state.shopping_list_revision}));
  actions.append(accept, wishlist, dismiss);
  card.append(tag, title, copy, actions);
  host.className = "";
  host.replaceChildren(card);
}

function renderBackend() {
  const diagnostics = state.recommendation_diagnostics || {};
  const policy = diagnostics.policy || {};
  byId("ranking").replaceChildren(...(diagnostics.candidate_ranking || []).map((candidate) => {
    const row = document.createElement("tr");
    const score = candidate.model_score == null ? "Unavailable" : Number(candidate.model_score).toFixed(5);
    [candidate.rank, candidate.normalized_product, score, candidate.eligible ? "Yes" : "No", (candidate.filter_reasons || []).join(", ") || "—", candidate.route_detour_cost_m == null ? "—" : `${Number(candidate.route_detour_cost_m).toFixed(1)} m`].forEach((value) => {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    });
    return row;
  }));
  byId("model-state").textContent = diagnostics.inference_ready ? "Checksum verified" : "Unavailable";
  byId("model-state").className = `pill ${diagnostics.inference_ready ? "open" : "closed"}`;
  byId("model-identity").textContent = `model_version=${diagnostics.model_version || "unknown"} · sha256=${diagnostics.artifact_sha256 || "unavailable"}`;
  byId("diag-events").textContent = (state.confirmed_cart_items || []).map((item) => `${item.product_id} (${item.name})`).join(", ") || "None";
  byId("diag-input").textContent = (diagnostics.normalized_basket_input || []).join(", ") || "None";
  byId("diag-excluded").textContent = (diagnostics.unmapped_demo_product_ids || []).join(", ") || "None";
  byId("diag-policy").textContent = `${policy.distinct_items || 0}/${policy.min_distinct_items || 0} distinct · debounce ${policy.debounce_active ? "active" : "clear"} · ${(policy.reasons || []).join(", ") || "allowed"}`;
  byId("diag-pending").textContent = policy.product_arrival_pending ? "Yes" : "No";
  byId("diag-selected").textContent = state.recommendations?.[0]?.product_name || "None";
}

function render() {
  if (!state) return;
  byId("sync").textContent = `Independent recommendation session · revision ${state.state_revision}`;
  renderCart();
  renderSuggestion();
  renderBackend();
}

async function bootstrap() {
  try {
    [map, state] = await Promise.all([request("/api/spatial/map"), request("/api/session/state")]);
    populateProductPicker();
    render();
  } catch (error) {
    byId("error").textContent = error.message;
    byId("error").hidden = false;
    return;
  }
  request("/reco_evidence.json")
    .then((evidence) => { byId("evidence").textContent = evidence.wording; })
    .catch(() => { byId("evidence").textContent = "Experimental model results are shown in Backend Analysis."; });
}

document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => {
  document.querySelectorAll(".tab").forEach((item) => item.classList.toggle("active", item === button));
  byId("customer-tab").hidden = button.dataset.tab !== "customer";
  byId("backend-tab").hidden = button.dataset.tab !== "backend";
}));
byId("product-picker").addEventListener("change", () => { byId("confirm-cart").disabled = !byId("product-picker").value; });
byId("confirm-cart").addEventListener("click", async () => {
  const productId = byId("product-picker").value;
  if (!productId) { setActionStatus("Select a verified demo product first."); return; }
  setActionStatus("Adding confirmed cart event…");
  const added = await control("confirmed_cart_add", {product_id: productId});
  setActionStatus(added ? "Confirmed cart event added." : "Cart event was not added.");
});
byId("reset-demo").addEventListener("click", async () => {
  setActionStatus("Resetting recommendation trip…");
  const reset = await control("reset_demo");
  setActionStatus(reset ? "Recommendation demo reset. Confirmed cart is empty." : "Reset failed.");
});

bootstrap();
setInterval(async () => {
  if (busy || !state) return;
  try { state = await request("/api/session/state"); render(); }
  catch (_) { byId("sync").textContent = "Sync lost"; }
}, 500);
