/**
 * routes.jsx - Screen routing (shopping, checkout, idle).
 * Owner: develop (shared - all four members review)
 */

import { Navigate, Route, Routes } from "react-router-dom";

function ShoppingScreen() {
  return (
    <main className="screen">
      <p className="eyebrow">YOUR SHOPPING SESSION</p>
      <h1>Shopping</h1>
      <p className="screen-description">
        Your trolley display is ready. Shopping and navigation features can be
        connected here.
      </p>
      <section className="feature-placeholder" aria-label="Shopping features">
        <div className="placeholder-icon" aria-hidden="true">
          +
        </div>
        <div>
          <h2>Start shopping</h2>
          <p>Validated items, your cart, and in-store guidance will appear here.</p>
        </div>
      </section>
    </main>
  );
}

function CheckoutScreen() {
  return (
    <main className="screen">
      <p className="eyebrow">READY WHEN YOU ARE</p>
      <h1>Checkout</h1>
      <p className="screen-description">
        Review and pay for your items at the end of your shopping trip.
      </p>
      <section className="feature-placeholder" aria-label="Checkout status">
        <div className="placeholder-icon" aria-hidden="true">
          $
        </div>
        <div>
          <h2>Your bill will appear here</h2>
          <p>Billing details will be shown when checkout is connected.</p>
        </div>
      </section>
    </main>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Navigate replace to="/shopping" />} />
      <Route path="/shopping" element={<ShoppingScreen />} />
      <Route path="/checkout" element={<CheckoutScreen />} />
      <Route path="*" element={<Navigate replace to="/shopping" />} />
    </Routes>
  );
}
