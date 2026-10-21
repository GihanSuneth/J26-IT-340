/**
 * App.jsx - Top-level layout of the trolley screen; hosts the four feature panels.
 * Owner: develop (shared - all four members review)
 */

import { NavLink } from "react-router-dom";
import { AppRoutes } from "./routes.jsx";

export default function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <a className="brand" href="/shopping" aria-label="Smart Trolley home">
          <span className="brand-mark" aria-hidden="true">
            ST
          </span>
          <span>
            <strong>Smart Trolley</strong>
            <small>In-store assistant</small>
          </span>
        </a>
        <nav className="primary-nav" aria-label="Main navigation">
          <NavLink
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            to="/shopping"
          >
            Shopping
          </NavLink>
          <NavLink
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            to="/checkout"
          >
            Checkout
          </NavLink>
        </nav>
      </header>
      <AppRoutes />
    </div>
  );
}
