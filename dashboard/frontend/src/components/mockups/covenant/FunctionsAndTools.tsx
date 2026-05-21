import React from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./FunctionsAndTools.css";

const TOOLS = [
  {
    id: "aml",
    name: "AML / SAR Engine",
    description: "Automated suspicious activity reporting and transaction monitoring.",
    status: "installed",
  },
  {
    id: "covenants",
    name: "Financial Covenants Tracker",
    description: "Real-time leverage ratio and debt obligation monitoring.",
    status: "available",
  },
  {
    id: "gdpr",
    name: "GDPR Retention Scanner",
    description: "Automated data aging and deletion enforcement.",
    status: "available",
  },
  {
    id: "sla",
    name: "SLA Credit Leakage Monitor",
    description: "Contract obligation tracking to prevent revenue leakage.",
    status: "available",
  },
  {
    id: "ropa",
    name: "ROPA Activity Logger",
    description: "Centralized Article 30 processing activity registry.",
    status: "installed",
  },
];

export function FunctionsAndTools() {
  return (
    <AppShell>
      <div className="ip-page">
        <div className="ip-page-header">
          <div className="ip-page-header-left">
            <h1 className="ip-page-title">Functions & Tools</h1>
            <p className="ip-page-subtitle">Pain-driven independent tools and generic function suites.</p>
          </div>
        </div>

        <div className="ip-content">
          <div className="ip-tools-grid">
            {TOOLS.map((tool) => (
              <div key={tool.id} className="ip-card ip-tool-card">
                <div className="ip-tool-header">
                  <h3 className="ip-tool-title">{tool.name}</h3>
                  {tool.status === "installed" ? (
                    <span className="ip-badge ip-badge--passed">
                      <span className="ip-badge-dot" /> Installed
                    </span>
                  ) : (
                    <span className="ip-tag">Available</span>
                  )}
                </div>
                <p className="ip-tool-desc">{tool.description}</p>
                
                <div className="ip-tool-actions">
                  {tool.status === "installed" ? (
                    <button className="ip-btn-ghost">Configure</button>
                  ) : (
                    <button className="ip-btn-primary">Install Tool</button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
