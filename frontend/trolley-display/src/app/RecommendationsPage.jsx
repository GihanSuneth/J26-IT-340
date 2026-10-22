import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./RecommendationsPage.css";

const API = "http://127.0.0.1:8001";

const CATEGORY_IMAGES = [
  { match: ["rice", "grain"], image: "https://images.unsplash.com/photo-1586201375761-83865001e31c?auto=format&fit=crop&w=700&q=85" },
  { match: ["fresh produce", "fruit", "vegetable"], image: "https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=700&q=85" },
  { match: ["dairy", "milk", "yogurt"], image: "https://images.unsplash.com/photo-1563636619-e9143da7973b?auto=format&fit=crop&w=700&q=85" },
  { match: ["biscuit", "cracker"], image: "https://images.unsplash.com/photo-1558961363-fa8fdf82db35?auto=format&fit=crop&w=700&q=85" },
  { match: ["oil", "fat", "ghee"], image: "https://images.unsplash.com/photo-1474979266404-7eaacbcd87c5?auto=format&fit=crop&w=700&q=85" },
  { match: ["coffee", "malt"], image: "https://images.unsplash.com/photo-1512568400610-62da28bc8a13?auto=format&fit=crop&w=700&q=85" },
  { match: ["soft drink", "beverage"], image: "https://images.unsplash.com/photo-1581636625402-29b2a704ef13?auto=format&fit=crop&w=700&q=85" },
  { match: ["tea"], image: "https://images.unsplash.com/photo-1544787219-7f47ccb76574?auto=format&fit=crop&w=700&q=85" },
  { match: ["canned", "preserved"], image: "https://images.unsplash.com/photo-1584269600464-37b1b58a9fe7?auto=format&fit=crop&w=700&q=85" },
  { match: ["chocolate", "confectionery"], image: "https://images.unsplash.com/photo-1548907040-4d42c2e2d4c8?auto=format&fit=crop&w=700&q=85" },
  { match: ["noodle", "pasta"], image: "https://images.unsplash.com/photo-1551183053-bf91a1d81141?auto=format&fit=crop&w=700&q=85" },
  { match: ["personal care", "hair", "soap", "oral"], image: "https://images.unsplash.com/photo-1608248543803-ba4f8c70ae0b?auto=format&fit=crop&w=700&q=85" },
  { match: ["sauce", "condiment"], image: "https://images.unsplash.com/photo-1472476443507-c7a5948772fc?auto=format&fit=crop&w=700&q=85" },
  { match: ["spice", "curry"], image: "https://images.unsplash.com/photo-1532336414038-cf19250c5757?auto=format&fit=crop&w=700&q=85" },
  { match: ["sugar", "sweetener"], image: "https://images.unsplash.com/photo-1581441363689-1f3c3c414635?auto=format&fit=crop&w=700&q=85" },
];
const DEFAULT_IMAGE = "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=700&q=85";
const money = (value) => value == null || !Number.isFinite(Number(value))
  ? "Price unavailable"
  : `LKR ${Number(value).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

function categoryImage(category = "") {
  const normalized = String(category).toLowerCase();
  return CATEGORY_IMAGES.find((entry) => entry.match.some((word) => normalized.includes(word)))?.image || DEFAULT_IMAGE;
}

function normalizeRecommendation(row, index, customerId) {
  const name = row.product_name ?? row.item_name ?? row.Item_Name ?? row.name ?? row.product ?? "";
  const category = row.category ?? row.Category ?? row.product_category ?? "Groceries";
  const rawPrice = row.price_lkr ?? row.Price_LKR ?? row.price ?? row.unit_price ?? null;
  const parsedPrice = rawPrice === null || rawPrice === "" ? null : Number(rawPrice);
  return {
    id: String(row.product_id ?? row.item_id ?? row.Item_ID ?? row.id ?? `${customerId}-${index}`),
    name: String(name),
    category: String(category),
    price: Number.isFinite(parsedPrice) ? parsedPrice : null,
    image: categoryImage(category),
    reason: row.reason ?? row.explanation ?? row.recommendation_reason ?? "Recommended from your purchase history",
    aisle: row.aisle ?? row.Aisle ?? category,
  };
}

export default function RecommendationsPage() {
  const navigate = useNavigate();
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem("user") || "null"); }
    catch { return null; }
  });
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const token = localStorage.getItem("access_token");
      if (!token) {
        navigate("/login", { replace: true });
        return;
      }
      try {
        // Trust the backend's authenticated identity, not a customer ID typed in the browser.
        const meResponse = await fetch(`${API}/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
          signal: controller.signal,
        });
        if (meResponse.status === 401) {
          localStorage.removeItem("access_token");
          localStorage.removeItem("user");
          navigate("/login", { replace: true });
          return;
        }
        if (!meResponse.ok) throw new Error(`Could not verify your account (${meResponse.status}).`);
        const authenticatedUser = await meResponse.json();
        setUser(authenticatedUser);
        localStorage.setItem("user", JSON.stringify(authenticatedUser));
        const customerId = authenticatedUser.customer_id;
        if (!customerId) throw new Error("Your account does not have a customer ID yet.");

        const response = await fetch(
          `${API}/c4/recommendations/${encodeURIComponent(customerId)}?top_n=5`,
          { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal }
        );
        const payload = await response.json().catch(() => ({}));
        if (response.status === 404) {
          setProducts([]);
          setLoadError(payload.detail || "No purchase-history recommendations are available for this customer yet.");
          return;
        }
        if (!response.ok) throw new Error(payload.detail || `Recommendation service returned ${response.status}.`);
        const rows = Array.isArray(payload) ? payload : payload.recommendations ?? payload.items ?? [];
        const mapped = rows.map((row, index) => normalizeRecommendation(row, index, customerId)).filter((item) => item.name);
        setProducts(mapped.slice(0, 5));
        if (!mapped.length) setLoadError("The recommendation service returned no products for your account yet.");
      } catch (error) {
        if (error.name !== "AbortError") setLoadError(`${error.message || "Could not load recommendations."} Check that the backend and recommendation model are running.`);
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    load();
    return () => controller.abort();
  }, [navigate]);

  const selectedProduct = useMemo(() => products.find((product) => product.id === selectedId), [products, selectedId]);

  return (
    <main className="recommendation-kiosk">
      <header className="rk-header">
        <div className="rk-brand" aria-label="SmartTrolley">
          <span className="rk-logo" aria-hidden="true">🛒</span>
          <span className="rk-brand-copy"><strong>SmartTrolley</strong><small>SMART SHOPPING, SMARTER CHOICES</small></span>
        </div>
        <div className="rk-user">
          <span className="rk-avatar" aria-hidden="true">●</span>
          <span className="rk-date"><strong>{user?.full_name || "Shopper"}</strong><small>Customer ID: {user?.customer_id || "Loading…"}</small></span>
          <button type="button" className="rk-back-button" onClick={() => navigate("/shopping")}>Back to shopping</button>
        </div>
      </header>

      <section className="rk-hero" aria-label="Personalized recommendations">
        <div className="rk-hero-copy">
          <span className="rk-eyebrow"><span>✦</span> SMART PICKS FOR YOU</span>
          <h1>Recommended <em>for You</em></h1>
          <p>Products suggested from your own purchase history and preferences.</p>
          <div className="rk-hero-line"><span /><span /></div>
        </div>
        <div className="rk-hero-image" role="img" aria-label="Fresh vegetables and groceries" />
        <div className="rk-hero-stamp"><span>♧</span><strong>Smart Picks</strong><small>For your basket</small></div>
      </section>

      <section className="rk-products-section">
        <div className="rk-section-heading">
          <div><h2>Recommended products</h2><p>These results come from your customer-specific recommendation service.</p></div>
          <span className="rk-count">{products.length} personalized picks</span>
        </div>
        {loading && <p className="rk-empty-state" role="status">Loading your personalized recommendations…</p>}
        {!loading && loadError && <p className="rk-empty-state" role="status">{loadError}</p>}
        {!loading && !loadError && products.length > 0 && (
          <div className="rk-product-grid">
            {products.map((product) => (
              <article className={`rk-product-card ${selectedId === product.id ? "is-selected" : ""}`} key={product.id}>
                <div className="rk-product-image-wrap"><img className="rk-product-image" src={product.image} alt={product.category} loading="lazy" /></div>
                <div className="rk-product-content">
                  <span className="rk-category"><span aria-hidden="true">✿</span>{product.category}</span>
                  <h3 title={product.name}>{product.name}</h3>
                  <strong className="rk-price">{money(product.price)}</strong>
                  <p className="rk-benefit"><span aria-hidden="true">✦</span>{product.reason}</p>
                  <span className="rk-badge">Personalized pick</span>
                  <button className="rk-select-button" type="button" onClick={() => { setSelectedId(product.id); setMessage(`${product.name} selected · Aisle: ${product.aisle}`); }}>
                    <span aria-hidden="true">⌖</span>{selectedId === product.id ? "Selected" : "Select product"}<span className="rk-button-arrow" aria-hidden="true">→</span>
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
        <div className={`rk-status ${message ? "visible" : ""}`} role="status" aria-live="polite">
          <span aria-hidden="true">✓</span><span>{message || "Select a recommended product to view its aisle."}</span>
          {selectedProduct && <button type="button" onClick={() => { setSelectedId(""); setMessage(""); }}>Clear selection</button>}
        </div>
      </section>
      <footer className="rk-footer"><strong>🛒 SmartTrolley</strong><span>Personalized choices · Easier shopping</span><button type="button" onClick={() => navigate("/shopping")}>Shopping bill →</button></footer>
    </main>
  );
}
