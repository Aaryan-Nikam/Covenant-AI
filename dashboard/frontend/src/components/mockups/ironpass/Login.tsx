import React, { useState } from "react";
import "./_shared/_shared.css";
import "./Login.css";

export function Login() {
  const [apiKey, setApiKey] = useState(
    sessionStorage.getItem("ironpass_api_key") || ""
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!apiKey.trim()) {
      setError("API key is required");
      return;
    }
    setIsLoading(true);
    setError("");

    // Validate the key hits the real backend before storing it
    const base = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
    try {
      const res = await fetch(`${base}/dashboard/overview`, {
        headers: { Authorization: `Bearer ${apiKey.trim()}` },
      });

      if (res.status === 401 || res.status === 403) {
        setError("Invalid API key — check your Ironpass console.");
        setIsLoading(false);
        return;
      }

      // Key works — persist and redirect
      sessionStorage.setItem("ironpass_api_key", apiKey.trim());
      window.location.hash = "dashboard";
    } catch {
      // Backend unreachable — accept the key so dev mode still works
      sessionStorage.setItem("ironpass_api_key", apiKey.trim());
      window.location.hash = "dashboard";
    }
  };

  return (
    <div className="ip-login-page">
      <div className="ip-login-container">
        <div className="ip-login-header">
          <div className="ip-login-logo">
            <svg width="24" height="24" viewBox="0 0 16 16" fill="none" className="ip-logo-icon">
              <path d="M8 1L2 3.5V8.5C2 11.5 4.7 13.9 8 15C11.3 13.9 14 11.5 14 8.5V3.5L8 1Z" stroke="#141414" strokeWidth="1.4" strokeLinejoin="round" fill="none" />
              <path d="M5.5 8L7 9.5L10.5 6" stroke="#141414" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="ip-login-logo-text">Ironpass</span>
          </div>
          <div className="ip-login-title">Sign in to Console</div>
          <div className="ip-login-subtitle">Enter your tenant API key to continue</div>
        </div>

        <form className="ip-login-form" onSubmit={handleLogin}>
          <div className="ip-form-group">
            <label className="ip-form-label" htmlFor="apikey">API Key</label>
            <input
              id="apikey"
              type="password"
              className="ip-input"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="dbnc_live_••••••••••••"
              required
              autoFocus
            />
            {error && (
              <div style={{ marginTop: 8, fontSize: 12, color: "#EF4444" }}>{error}</div>
            )}
          </div>
          <button type="submit" className="ip-login-btn" disabled={isLoading}>
            {isLoading ? "Authenticating..." : "Sign in"}
          </button>
        </form>

        <div className="ip-login-footer">
          Don't have an API key? <a href="#api-keys">Generate one in the console</a>
        </div>
      </div>
    </div>
  );
}
