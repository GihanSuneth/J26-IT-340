import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ShoppingPage.css";

const API = "http://127.0.0.1:8001";
const CATEGORIES = [
  ["Beverages - Malt & Coffee","☕","photo-1512568400610-62da28bc8a13"],
  ["Beverages - Soft Drinks","🥤","photo-1581636625402-29b2a704ef13"],
  ["Beverages - Tea","🍵","photo-1544787219-7f47ccb76574"],
  ["Biscuits","🍪","photo-1558961363-fa8fdf82db35"],
  ["Canned & Preserved Food","🥫","photo-1584269600464-37b1b58a9fe7"],
  ["Chocolate & Confectionery","🍫","photo-1548907040-4d42c2e2d4c8"],
  ["Cooking Oil & Fats","🫒","photo-1474979266404-7eaacbcd87c5"],
  ["Dairy - Liquid & Yogurt","🥛","photo-1563636619-e9143da7973b"],
  ["Dairy - Milk Powder","🥛","photo-1628088062854-d1870b4553da"],
  ["Flour & Baking","🥣","photo-1627485937980-221c88ac04f9"],
  ["Household - Cleaning","🧽","photo-1585421514738-01798e348b17"],
  ["Household - Laundry","🧺","photo-1517677208171-0bc6725a3e60"],
  ["Noodles & Pasta","🍝","photo-1551183053-bf91a1d81141"],
  ["Personal Care - Bath & Soap","🧼","photo-1608248543803-ba4f8c70ae0b"],
  ["Personal Care - Hair Care","🧴","photo-1527799820374-dcf8d9d4a388"],
  ["Personal Care - Oral Care","🪥","photo-1609840114035-3c981b782dfe"],
  ["Rice & Grains","🌾","photo-1586201375761-83865001e31c"],
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

export default function ShoppingPage() {
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
        const cats = Array.isArray(cd) ? cd : cd.categories || [];
        setCatalogue(normalized);
        setCategories(cats.length ? cats : [...new Set(normalized.map((x) => x.category))]);
        setActiveCategory(cats[0] || normalized[0]?.category || "");
      } catch (e) {
        if (e.name !== "AbortError") setError(`${e.message || "Catalogue could not load."} Ensure the backend is running at ${API}.`);
      } finally { setLoading(false); }
    })();
    return () => ctrl.abort();
  }, []);

  const products = useMemo(() => catalogue.filter((x) =>
    (!activeCategory || x.category === activeCategory) &&
    (!search.trim() || `${x.name} ${x.category} ${x.id}`.toLowerCase().includes(search.trim().toLowerCase()))
  ), [catalogue, activeCategory, search]);
  const selected = catalogue.find((x) => x.id === selectedId);
  const itemCount = cart.reduce((sum, x) => sum + x.quantity, 0);
  const total = cart.reduce((sum, x) => sum + Number(x.price) * x.quantity, 0);
  const categoryInfo = (name) => CATEGORIES.find((x) => x.name === name) ||
    CATEGORIES.find((x) => name.toLowerCase().includes(x.name.split(" ")[0].toLowerCase())) || CATEGORIES[16];

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
    add(selected, qty); setSelectedId(""); setQuantity("1");
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
        <section className="shop-catalogue">
          <div className="shop-section-title"><div><span className="shop-eyebrow">GROCERY CATALOGUE</span><h2>Choose a category</h2></div><label className="shop-search"><span>⌕</span><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search groceries..." aria-label="Search groceries" /></label></div>
          <div className="shop-category-grid">{categories.map((cat) => { const info = categoryInfo(cat); return <button key={cat} type="button" className={`shop-category-tile ${activeCategory === cat ? "active" : ""}`} onClick={() => { setActiveCategory(cat); setSelectedId(""); }}><img src={info.image} alt="" loading="lazy" /><span className="shop-category-icon">{info.icon}</span><span className="shop-category-name">{cat}</span></button>; })}</div>
          <div className="shop-products-heading"><h3>{activeCategory || "All products"}</h3><span>{products.length} products</span></div>
          {loading && <div className="shop-state">Loading grocery catalogue…</div>}
          {error && <div className="shop-state shop-error" role="alert">{error}</div>}
          {!loading && !error && products.length === 0 && <div className="shop-state">No products found. Try another category or search term.</div>}
          <div className="shop-product-grid">{products.slice(0, 8).map((product) => { const info = categoryInfo(product.category); return <article className="shop-product-card" key={product.id}><div className="shop-product-photo"><img src={info.image} alt="" loading="lazy" /><span>{info.icon}</span></div><div className="shop-product-info"><small>{product.category}</small><h4>{product.name}</h4><p>{product.available ? "Available" : "Check availability"}</p><div className="shop-product-bottom"><strong>{product.price != null ? money(product.price) : "Price unavailable"}</strong><button type="button" onClick={() => add(product)} disabled={!product.available || product.price == null}>＋ Add</button></div></div></article>; })}</div>
          <section className="shop-manual-panel"><div className="shop-manual-heading"><span>＋</span><div><h3>Add a product manually</h3><p>Select a product from the catalogue and choose the quantity.</p></div></div>
            <form onSubmit={addSelected} className="shop-manual-form">
              <label>Category<select value={activeCategory} onChange={(e) => { setActiveCategory(e.target.value); setSelectedId(""); }}>{categories.map((cat) => <option key={cat} value={cat}>{cat}</option>)}</select></label>
              <label className="shop-product-select">Product<select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} required><option value="">Select a product</option>{catalogue.filter((x) => x.category === activeCategory).map((x) => <option key={x.id} value={x.id}>{x.name} — {x.price != null ? money(x.price) : "Price unavailable"}</option>)}</select></label>
              <label className="shop-qty-input">Quantity<input type="number" min="1" step="1" value={quantity} onChange={(e) => setQuantity(e.target.value)} required /></label>
              <button type="submit" disabled={!selected || !selected.available || selected.price == null}>Add to bill</button>
            </form>
          </section>
        </section>
        <aside className="shop-bill-panel">
          <div className="shop-bill-header"><div><span className="shop-eyebrow">YOUR PURCHASE</span><h2>Shopping bill</h2><p>Review your selected items</p></div><span className="shop-item-count">{itemCount} items</span></div>
          <div className="shop-bill-scroll">{cart.length === 0 ? <div className="shop-empty-bill"><span>🛒</span><h3>Your trolley is empty</h3><p>Add products from the catalogue to begin shopping.</p></div> : cart.map((item) => { const info = categoryInfo(item.category); return <div className="shop-bill-item" key={item.id}><img src={info.image} alt="" /><div className="shop-bill-item-copy"><strong>{item.name}</strong><small>{money(item.price)} each</small><div className="shop-quantity"><button type="button" aria-label={`Decrease ${item.name}`} disabled={item.quantity <= 1} onClick={() => changeQty(item.id, -1)}>−</button><span>{item.quantity}</span><button type="button" aria-label={`Increase ${item.name}`} onClick={() => changeQty(item.id, 1)}>＋</button></div></div><div className="shop-bill-item-total"><strong>{money(item.price * item.quantity)}</strong><button type="button" className="shop-remove" onClick={() => setCart((old) => old.filter((x) => x.id !== item.id))} aria-label={`Remove ${item.name}`}>×</button></div></div>; })}</div>
          <div className="shop-bill-footer"><div className="shop-bill-summary"><span>Items</span><strong>{itemCount}</strong></div><div className="shop-bill-total"><span>Grand total</span><strong>{money(total)}</strong></div><div className="shop-bill-actions"><button className="shop-clear-button" type="button" disabled={!cart.length} onClick={() => { setCart([]); setMessage("Shopping bill cleared."); }}>Clear bill</button><button className="shop-checkout-button" type="button" disabled={!cart.length} onClick={() => setMessage("Checkout can be connected later.")}>Review bill →</button></div><p className="shop-bill-note">Prices are shown from the store catalogue.</p></div>
        </aside>
      </div>
      {message && <div className="shop-message" role="status"><span>{message}</span><button type="button" onClick={() => setMessage("")} aria-label="Dismiss">×</button></div>}
    </main>
    <footer className="shop-footer"><strong>🛒 SmartTrolley</strong><span>Personalized choices · Easier shopping</span><button type="button" onClick={() => navigate("/recommendations")}>Recommendations →</button></footer>
  </div>;
}
