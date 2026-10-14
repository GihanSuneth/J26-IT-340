import { useEffect, useMemo, useState } from "react";
import "./App.css";

// Illustrative demo prices only. The API returns recommendation data, not verified prices.
const initialProducts = [
  {
    id: "P00760",
    name: "Kpo Baked Beans 425g",
    category: "Canned & Preserved Food",
    score: 0.370077,
    price: 450,
  },
  {
    id: "P00300",
    name: "Sprite Necto 400ml",
    category: "Beverages - Soft Drinks",
    score: 0.362392,
    price: 180,
  },
  {
    id: "P01048",
    name: "Marina Sunflower Oil 500ml",
    category: "Cooking Oil & Fats",
    score: 0.359685,
    price: 650,
  },
  {
    id: "P00993",
    name: "Diamond Margarine 5000ml",
    category: "Cooking Oil & Fats",
    score: 0.322364,
    price: 1250,
  },
  {
    id: "P01049",
    name: "Marina Sunflower Oil 500ml",
    category: "Cooking Oil & Fats",
    score: 0.305034,
    price: 650,
  },
];

const API_BASE_URL = "http://127.0.0.1:8000/c4/recommendations";

function App() {
  // customerId is what the user is editing; activeCustomerId is the ID currently queried.
  const [customerId, setCustomerId] = useState("C0118");
  const [activeCustomerId, setActiveCustomerId] = useState("C0118");
  const [products, setProducts] = useState([]);
  const [recommendationStatus, setRecommendationStatus] = useState("loading");
  const [recommendationError, setRecommendationError] = useState("");

  const [cart, setCart] = useState([]);
  const [productName, setProductName] = useState("");
  const [category, setCategory] = useState("Groceries");
  const [price, setPrice] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    async function loadRecommendations() {
      setRecommendationStatus("loading");
      setRecommendationError("");
      setProducts([]);

      try {
        const encodedCustomerId = encodeURIComponent(activeCustomerId);
        const response = await fetch(`${API_BASE_URL}/${encodedCustomerId}`, {
          signal: controller.signal,
        });

        if (!response.ok) {
          let detail = `API request failed (${response.status})`;
          try {
            const errorData = await response.json();
            if (errorData.detail) detail = errorData.detail;
          } catch {
            // Keep the default error if the response isn't JSON.
          }
          throw new Error(detail);
        }

        const data = await response.json();
        if (!Array.isArray(data.recommendations)) {
          throw new Error("The API response does not contain a recommendations list.");
        }

        const apiProducts = data.recommendations.map((item) => {
          const existing = initialProducts.find(
            (product) => product.id === item.product_id
          );

          return {
            id: item.product_id,
            name: item.product_name,
            category: item.category,
            score: item.score,
            // Demo prices are matched by product ID; unknown products use 0.
            price: existing?.price ?? 0,
            pastPurchaseCount: item.past_purchase_count,
            daysSinceLastPurchase: item.days_since_last_purchase,
          };
        });

        setProducts(apiProducts);
        setRecommendationStatus("success");
      } catch (error) {
        if (error.name === "AbortError") return;
        console.error("Could not load recommendations:", error);
        setProducts([]);
        setRecommendationError(error.message || "Unable to load recommendations.");
        setRecommendationStatus("error");
      }
    }

    loadRecommendations();
    return () => controller.abort();
  }, [activeCustomerId]);

  const handleCustomerSubmit = (event) => {
    event?.preventDefault();
    const cleanCustomerId = customerId.trim();

    if (!cleanCustomerId) {
      setMessage("Enter a customer ID, for example C0118.");
      return;
    }

    setCustomerId(cleanCustomerId);
    if (cleanCustomerId === activeCustomerId) {
      // Allow the user to retry the current customer's request.
      setActiveCustomerId("");
      window.setTimeout(() => setActiveCustomerId(cleanCustomerId), 0);
    } else {
      setActiveCustomerId(cleanCustomerId);
    }
    setMessage(`Loading recommendations for ${cleanCustomerId}.`);
  };

  // Add a recommended product to the bill.
  const addToCart = (product) => {
    setCart((currentCart) => {
      const existing = currentCart.find((item) => item.id === product.id);
      if (existing) {
        return currentCart.map((item) =>
          item.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      }
      return [...currentCart, { ...product, quantity: 1 }];
    });
    setMessage(`${product.name} added to your bill.`);
  };

  // Increase or decrease an item's quantity.
  const updateQuantity = (id, change) => {
    setCart((currentCart) =>
      currentCart
        .map((item) =>
          item.id === id ? { ...item, quantity: item.quantity + change } : item
        )
        .filter((item) => item.quantity > 0)
    );
  };

  // Remove one product completely from the bill.
  const removeFromCart = (id) => {
    const removedItem = cart.find((item) => item.id === id);
    setCart((currentCart) => currentCart.filter((item) => item.id !== id));
    if (removedItem) setMessage(`${removedItem.name} removed from your bill.`);
  };

  // Add a product manually.
  const addManualProduct = (event) => {
    event.preventDefault();
    const cleanName = productName.trim();
    const cleanCategory = category.trim();
    const unitPrice = Number(price);
    const itemQuantity = Number(quantity);

    if (
      !cleanName ||
      !cleanCategory ||
      price.trim() === "" ||
      !Number.isFinite(unitPrice) ||
      unitPrice < 0 ||
      !Number.isInteger(itemQuantity) ||
      itemQuantity < 1
    ) {
      setMessage("Enter a product name, category, valid price and quantity.");
      return;
    }

    const newProduct = {
      id: `MANUAL-${Date.now()}`,
      name: cleanName,
      category: cleanCategory,
      price: unitPrice,
      score: null,
    };

    setCart((currentCart) => [
      ...currentCart,
      { ...newProduct, quantity: itemQuantity },
    ]);
    setProductName("");
    setPrice("");
    setQuantity("1");
    setMessage(`${cleanName} added to your bill.`);
  };

  const total = useMemo(
    () => cart.reduce((sum, item) => sum + item.price * item.quantity, 0),
    [cart]
  );
  const itemCount = cart.reduce((sum, item) => sum + item.quantity, 0);
  const formatLKR = (amount) =>
    `LKR ${amount.toLocaleString("en-LK", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;

  return (
    <div className="trolley-app">
      <header className="topbar">
        <div className="brand">
          <div className="brand-icon">S</div>
          <div>
            <h1>SmartTrolley</h1>
            <p>Personalized shopping assistant</p>
          </div>
        </div>
        <div className="demo-badge">PP1 DEMO</div>
      </header>

      <main className="dashboard">
        <section className="welcome">
          <div>
            <p className="eyebrow">YOUR SMART SHOPPING EXPERIENCE</p>
            <h2>Welcome to your trolley</h2>
            <p className="welcome-description">
              Discover your recommendations and manage your shopping bill in one place.
            </p>
          </div>
          <div className="welcome-icon">🛒</div>
        </section>

        <section className="customer-selector panel">
          <div className="panel-heading">
            <div className="panel-icon">👤</div>
            <div>
              <h2>Choose customer</h2>
              <p>Enter a customer ID from the purchase-history dataset.</p>
            </div>
          </div>
          <form className="customer-form" onSubmit={handleCustomerSubmit}>
            <label htmlFor="customer-id">
              Customer ID
              <input
                id="customer-id"
                type="text"
                value={customerId}
                onChange={(event) => setCustomerId(event.target.value)}
                placeholder="e.g. C0118"
                autoComplete="off"
                required
              />
            </label>
            <button className="primary-button" type="submit">
              Load recommendations
            </button>
          </form>
          <p className="product-id">Currently viewing customer: {activeCustomerId || customerId}</p>
        </section>

        <section className="section-heading">
          <div>
            <p className="eyebrow">PERSONALIZED FOR YOU</p>
            <h2>Recommended products</h2>
            <p>Products ranked by your recommendation model.</p>
          </div>
          <span className="product-count">{products.length} products</span>
        </section>

        {recommendationStatus === "loading" && (
          <p className="recommendation-status" role="status">
            Loading personalized recommendations for {activeCustomerId || customerId}...
          </p>
        )}

        {recommendationStatus === "error" && (
          <div className="recommendation-status error" role="alert">
            Could not load recommendations for {activeCustomerId || customerId}. {recommendationError}
            <button
              type="button"
              className="secondary-button"
              onClick={handleCustomerSubmit}
            >
              Try again
            </button>
          </div>
        )}

        {recommendationStatus === "success" && products.length === 0 && (
          <p className="recommendation-status" role="status">
            No recommendations are available for this customer yet.
          </p>
        )}

        <section className="product-grid">
          {products.map((product) => (
            <article className="product-card" key={product.id}>
              <div className="product-visual">🛍️</div>
              <div className="product-details">
                <span className="category-label">{product.category}</span>
                <h3>{product.name}</h3>
                <p className="product-id">{product.id}</p>
                {typeof product.daysSinceLastPurchase === "number" && (
                  <p className="product-id">
                    Last purchased {product.daysSinceLastPurchase} days ago
                  </p>
                )}
                <div className="product-card-bottom">
                  <strong>{formatLKR(product.price)}</strong>
                  <button
                    type="button"
                    className="primary-button"
                    onClick={() => addToCart(product)}
                  >
                    + Add
                  </button>
                </div>
              </div>
            </article>
          ))}
        </section>

        <div className="main-columns">
          <section className="panel manual-panel">
            <div className="panel-heading">
              <div className="panel-icon">＋</div>
              <div>
                <h2>Add a product manually</h2>
                <p>Add an item that is not in the recommendation list.</p>
              </div>
            </div>

            <form onSubmit={addManualProduct} className="manual-form">
              <label>
                Product name
                <input
                  value={productName}
                  onChange={(event) => setProductName(event.target.value)}
                  placeholder="e.g. White rice 1kg"
                  required
                />
              </label>
              <label>
                Category
                <input
                  value={category}
                  onChange={(event) => setCategory(event.target.value)}
                  placeholder="e.g. Rice & Grains"
                  required
                />
              </label>
              <div className="form-row">
                <label>
                  Unit price (LKR)
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={price}
                    onChange={(event) => setPrice(event.target.value)}
                    placeholder="250.00"
                    required
                  />
                </label>
                <label>
                  Quantity
                  <input
                    type="number"
                    min="1"
                    step="1"
                    value={quantity}
                    onChange={(event) => setQuantity(event.target.value)}
                    required
                  />
                </label>
              </div>
              <button className="primary-button full-button" type="submit">
                Add product to bill
              </button>
            </form>
          </section>

          <section className="panel bill-panel">
            <div className="bill-heading">
              <div>
                <p className="eyebrow">YOUR PURCHASE</p>
                <h2>Shopping bill</h2>
              </div>
              <span className="cart-count">{itemCount} items</span>
            </div>

            {cart.length === 0 ? (
              <div className="empty-cart">
                <div className="empty-cart-icon">🛒</div>
                <h3>Your trolley is empty</h3>
                <p>Add a recommended or manual product to get started.</p>
              </div>
            ) : (
              <div className="cart-list">
                {cart.map((item) => (
                  <div className="cart-item" key={item.id}>
                    <div className="cart-item-info">
                      <h3>{item.name}</h3>
                      <p>{formatLKR(item.price)} each</p>
                      <div className="quantity-controls">
                        <button
                          type="button"
                          aria-label={`Decrease ${item.name} quantity`}
                          onClick={() => updateQuantity(item.id, -1)}
                          disabled={item.quantity <= 1}
                        >
                          −
                        </button>
                        <span>{item.quantity}</span>
                        <button
                          type="button"
                          aria-label={`Increase ${item.name} quantity`}
                          onClick={() => updateQuantity(item.id, 1)}
                        >
                          +
                        </button>
                      </div>
                      <button
                        type="button"
                        className="remove-item-button"
                        onClick={() => removeFromCart(item.id)}
                      >
                        Remove
                      </button>
                    </div>
                    <strong>{formatLKR(item.price * item.quantity)}</strong>
                  </div>
                ))}
              </div>
            )}

            <div className="bill-summary">
              <div className="summary-line">
                <span>Total units</span>
                <span>{itemCount}</span>
              </div>
              <div className="grand-total">
                <span>Grand total</span>
                <strong>{formatLKR(total)}</strong>
              </div>
              <button
                type="button"
                className="clear-button"
                onClick={() => {
                  setCart([]);
                  setMessage("Shopping bill cleared.");
                }}
                disabled={cart.length === 0}
              >
                Clear bill
              </button>
            </div>
          </section>
        </div>

        {message && (
          <div className="status-message" role="status">
            {message}
            <button
              type="button"
              onClick={() => setMessage("")}
              aria-label="Dismiss message"
            >
              ×
            </button>
          </div>
        )}

        <p className="prototype-note">
          Prototype demonstration only. Product prices are illustrative demo values,
          not verified current supermarket prices. Recommendations are loaded from
          the Component 4 API for the selected customer when the backend is available.
        </p>
      </main>
    </div>
  );
}

export default App;
