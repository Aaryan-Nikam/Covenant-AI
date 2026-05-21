import React, { useState, useEffect } from "react";
import logoUrl from "../../../../assets/govern_logo.svg";
import "./_shared.css";

type NavPage =
  | "dashboard"
  | "audit"
  | "violations"
  | "reports"
  | "frameworks"
  | "policies"
  | "legal"
  | "guardrails"
  | "agent-security-suite"
  | "gov-analytics"
  | "functions-tools"
  | "industry-suites"
  | "console";

interface AppShellProps {
  children: React.ReactNode;
}

const navGroups = [
  {
    label: "Core",
    items: [
      { id: "dashboard" as NavPage, label: "Dashboard" },
      { id: "audit" as NavPage, label: "Audit Log" },
      { id: "violations" as NavPage, label: "Violations", badge: 3 },
      { id: "reports" as NavPage, label: "Reports & Analytics" },
    ],
  },
  {
    label: "Compliance",
    items: [
      { id: "frameworks" as NavPage, label: "Frameworks & Guidelines" },
      { id: "policies" as NavPage, label: "Policies" },
      { id: "legal" as NavPage, label: "Legal" },
    ],
  },
  {
    label: "Governance",
    items: [
      { id: "guardrails" as NavPage, label: "Guardrails" },
      { id: "agent-security-suite" as NavPage, label: "Agent Security" },
      { id: "gov-analytics" as NavPage, label: "Analytics" },
    ],
  },
  {
    label: "Products & Tools",
    items: [
      { id: "functions-tools" as NavPage, label: "Functions & Tools" },
      { id: "industry-suites" as NavPage, label: "Industry Suites" },
      { id: "console" as NavPage, label: "Test Console", accent: true },
    ],
  },
];

export function AppShell({ children }: AppShellProps) {
  const [activePage, setActivePage] = useState<NavPage>("dashboard");

  useEffect(() => {
    const hash = window.location.hash.slice(1) as NavPage;
    if (hash) {
      setActivePage(hash);
    }
  }, []);

  const handleNavigate = (page: NavPage) => {
    window.location.hash = page;
    setActivePage(page);
  };

  return (
    <div className="ip-shell">
      <nav className="ip-sidebar">
        <div className="ip-logo-area">
          <img src={logoUrl} alt="Covenant AI Logo" className="ip-logo-icon" style={{width: 24, height: 24, objectFit: 'contain'}} />
          <span className="ip-logo-text">Covenant AI</span>
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
          <div className="ip-status-url">api.covenant.io</div>
        </div>
      </nav>

      <main className="ip-main">
        {children}
      </main>
    </div>
  );
}
