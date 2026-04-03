import React, { useState } from "react";
import "./_shared.css";

type NavPage =
  | "dashboard"
  | "audit"
  | "violations"
  | "agents"
  | "frameworks"
  | "policies"
  | "guardrails"
  | "governance"
  | "console"
  | "reports"
  | "api-keys"
  | "team"
  | "settings";

interface AppShellProps {
  activePage: NavPage;
  children: React.ReactNode;
  onNavigate?: (page: NavPage) => void;
}

const navGroups = [
  {
    label: "Monitor",
    items: [
      { id: "dashboard" as NavPage, label: "Dashboard" },
      { id: "audit" as NavPage, label: "Audit Log" },
      { id: "violations" as NavPage, label: "Violations", badge: 3 },
      { id: "agents" as NavPage, label: "Agents" },
    ],
  },
  {
    label: "Compliance",
    items: [
      { id: "frameworks" as NavPage, label: "Frameworks" },
      { id: "policies" as NavPage, label: "Policies" },
      { id: "guardrails" as NavPage, label: "Guardrails" },
      { id: "governance" as NavPage, label: "Governance" },
    ],
  },
  {
    label: "Tools",
    items: [
      { id: "console" as NavPage, label: "Test Console", accent: true },
      { id: "reports" as NavPage, label: "Reports" },
    ],
  },
  {
    label: "Account",
    items: [
      { id: "api-keys" as NavPage, label: "API Keys" },
      { id: "team" as NavPage, label: "Team" },
      { id: "settings" as NavPage, label: "Settings" },
    ],
  },
];

export function AppShell({ children }: AppShellProps) {
  // Override activePage and onNavigate to use hash routing globally for the mockups
  const activePage = window.location.hash.slice(1) || "dashboard";
  const handleNavigate = (page: NavPage) => {
    window.location.hash = page;
  };

  return (
    <div className="ip-shell">
      <nav className="ip-sidebar">
        <div className="ip-logo-area">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className="ip-logo-icon">
            <path d="M8 1L2 3.5V8.5C2 11.5 4.7 13.9 8 15C11.3 13.9 14 11.5 14 8.5V3.5L8 1Z" stroke="#141414" strokeWidth="1.4" strokeLinejoin="round" fill="none"/>
            <path d="M5.5 8L7 9.5L10.5 6" stroke="#141414" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className="ip-logo-text">Ironpass</span>
        </div>

        <div className="ip-nav">
          {navGroups.map((group) => (
            <div key={group.label} className="ip-nav-group">
              <div className="ip-nav-group-label">{group.label}</div>
              {group.items.map((item) => (
                <button
                  key={item.id}
                  className={`ip-nav-item${activePage === item.id ? " ip-nav-item--active" : ""}`}
                  onClick={() => handleNavigate(item.id)}
                >
                  {item.accent && (
                    <span className="ip-nav-accent-dot" />
                  )}
                  <span>{item.label}</span>
                  {item.badge && (
                    <span className="ip-nav-badge">{item.badge}</span>
                  )}
                </button>
              ))}
            </div>
          ))}
        </div>

        <div className="ip-system-status">
          <div className="ip-status-row">
            <span className="ip-status-dot ip-status-dot--active" />
            <span className="ip-status-label">PROXY ACTIVE</span>
          </div>
          <div className="ip-status-url">api.ironpass.io</div>
        </div>
      </nav>

      <main className="ip-main">
        {children}
      </main>
    </div>
  );
}
