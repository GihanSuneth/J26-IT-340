
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

const API_URL = "http://127.0.0.1:8001";

export default function Login() {
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
      const response = await fetch(`${API_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Login failed.");
      }

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("user", JSON.stringify(data.user));

      navigate("/shopping");
    } catch (err) {
      setError(err.message || "Cannot connect to the server.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-screen">
      <div className="auth-background" />

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
            <span className="auth-kicker">SMART RETAIL TECHNOLOGY</span>
            <h1>
              Your Smart
              <br />
              <span>Shopping Partner</span>
            </h1>
            <p>
              Experience a smarter shopping journey with
              personalized recommendations and convenient
              smart billing.
            </p>

            <div className="auth-benefits">
              <div>
                <span className="benefit-icon">✦</span>
                <span>
                  <strong>Personalized recommendations</strong>
                  <small>Products tailored to your preferences</small>
                </span>
              </div>
              <div>
                <span className="benefit-icon">▣</span>
                <span>
                  <strong>Smart billing</strong>
                  <small>A more convenient checkout experience</small>
                </span>
              </div>
              <div>
                <span className="benefit-icon">↗</span>
                <span>
                  <strong>Smarter shopping</strong>
                  <small>Discover products suited to your needs</small>
                </span>
              </div>
            </div>
          </div>

          <p className="auth-footer-note">
            INTELLIGENT SHOPPING · PERSONALIZED EXPERIENCES
          </p>
        </aside>

        <section className="auth-card-wrap">
          <form className="auth-card" onSubmit={handleSubmit}>
            <div className="auth-card-brand">
              <span className="auth-card-logo">S</span>
              <strong>
                Smart<span>Trolley</span>
              </strong>
              <small>SMART SHOPPING, SMARTER CHOICES</small>
            </div>

            <div className="auth-heading">
              <h2>Welcome Back</h2>
              <p>
                Sign in to access your account and continue
                your personalized shopping experience.
              </p>
            </div>

            <label htmlFor="login-email">Email address</label>
            <div className="auth-input-wrap">
              <span aria-hidden="true">✉</span>
              <input
                id="login-email"
                type="email"
                placeholder="Enter your email address"
                autoComplete="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </div>

            <label htmlFor="login-password">Password</label>
            <div className="auth-input-wrap">
              <span aria-hidden="true">▣</span>
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                placeholder="Enter your password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
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

            <button
              className="auth-submit"
              type="submit"
              disabled={loading}
            >
              {loading ? "Signing in..." : "Sign In"}
              {!loading && <span aria-hidden="true">→</span>}
            </button>

            <div className="auth-divider">
              <span />
              <small>SMART SHOPPING STARTS HERE</small>
              <span />
            </div>

            <p className="auth-switch">
              Don’t have an account?{" "}
              <Link to="/register">Create an account</Link>
            </p>
          </form>
        </section>
      </section>
    </main>
  );
}
