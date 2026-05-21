import React, { useState } from "react";
import logoUrl from "../../../assets/logo.svg";
import "./_shared/_shared.css";
import "./Login.css";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      setError("Email and password are required");
      return;
    }
    setIsLoading(true);
    setError("");

    const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    try {
      // Mock API call for frontend testing
      await new Promise(resolve => setTimeout(resolve, 500));
      
      localStorage.setItem("covenant_token", "mock_jwt_token_for_testing");
      window.location.hash = "workspaces";
    } catch {
      setError("Unable to connect to the backend.");
      setIsLoading(false);
    }
  };

  return (
    <div className="ip-login-page">
      <div className="ip-login-container">
        <div className="ip-login-header">
          <div className="ip-login-logo">
            <img src={logoUrl} alt="Covenant AI Logo" className="ip-logo-icon" style={{width: 32, height: 32, objectFit: 'contain'}} />
            <span className="ip-login-logo-text">Covenant AI</span>
          </div>
          <div className="ip-login-title">Sign in to Covenant AI</div>
          <div className="ip-login-subtitle">Enter your email and password to continue</div>
        </div>

        <form className="ip-login-form" onSubmit={handleLogin}>
          <div className="ip-form-group">
            <label className="ip-form-label" htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              className="ip-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              autoFocus
            />
          </div>
          <div className="ip-form-group" style={{marginTop: 16}}>
            <label className="ip-form-label" htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              className="ip-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
            {error && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#EF4444" }}>{error}</div>
            )}
          </div>
          <button type="submit" className="ip-login-btn" disabled={isLoading} style={{marginTop: 24}}>
            {isLoading ? "Authenticating..." : "Sign in"}
          </button>
        </form>

        <div className="ip-login-footer">
          Don't have an account? Contact your administrator.
        </div>
      </div>
    </div>
  );
}
