
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import "./AuthShared.css";
import "./Register.css";

const API_URL = "http://127.0.0.1:8001";

export default function Register() {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`${API_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          full_name: fullName.trim(),
          email: email.trim(),
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Registration failed. Please check your details."
        );
      }

      if (!data.access_token || !data.user) {
        throw new Error(
          "Registration succeeded, but the server did not return the expected login details."
        );
      }

      navigate("/login", {
        replace: true,
        state: {
         registered: true,
         email: email.trim(),
  },
});
    } catch (err) {
      setError(err.message || "Cannot connect to the server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-screen">
      <div className="auth-background" aria-hidden="true" />

      <section className="auth-layout">
        <aside className="auth-intro">
          <Link to="/login" className="auth-brand">
            <span className="auth-brand-icon">S</span>
            <span>
              <strong>SmartTrolley</strong>
              <small>SMART SHOPPING, SMARTER CHOICES</small>
            </span>
          </Link>

          <div className="auth-intro-copy">
            <span className="auth-kicker">JOIN SMARTTROLLEY</span>
            <h1>
              A smarter way
              <br />
              to <span>shop every day.</span>
            </h1>
            <p>
              Create your account to enjoy a more convenient shopping
              experience with personalized product recommendations
              and smart billing.
            </p>

            <div className="auth-benefits">
              <div>
                <span className="benefit-icon">✦</span>
                <span>
                  <strong>Personalized picks</strong>
                  <small>Discover products based on your purchases.</small>
                </span>
              </div>

              <div>
                <span className="benefit-icon">▣</span>
                <span>
                  <strong>Simple smart billing</strong>
                  <small>Keep track of your trolley total.</small>
                </span>
              </div>

              <div>
                <span className="benefit-icon">↗</span>
                <span>
                  <strong>Shop with ease</strong>
                  <small>Find the groceries you need faster.</small>
                </span>
              </div>
            </div>
          </div>

          <p className="auth-footer-note">
            INTELLIGENT SHOPPING · PERSONALIZED EXPERIENCES
          </p>
        </aside>

        <section className="auth-card-wrap">
          <form
            className="auth-card auth-card--register"
            onSubmit={handleSubmit}
          >
            <div className="auth-card-brand">
              <span className="auth-card-logo">S</span>
              <strong>
                Smart<span>Trolley</span>
              </strong>
              <small>SMART SHOPPING, SMARTER CHOICES</small>
            </div>

            <div className="auth-heading">
              <h2>Create Account</h2>
              <p>
                Join SmartTrolley and make your next shopping
                experience smarter.
              </p>
            </div>

            <label htmlFor="register-name">Full name</label>
            <div className="auth-input-wrap">
              <span aria-hidden="true">♙</span>
              <input
                id="register-name"
                type="text"
                placeholder="Enter your full name"
                autoComplete="name"
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required
                minLength={2}
                maxLength={100}
              />
            </div>

            <label htmlFor="register-email">Email address</label>
            <div className="auth-input-wrap">
              <span aria-hidden="true">✉</span>
              <input
                id="register-email"
                type="email"
                placeholder="Enter your email address"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <label htmlFor="register-password">Password</label>
            <div className="auth-input-wrap">
              <span aria-hidden="true">▣</span>
              <input
                id="register-password"
                type={showPassword ? "text" : "password"}
                placeholder="Create a password (8+ characters)"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
                minLength={8}
                maxLength={128}
              />
              <button
                className="password-toggle"
                type="button"
                onClick={() => setShowPassword((value) => !value)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>

            {error && (
              <p className="auth-error" role="alert">
                {error}
              </p>
            )}

            <button className="auth-submit" type="submit" disabled={loading}>
              {loading ? "Creating account..." : "Create Account"}
              {!loading && <span aria-hidden="true">→</span>}
            </button>

            <div className="auth-divider">
              <span />
              <small>YOUR SMART SHOPPING STARTS HERE</small>
              <span />
            </div>

            <p className="auth-switch">
              Already have an account? <Link to="/login">Sign in</Link>
            </p>
          </form>
        </section>
      </section>
    </main>
  );
}
