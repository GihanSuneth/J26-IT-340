import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";

const API = "http://127.0.0.1:8001";
const CATEGORIES = [
  ["Rice & Grains","🌾","photo-1586201375761-83865001e31c"],
  ["Fresh Produce","🥬","photo-1540420773420-3366772f4999"],
  ["Dairy - Liquid & Yogurt","🥛","photo-1563636619-e9143da7973b"],
  ["Biscuits","🍪","photo-1558961363-fa8fdf82db35"],
  ["Cooking Oil & Fats","🫒","photo-1474979266404-7eaacbcd87c5"],
  ["Beverages - Malt & Coffee","☕","photo-1512568400610-62da28bc8a13"],
  ["Beverages - Soft Drinks","🥤","photo-1581636625402-29b2a704ef13"],
  ["Beverages - Tea","🍵","photo-1544787219-7f47ccb76574"],
  ["Canned & Preserved Food","🥫","photo-1584269600464-37b1b58a9fe7"],
  ["Chocolate & Confectionery","🍫","photo-1548907040-4d42c2e2d4c8"],
  ["Dairy - Milk Powder","🥛","photo-1628088062854-d1870b4553da"],
  ["Flour & Baking","🥣","photo-1627485937980-221c88ac04f9"],
  ["Household - Cleaning","🧽","photo-1585421514738-01798e348b17"],
  ["Household - Laundry","🧺","photo-1517677208171-0bc6725a3e60"],
  ["Noodles & Pasta","🍝","photo-1551183053-bf91a1d81141"],
  ["Personal Care - Bath & Soap","🧼","photo-1608248543803-ba4f8c70ae0b"],
  ["Personal Care - Hair Care","🧴","photo-1527799820374-dcf8d9d4a388"],
  ["Personal Care - Oral Care","🪥","photo-1609840114035-3c981b782dfe"],
  ["Sauces & Condiments","🫙","photo-1472476443507-c7a5948772fc"],
  ["Spices & Curry Powder","🌶️","photo-1532336414038-cf19250c5757"],
  ["Sugar & Sweeteners","🍯","photo-1581441363689-1f3c3c414635"],
].map(([name, icon, photo]) => ({ name, icon, image: `https://images.unsplash.com/${photo}?auto=format&fit=crop&w=500&q=85` }));

