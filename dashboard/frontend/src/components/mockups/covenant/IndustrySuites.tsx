import React from "react";
import "./_shared/_shared.css";
import "./IndustrySuites.css";

const SUITES = [
  {
    id: "finance",
    name: "Financial Services Suite",
    description: "End-to-end compliance for banking, lending, and asset management. Monitor AML patterns and track complex financial covenants.",
    modules: ["AML / SAR Automation", "Financial Covenants"],
    status: "installed",
  },
  {
    id: "healthcare",
    name: "Healthcare & Life Sciences Suite",
    description: "Automated PHI redaction, HIPAA compliance guardrails, and secure data handling for medical records and patient data.",
    modules: ["HIPAA Compliance", "PHI Anonymization"],
    status: "available",
  },
  {
    id: "legal",
    name: "Legal & Contract Suite",
    description: "Intelligent contract analysis, deviation tracking, and automated DSAR fulfillment for legal teams and law firms.",
    modules: ["Contract Analysis", "DSAR Automation"],
    status: "available",
  },
];

import { AppShell } from "./_shared/AppShell";

export function IndustrySuites() {
  return (
    <AppShell>
      <div className="ip-page">
        <div className="ip-page-header">
          <div className="ip-page-header-left">
            <h1 className="ip-page-title">Industry Suites</h1>
            <p className="ip-page-subtitle">Bundled, niche-specific solutions tailored for highly regulated sectors.</p>
          </div>
        </div>

        <div className="ip-content">
          <div className="ip-suites-grid">
            {SUITES.map((suite) => (
              <div key={suite.id} className="ip-card ip-suite-card">
                <div className="ip-suite-header">
                  <h3 className="ip-suite-title">{suite.name}</h3>
                  {suite.status === "installed" ? (
                    <span className="ip-badge ip-badge--passed">
                      <span className="ip-badge-dot" /> Installed
                    </span>
                  ) : (
                    <span className="ip-tag">Available</span>
                  )}
                </div>
                <p className="ip-suite-desc">{suite.description}</p>
                
                <div className="ip-suite-modules">
                  <div className="ip-section-heading">Included Modules</div>
                  <ul className="ip-suite-module-list">
                    {suite.modules.map(mod => (
                      <li key={mod} className="ip-suite-module-item">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: 'var(--accent-primary)' }}>
                          <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        {mod}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="ip-suite-actions">
                  {suite.status === "installed" ? (
                    <button className="ip-btn-ghost">Configure Suite</button>
                  ) : (
                    <button className="ip-btn-primary">Install Suite</button>
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
