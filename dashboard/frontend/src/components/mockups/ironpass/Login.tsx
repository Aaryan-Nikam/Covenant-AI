import React, { useState } from "react";
import "./_shared/_shared.css";
import "./Login.css";

export function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    // Simulate login then redirect to dashboard
    setTimeout(() => {
      window.location.hash = "dashboard";
    }, 800);
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
          <div className="ip-login-subtitle">Continue to your workspace</div>
        </div>

        <form className="ip-login-form" onSubmit={handleLogin}>
          <div className="ip-form-group">
            <label className="ip-form-label" htmlFor="email">Email address</label>
            <input
              id="email"
              type="email"
              className="ip-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              required
            />
          </div>
          <div className="ip-form-group">
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
          </div>
          <button type="submit" className="ip-login-btn" disabled={isLoading}>
            {isLoading ? "Authenticating..." : "Sign in"}
          </button>
        </form>

        <div className="ip-login-footer">
          Don't have an account? <a href="#contact">Contact security team</a>
        </div>
      </div>
    </div>
  );
}
