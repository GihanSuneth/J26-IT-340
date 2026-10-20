import { useEffect, useMemo, useState } from "react";
import "./App.css";

// Backend origin only; endpoint paths are defined in loadData().
const API_BASE = "http://127.0.0.1:8001";

function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem("user") || "null");
  } catch {
    return null;
  }
}

function App() {
  const storedUser = getStoredUser();
  const loggedInCustomerId = storedUser?.customer_id || "";

  const [products, setProducts] = useState([]);
  const [customerIdInput, setCustomerIdInput] = useState(loggedInCustomerId);
  const [customerId, setCustomerId] = useState(loggedInCustomerId);
  const [catalogue, setCatalogue] = useState([]);
  const [categories, setCategories] = useState([]);
  const [recommendationStatus, setRecommendationStatus] = useState("loading");
  const [catalogueStatus, setCatalogueStatus] = useState("loading");
  const [cart, setCart] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedProductId, setSelectedProductId] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadData() {
      setRecommendationStatus("loading");
      setCatalogueStatus("loading");
      setMessage("");

      try {
        const [recommendationResponse, categoryResponse, catalogueResponse] =
          await Promise.all([
            customerId
              ? fetch(`${API_BASE}/c4/recommendations/${encodeURIComponent(customerId)}`, {
                  signal: controller.signal,
                })
              : Promise.resolve(null),
            fetch(`${API_BASE}/c4/catalog/categories`, { signal: controller.signal }),
            fetch(`${API_BASE}/c4/catalog/products`, { signal: controller.signal }),
          ]);

        if (recommendationResponse && !recommendationResponse.ok) {
          throw new Error(`Recommendations request failed (HTTP ${recommendationResponse.status}).`);
        }
        if (!categoryResponse.ok) {
          throw new Error(`Categories request failed (HTTP ${categoryResponse.status}).`);
        }
        if (!catalogueResponse.ok) {
          throw new Error(`Catalogue request failed (HTTP ${catalogueResponse.status}).`);
        }

        const [recommendationData, categoryData, catalogueData] = await Promise.all([
          recommendationResponse
            ? recommendationResponse.json()
            : Promise.resolve({ recommendations: [] }),
          categoryResponse.json(),
          catalogueResponse.json(),
        ]);

        const rawItems = Array.isArray(catalogueData)
          ? catalogueData
          : catalogueData.products || [];
        const normalizeId = (value) => String(value ?? "").trim();
        const normalizeProduct = (item) => {
          const stockStatus = item.stock_status ?? item.Stock_Status ??
            (item.available === true ? "Available" : "Unknown");
          const rawPrice = item.price ?? item.price_lkr ?? item.Price_LKR ?? null;
          return {
            id: normalizeId(item.id ?? item.product_id ?? item.Item_ID),
            name: item.name ?? item.item_name ?? item.Item_Name ?? "Unnamed product",
            category: item.category ?? item.Category ?? "Uncategorized",
            price: rawPrice == null || rawPrice === "" ? null : Number(rawPrice),
            stock_status: stockStatus,
            available: typeof item.available === "boolean"
              ? item.available
              : String(stockStatus).toLowerCase() === "available",
          };
        };
        const normalizedCatalogue = rawItems.map(normalizeProduct);
        const catalogueById = new Map(normalizedCatalogue.map((item) => [item.id, item]));

        const recommendationItems = recommendationData.recommendations || [];
        const mappedRecommendations = recommendationItems.map((item) => {
          const id = normalizeId(item.product_id ?? item.id);
          const catalogItem = catalogueById.get(id);
          return {
            id,
            name: catalogItem?.name ?? item.product_name ?? id,
            category: catalogItem?.category ?? item.category ?? "Uncategorized",
            price: catalogItem?.price ?? null,
            available: catalogItem?.available ?? false,
            stock_status: catalogItem?.stock_status ?? "Unknown",
            score: item.score,
            pastPurchaseCount: item.past_purchase_count,
            daysSinceLastPurchase: item.days_since_last_purchase,
          };
        });

        setCatalogue(normalizedCatalogue);
        setCategories(Array.isArray(categoryData) ? categoryData : categoryData.categories || []);
        setProducts(mappedRecommendations);
        setRecommendationStatus("success");
        setCatalogueStatus("success");
      } catch (error) {
        if (error.name === "AbortError") return;
        console.error("SmartTrolley data loading failed:", error);
        setRecommendationStatus("error");
        setCatalogueStatus("error");
        setMessage(error.message || "Could not connect to the backend.");
      }
    }

    loadData();
    return () => controller.abort();
  }, [customerId]);

  const loadCustomerRecommendations = (event) => {
    event.preventDefault();
    const cleanedId = customerIdInput.trim();
    if (!cleanedId) {
      setMessage("Please enter a customer ID.");
      return;
    }
    setMessage("");
    setCustomerId(cleanedId);
  };

  const productsInCategory = useMemo(() => {
    if (!selectedCategory) return [];
    return catalogue.filter((item) => item.category === selectedCategory);
  }, [catalogue, selectedCategory]);

  const selectedProduct = useMemo(
    () => catalogue.find((item) => item.id === selectedProductId) || null,
    [catalogue, selectedProductId]
  );

  const formatLKR = (amount) =>
    `LKR ${Number(amount).toLocaleString("en-LK", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;

  const addToCart = (product) => {
    if (product.price == null || !Number.isFinite(Number(product.price))) {
      setMessage(`A catalogue price is not available for ${product.name}. It was not added.`);
      return;
    }
    if (!product.available) {
      setMessage(`${product.name} is not marked as available in the catalogue.`);
      return;
    }
    setCart((current) => {
      const existing = current.find((item) => item.id === product.id);
      if (existing) {
        return current.map((item) => item.id === product.id
          ? { ...item, quantity: item.quantity + 1 }
          : item);
      }
      return [...current, { ...product, quantity: 1 }];
    });
    setMessage(`${product.name} added to your bill.`);
  };

  const updateQuantity = (id, change) => {
    setCart((current) => current
      .map((item) => item.id === id ? { ...item, quantity: item.quantity + change } : item)
      .filter((item) => item.quantity > 0));
  };

  const removeFromCart = (id) => {
    const item = cart.find((product) => product.id === id);
    setCart((current) => current.filter((product) => product.id !== id));
    if (item) setMessage(`${item.name} removed from your bill.`);
  };

  const addManualProduct = (event) => {
    event.preventDefault();
    const itemQuantity = Number(quantity);
    if (!selectedProduct) {
      setMessage("Please select a product from the catalogue.");
      return;
    }
    if (!Number.isInteger(itemQuantity) || itemQuantity < 1) {
      setMessage("Please enter a valid quantity of at least 1.");
      return;
    }
    if (selectedProduct.price == null || !Number.isFinite(selectedProduct.price)) {
      setMessage("This product does not have a catalogue price, so it cannot be added.");
      return;
    }
    if (!selectedProduct.available) {
      setMessage("This product is not marked as available in the catalogue.");
      return;
    }
    setCart((current) => {
      const existing = current.find((item) => item.id === selectedProduct.id);
      if (existing) {
        return current.map((item) => item.id === selectedProduct.id
          ? { ...item, quantity: item.quantity + itemQuantity }
          : item);
      }
      return [...current, { ...selectedProduct, quantity: itemQuantity }];
    });
    setMessage(`${selectedProduct.name} added to your bill.`);
    setSelectedProductId("");
    setSelectedCategory("");
    setQuantity("1");
  };

  const total = useMemo(
    () => cart.reduce((sum, item) => sum + Number(item.price) * item.quantity, 0),
    [cart]
  );
  const itemCount = cart.reduce((sum, item) => sum + item.quantity, 0);

  return (
    <div className="trolley-app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">S</div>
          <div><h1>SmartTrolley</h1><p>Personalized shopping assistant</p></div>
        </div>
        {storedUser && (
          <div className="account-summary">
            <span>{storedUser.full_name || storedUser.email}</span>
            <span className="product-id">Customer ID: {storedUser.customer_id}</span>
          </div>
        )}
      </header>

      <main className="dashboard">
        <section className="welcome">
          <div>
            <p className="eyebrow">YOUR SMART SHOPPING EXPERIENCE</p>
            <h2>Welcome to your trolley</h2>
            <p className="welcome-description">Discover your recommendations and manage your shopping bill in one place.</p>
          </div>
          <div className="welcome-icon">🛒</div>
        </section>

        <section className="customer-selector panel">
          <form onSubmit={loadCustomerRecommendations} className="form-row">
            <label>Customer ID
              <input type="text" value={customerIdInput}
                onChange={(event) => setCustomerIdInput(event.target.value)}
                placeholder="Your customer ID" required />
            </label>
            <button className="primary-button" type="submit" disabled={recommendationStatus === "loading"}>
              {recommendationStatus === "loading" ? "Loading..." : "Load recommendations"}
            </button>
          </form>
          <p className="product-id">Showing recommendations for customer: <strong>{customerId || "Not selected"}</strong></p>
        </section>

        <section className="section-heading">
          <div><p className="eyebrow">PERSONALIZED FOR YOU</p><h2>Recommended products</h2><p>Products ranked by your recommendation model.</p></div>
          <span className="product-count">{products.length} products</span>
        </section>

        {recommendationStatus === "loading" && <p className="recommendation-status" role="status">Loading personalized recommendations...</p>}
        {recommendationStatus === "error" && <div className="recommendation-status error" role="alert">Could not load recommendations. Check that the backend is running and review the browser Console for the exact error.</div>}
        {catalogueStatus === "error" && <p className="recommendation-status error">The catalogue could not be loaded. Manual product selection is unavailable.</p>}
        {recommendationStatus === "success" && products.length === 0 && <p className="recommendation-status">No recommendations are available for this customer yet.</p>}

        <section className="product-grid">
          {products.map((product) => (
            <article className="product-card" key={product.id}>
              <div className="product-visual">🛍️</div>
              <div className="product-details">
                <span className="category-label">{product.category}</span>
                <h3>{product.name}</h3>
                <p className="product-id">{product.id}</p>
                {typeof product.daysSinceLastPurchase === "number" && <p className="product-id">Last purchased {product.daysSinceLastPurchase} days ago</p>}
                <div className="product-card-bottom">
                  <div>{product.price != null ? <strong>{formatLKR(product.price)}</strong> : <span>Price unavailable</span>}</div>
                  <button type="button" className="primary-button" onClick={() => addToCart(product)} disabled={product.price == null || !product.available}>
                    {product.price == null ? "Price unavailable" : !product.available ? "Unavailable" : "+ Add"}
                  </button>
                </div>
              </div>
            </article>
          ))}
        </section>

        <div className="main-columns">
          <section className="panel manual-panel">
            <div className="panel-heading"><div className="panel-icon">＋</div><div><h2>Add a product manually</h2><p>Select a product from the grocery catalogue.</p></div></div>
            <form onSubmit={addManualProduct} className="manual-form">
              <label>Category
                <select value={selectedCategory} onChange={(event) => { setSelectedCategory(event.target.value); setSelectedProductId(""); }} required>
                  <option value="">Select a category</option>
                  {categories.map((item) => <option value={item} key={item}>{item}</option>)}
                </select>
              </label>
              <label>Product
                <select value={selectedProductId} onChange={(event) => setSelectedProductId(event.target.value)} disabled={!selectedCategory || catalogueStatus !== "success"} required>
                  <option value="">{!selectedCategory ? "Select a category first" : "Select a product"}</option>
                  {productsInCategory.map((item) => <option value={item.id} key={item.id}>{item.name} ({item.id})</option>)}
                </select>
              </label>
              <div className="form-row">
                <label>Unit price (LKR)
                  <input type="text" value={selectedProduct?.price != null ? Number(selectedProduct.price).toLocaleString("en-LK") : ""} placeholder="Auto-filled from catalogue" readOnly />
                </label>
                <label>Quantity
                  <input type="number" min="1" step="1" value={quantity} onChange={(event) => setQuantity(event.target.value)} required />
                </label>
              </div>
              {selectedProduct && <p className="product-id">Stock status: {selectedProduct.stock_status}. A catalogue-listed price may not be the current in-store price.</p>}
              <button className="primary-button full-button" type="submit" disabled={!selectedProduct || !selectedProduct.available || selectedProduct.price == null}>Add product to bill</button>
            </form>
          </section>

          <section className="panel bill-panel">
            <div className="bill-heading"><div><p className="eyebrow">YOUR PURCHASE</p><h2>Shopping bill</h2></div><span className="cart-count">{itemCount} items</span></div>
            {cart.length === 0 ? (
              <div className="empty-cart"><div className="empty-cart-icon">🛒</div><h3>Your trolley is empty</h3><p>Add a recommended or catalogue product to get started.</p></div>
            ) : (
              <div className="cart-list">
                {cart.map((item) => (
                  <div className="cart-item" key={item.id}>
                    <div className="cart-item-info">
                      <h3>{item.name}</h3><p>{formatLKR(item.price)} each</p>
                      <div className="quantity-controls">
                        <button type="button" aria-label={`Decrease ${item.name} quantity`} onClick={() => updateQuantity(item.id, -1)} disabled={item.quantity <= 1}>−</button>
                        <span>{item.quantity}</span>
                        <button type="button" aria-label={`Increase ${item.name} quantity`} onClick={() => updateQuantity(item.id, 1)}>+</button>
                      </div>
                      <button type="button" className="remove-item-button" onClick={() => removeFromCart(item.id)}>Remove</button>
                    </div>
                    <strong>{formatLKR(item.price * item.quantity)}</strong>
                  </div>
                ))}
              </div>
            )}
            <div className="bill-summary">
              <div className="summary-line"><span>Total units</span><span>{itemCount}</span></div>
              <div className="grand-total"><span>Grand total</span><strong>{formatLKR(total)}</strong></div>
            </div>
          </section>
        </div>
        {message && <p className="message" role="status">{message}</p>}
      </main>
    </div>
  );
}

export default App;