function readUser() {
  try { return JSON.parse(localStorage.getItem("user") || "null"); }
  catch { return null; }
}
function normalizeProduct(item) {
  const stock = item.stock_status ?? item.Stock_Status ?? (item.available ? "Available" : "Unknown");
  const price = item.price ?? item.price_lkr ?? item.Price_LKR ?? null;
  return {
    id: String(item.id ?? item.product_id ?? item.Item_ID ?? ""),
    name: item.name ?? item.item_name ?? item.Item_Name ?? "Unnamed product",
    category: item.category ?? item.Category ?? "Uncategorized",
    price: price == null || price === "" ? null : Number(price),
    stock_status: stock,
    available: typeof item.available === "boolean" ? item.available : String(stock).toLowerCase() === "available",
  };
}
const money = (n) => `LKR ${Number(n).toLocaleString("en-LK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function App() {
  const navigate = useNavigate();
  const [user] = useState(readUser);
  const [catalogue, setCatalogue] = useState([]);
  const [categories, setCategories] = useState([]);
  const [activeCategory, setActiveCategory] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [cart, setCart] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [showProductDropdown, setShowProductDropdown] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    (async () => {
      try {
        const [cr, pr] = await Promise.all([
          fetch(`${API}/c4/catalog/categories`, { signal: ctrl.signal }),
          fetch(`${API}/c4/catalog/products`, { signal: ctrl.signal }),
        ]);
        if (!cr.ok) throw new Error(`Categories request failed (${cr.status}).`);
        if (!pr.ok) throw new Error(`Products request failed (${pr.status}).`);
        const [cd, pd] = await Promise.all([cr.json(), pr.json()]);
        const raw = Array.isArray(pd) ? pd : pd.products || [];
        const normalized = raw.map(normalizeProduct).filter((x) => x.id);
        const rawCategories = Array.isArray(cd) ? cd : cd.categories || [];
        const cats = rawCategories.map((cat) =>
          typeof cat === "string" ? cat : cat.name ?? cat.category ?? cat.category_name ?? ""
        ).filter(Boolean);
        setCatalogue(normalized);
        const finalCategories = cats.length ? cats : [...new Set(normalized.map((x) => x.category))];
        setCategories(finalCategories);
        setActiveCategory(finalCategories[0] || normalized[0]?.category || "");
      } catch (e) {
        if (e.name !== "AbortError") setError(`${e.message || "Catalogue could not load."} Ensure the backend is running at ${API}.`);
      } finally { setLoading(false); }
    })();
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    if (!user) navigate("/login", { replace: true });
  }, [user, navigate]);

  const products = useMemo(() => catalogue.filter((x) =>
    (!activeCategory || x.category === activeCategory) &&
    (!search.trim() || `${x.name} ${x.category} ${x.id}`.toLowerCase().includes(search.trim().toLowerCase()))
  ), [catalogue, activeCategory, search]);
  const selected = catalogue.find((x) => x.id === selectedId);
  const suggestions = catalogue.filter((x) =>
    x.category === activeCategory && search.trim() &&
    x.name.toLowerCase().includes(search.trim().toLowerCase())
  ).slice(0, 7);
  const itemCount = cart.reduce((sum, x) => sum + x.quantity, 0);
  const total = cart.reduce((sum, x) => sum + Number(x.price) * x.quantity, 0);
  const categoryInfo = (name) => {
    const normalized = String(name || "").trim().toLowerCase().replace(/\s+/g, " ");
    const exact = CATEGORIES.find((x) => x.name.trim().toLowerCase().replace(/\s+/g, " ") === normalized);
    if (exact) return exact;
    if (normalized.includes("malt") || normalized.includes("coffee")) return CATEGORIES.find((x) => x.name === "Beverages - Malt & Coffee");
    if (normalized.includes("soft drink")) return CATEGORIES.find((x) => x.name === "Beverages - Soft Drinks");
    if (normalized.includes("tea")) return CATEGORIES.find((x) => x.name === "Beverages - Tea");
    return CATEGORIES.find((x) => normalized.includes(x.name.split(" ")[0].toLowerCase())) || CATEGORIES[0];
  };

  function add(product, qty = 1) {
    if (!product || product.price == null || !Number.isFinite(product.price)) { setMessage("A valid catalogue price is unavailable."); return; }
    if (!product.available) { setMessage(`${product.name} is marked unavailable.`); return; }
    setCart((old) => {
      const found = old.find((x) => x.id === product.id);
      return found ? old.map((x) => x.id === product.id ? { ...x, quantity: x.quantity + qty } : x) : [...old, { ...product, quantity: qty }];
    });
    setMessage(`${product.name} added to your bill.`);
  }
  function addSelected(e) {
    e.preventDefault();
    const qty = Number(quantity);
    if (!selected) { setMessage("Select a product first."); return; }
    if (!Number.isInteger(qty) || qty < 1) { setMessage("Enter a quantity of at least 1."); return; }
    add(selected, qty); setSelectedId(""); setSearch(""); setQuantity("1"); setShowProductDropdown(false);
  }
  function changeQty(id, change) {
    setCart((old) => old.map((x) => x.id === id ? { ...x, quantity: x.quantity + change } : x).filter((x) => x.quantity > 0));
  }

  return <div className="shopping-kiosk">
    <header className="shop-topbar">
      <div className="shop-brand"><span className="shop-logo">🛒</span><div><strong>SmartTrolley</strong><small>SMART SHOPPING, SMARTER CHOICES</small></div></div>
      <div className="shop-header-right">
        <div className="shop-customer"><span className="shop-avatar">●</span><div><strong>{user?.full_name || user?.name || "Shopper"}</strong><small>{user?.customer_id ? `Customer ID: ${user.customer_id}` : user?.email || "Personalized shopping"}</small></div></div>
        <button className="shop-nav-button" onClick={() => navigate("/recommendations")} type="button">✦ Recommendations</button>
      </div>
    </header>
    <main className="shop-main">
      <section className="shop-welcome"><div><span className="shop-eyebrow">YOUR SMART SHOPPING EXPERIENCE</span><h1>Shop your way, <em>smarter.</em></h1><p>Choose a category, select your groceries, and watch your bill update instantly.</p></div><div className="shop-welcome-art" aria-hidden="true">🥬 🍅 🥕</div></section>
      <div className="shop-workspace">
        <aside className="shop-category-sidebar" aria-label="Grocery categories">
          <div className="shop-sidebar-heading"><span className="shop-eyebrow">CATEGORIES</span><strong>Shop by aisle</strong></div>
          <div className="shop-category-list">{categories.map((cat) => { const info = categoryInfo(cat); return <button key={cat} type="button" className={`shop-category-row ${activeCategory === cat ? "active" : ""}`} onClick={() => { setActiveCategory(cat); setSearch(""); setSelectedId(""); }}><img src={info.image} alt="" loading="lazy" /><span className="shop-category-row-icon">{info.icon}</span><span>{cat}</span><span className="shop-category-chevron">›</span></button>; })}</div>
        </aside>
        <section className="shop-catalogue shop-product-workspace">
          <div className="shop-middle-heading"><div><span className="shop-eyebrow">STEP 1 · CHOOSE ITEMS</span><h2>Find your groceries</h2><p>Choose a category on the left, then search for a product.</p></div><span className="shop-middle-count">{catalogue.filter((x) => x.category === activeCategory).length} products</span></div>
          <section className="shop-category-feature">
            <img src={categoryInfo(activeCategory).image} alt="" />
            <div><span className="shop-eyebrow">SELECTED CATEGORY</span><h3>{activeCategory || "Choose a category"}</h3><p>Search results will only include products from this category.</p></div>
            <span className="shop-feature-icon">{categoryInfo(activeCategory).icon}</span>
          </section>
          <section className="shop-manual-panel shop-quick-add-panel">
            <div className="shop-manual-heading"><span>＋</span><div><h3>Add to your trolley</h3><p>{loading ? "Loading store catalogue…" : "Search, select a match, set quantity, and add it to your bill."}</p></div></div>
            {error && <div className="shop-state shop-error" role="alert">{error}</div>}
            <form onSubmit={addSelected} className="shop-manual-form">
              <label className="shop-product-select">Search or choose product
                <div className="shop-search-control">
                  <input autoComplete="off" value={search} onFocus={() => setShowProductDropdown(true)} onChange={(e) => { setSearch(e.target.value); setSelectedId(""); setShowProductDropdown(true); }} placeholder={`Search ${activeCategory || "products"}…`} required aria-label="Search products in selected category" />
                  <button type="button" className="shop-browse-products" aria-label="Show products in this category" aria-expanded={showProductDropdown} onClick={() => setShowProductDropdown((open) => !open)}>▾</button>
                </div>
                {showProductDropdown && <div className="shop-product-suggestions" role="listbox" aria-label="Products in selected category">
                  {(search.trim() ? suggestions : catalogue.filter((product) => product.category === activeCategory).slice(0, 30)).map((product) => <button type="button" role="option" aria-selected={selectedId === product.id} key={product.id} onClick={() => { setSelectedId(product.id); setSearch(product.name); setShowProductDropdown(false); setMessage(""); }}>
                    <span className="shop-suggestion-image"><img src={categoryInfo(product.category).image} alt="" /></span><span className="shop-suggestion-copy"><strong>{product.name}</strong><small>{product.available ? "Available" : "Unavailable"}</small></span><strong className="shop-suggestion-price">{product.price != null ? money(product.price) : "Price N/A"}</strong>
                  </button>)}
                  {!loading && (search.trim() ? suggestions.length === 0 : catalogue.filter((product) => product.category === activeCategory).length === 0) && <p className="shop-no-suggestions">No products found in this category.</p>}
                </div>}
              </label>
              <label className="shop-qty-input">Quantity<input type="number" min="1" step="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} required /></label>
              <button className="shop-add-button" type="submit" disabled={!selected || !selected.available || selected.price == null}>Add to bill</button>
            </form>
            {message && <p className="shop-picker-hint" role="status">{message}</p>}
          </section>
          <section className="shop-smart-options" aria-label="Explore recommendations">
            <div className="shop-smart-options-copy"><span className="shop-smart-sparkle">✦</span><div><strong>Make your shopping smarter</strong><p>Explore personalized picks or discover meal ideas anytime.</p></div></div>
            <div className="shop-smart-option-actions">
              <button type="button" className="shop-smart-option" onClick={() => navigate("/recommendations")}><span>✦</span><span><strong>For you</strong><small>Based on your purchases</small></span><b>→</b></button>
              <button type="button" className="shop-smart-option recipe" onClick={() => setMessage("Recipe ideas will be available when the recipe recommendation component is connected.")}><span>🍲</span><span><strong>Recipe ideas</strong><small>Meals and ingredients</small></span><b>→</b></button>
            </div>
          </section>
        </section>
        <aside className="shop-bill-panel">
          <div className="shop-bill-header"><div><span className="shop-eyebrow">YOUR PURCHASE</span><h2>Shopping bill</h2><p>Review your selected items</p></div><span className="shop-item-count">{itemCount} items</span></div>
          <div className="shop-bill-scroll">{cart.length === 0 ? <div className="shop-empty-bill"><span>🛒</span><h3>Your trolley is empty</h3><p>Add products from the middle panel to begin shopping.</p></div> : cart.map((item) => { const info = categoryInfo(item.category); return <div className="shop-bill-item" key={item.id}><img src={info.image} alt="" /><div className="shop-bill-item-copy"><strong>{item.name}</strong><small>{money(item.price)} each</small><div className="shop-quantity"><button type="button" aria-label={`Decrease ${item.name}`} disabled={item.quantity <= 1} onClick={() => changeQty(item.id, -1)}>−</button><span>{item.quantity}</span><button type="button" aria-label={`Increase ${item.name}`} onClick={() => changeQty(item.id, 1)}>＋</button></div></div><div className="shop-bill-item-total"><strong>{money(item.price * item.quantity)}</strong><button type="button" className="shop-remove" onClick={() => setCart((old) => old.filter((x) => x.id !== item.id))} aria-label={`Remove ${item.name}`}>×</button></div></div>; })}</div>
          <div className="shop-bill-footer"><div className="shop-bill-summary"><span>Items</span><strong>{itemCount}</strong></div><div className="shop-bill-total"><span>Grand total</span><strong>{money(total)}</strong></div><div className="shop-bill-actions"><button className="shop-clear-button" type="button" disabled={!cart.length} onClick={() => { setCart([]); setMessage("Shopping bill cleared."); }}>Clear bill</button><button className="shop-checkout-button" type="button" disabled={!cart.length} onClick={() => setMessage("Checkout can be connected later.")}>Review bill →</button></div><p className="shop-bill-note">Prices are shown from the store catalogue.</p></div>
        </aside>
      </div>
      {message && <div className="shop-message" role="status"><span>{message}</span><button type="button" onClick={() => setMessage("")} aria-label="Dismiss">×</button></div>}
    </main>
    <footer className="shop-footer"><strong>🛒 SmartTrolley</strong><span>Personalized choices · Easier shopping</span><button type="button" onClick={() => navigate("/recommendations")}>Recommendations →</button></footer>
  </div>;
}
