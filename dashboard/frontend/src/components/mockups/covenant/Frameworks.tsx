import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Frameworks.css";

interface Framework {
  id: string;
  name: string;
  full: string;
  dataTypes: number;
  activePolicies: number;
  totalPolicies: number;
  scope: string;
  actions: string[];
  activeSince: string;
  status: "active" | "inactive" | "conflict";
  conflicts?: { policy: string; framework: string }[];
  reviewDue?: string;
  monogram: string;
  desc: string;
}

const frameworks: Framework[] = [
  {
    id: "pci-dss", name: "PCI-DSS", full: "Payment Card Industry Data Security Standard",
    dataTypes: 14, activePolicies: 8, totalPolicies: 8,
    scope: "US / Global", actions: ["Mask", "Tokenize", "Block"],
    activeSince: "Jan 12, 2026", status: "active", monogram: "P",
    desc: "Protects cardholder data and prevents payment fraud across all agent traffic.",
    reviewDue: "Jun 15, 2026",
  },
  {
    id: "hipaa", name: "HIPAA", full: "Health Insurance Portability and Accountability Act",
    dataTypes: 18, activePolicies: 7, totalPolicies: 7,
    scope: "United States", actions: ["Mask", "Block"],
    activeSince: "Jan 12, 2026", status: "active", monogram: "H",
    desc: "Enforces de-identification of protected health information (PHI) in all prompts.",
    reviewDue: "Apr 10, 2026",
  },
  {
    id: "gdpr", name: "GDPR", full: "General Data Protection Regulation",
    dataTypes: 22, activePolicies: 6, totalPolicies: 8,
    scope: "European Union", actions: ["Mask", "Tokenize", "Block", "Allow+Log"],
    activeSince: "Feb 03, 2026", status: "conflict", monogram: "G",
    desc: "Enforces personal data minimisation and subject rights for EU data subjects.",
    reviewDue: "Mar 01, 2026",
    conflicts: [
      { policy: "Phone Number Log", framework: "PCI-DSS" },
      { policy: "Allow+Log for NAME", framework: "HIPAA" },
    ],
  },
  {
    id: "soc2", name: "SOC 2", full: "System and Organization Controls 2",
    dataTypes: 8, activePolicies: 0, totalPolicies: 5,
    scope: "US / Global", actions: ["Allow+Log", "Block"],
    activeSince: "", status: "inactive", monogram: "S",
    desc: "Audit-trail and access control requirements for service organizations.",
  },
];

function ComplianceBar({ active, total }: { active: number; total: number }) {
  const pct = total === 0 ? 0 : (active / total) * 100;
  return (
    <div className="ip-compliance-bar-wrap">
      <div className="ip-compliance-bar">
        <div className="ip-compliance-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="ip-compliance-label">{active}/{total} policies active</span>
    </div>
  );
}

export function Frameworks() {
  const [toggles, setToggles] = useState<Record<string, boolean>>({ "pci-dss": true, "hipaa": true, "gdpr": true, "soc2": false });
  const [expanded, setExpanded] = useState<string | null>(null);
  const [activePage, setActivePage] = useState<any>("frameworks");

  const toggle = (id: string) => setToggles(prev => ({ ...prev, [id]: !prev[id] }));
  const toggleConflict = (id: string) => setExpanded(prev => prev === id ? null : id);

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Frameworks</div>
          <div className="ip-page-subtitle">Activate compliance frameworks — each one applies a curated set of detection policies</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost">Browse catalog</button>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-frameworks-grid">
          {frameworks.map((fw) => {
            const active = toggles[fw.id];
            const hasConflict = fw.status === "conflict" && active;
            return (
              <div
                key={fw.id}
                className={`ip-sheet ip-framework-card${!active ? " ip-framework-card--inactive" : ""}${hasConflict ? " ip-framework-card--conflict" : ""}`}
              >
                <div className="ip-fw-header">
                  <div className="ip-fw-header-left">
                    <div className={`ip-fw-monogram${!active ? " ip-fw-monogram--inactive" : ""}`}>
                      <span className="ip-mono">{fw.monogram}</span>
                    </div>
                    <div>
                      <div className="ip-fw-name">{fw.name}</div>
                      <div className="ip-fw-scope">{fw.scope}</div>
                    </div>
                  </div>
                  <label className="ip-toggle">
                    <input type="checkbox" checked={active} onChange={() => toggle(fw.id)} />
                    <span className="ip-toggle-track" />
                    <span className="ip-toggle-thumb" />
                  </label>
                </div>

                <div className="ip-fw-desc">{fw.desc}</div>

                {hasConflict && fw.conflicts && (
                  <div className="ip-fw-conflict-block">
                    <button className="ip-fw-conflict-header" onClick={() => toggleConflict(fw.id)}>
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none"><path d="M6 1L11 10H1L6 1Z" stroke="var(--status-masked-dot)" strokeWidth="1.2" fill="none"/><path d="M6 5V7" stroke="var(--status-masked-dot)" strokeWidth="1.2" strokeLinecap="round"/><circle cx="6" cy="8.5" r="0.5" fill="var(--status-masked-dot)"/></svg>
                      <span>{fw.conflicts.length} policy conflict{fw.conflicts.length > 1 ? "s" : ""} detected</span>
                      <span className="ip-fw-conflict-caret">{expanded === fw.id ? "▲" : "▼"}</span>
                    </button>
                    {expanded === fw.id && (
                      <div className="ip-fw-conflict-detail">
                        {fw.conflicts.map((c, i) => (
                          <div key={i} className="ip-fw-conflict-row">
                            <span className="ip-mono" style={{ fontSize: 11 }}>{c.policy}</span>
                            <span style={{ fontSize: 11, color: "var(--text-tertiary)" }}>conflicts with {c.framework}</span>
                          </div>
                        ))}
                        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 6 }}>
                          Highest-severity action wins. Go to Policies to resolve manually.
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {active && (
                  <ComplianceBar active={fw.activePolicies} total={fw.totalPolicies} />
                )}

                <div className="ip-fw-meta">
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {fw.actions.map(a => <span key={a} className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>{a}</span>)}
                    <span className="ip-fw-dtype-count">{fw.dataTypes} data types</span>
                  </div>
                </div>

                <div className="ip-fw-footer">
                  {active && fw.activeSince && (
                    <span className="ip-fw-since">
                      Active {fw.activeSince}
                      {fw.reviewDue && <> · <span style={{ color: fw.id === "gdpr" ? "var(--status-blocked-text)" : fw.id === "hipaa" ? "var(--status-masked-text)" : "inherit" }}>review {fw.reviewDue}</span></>}
                    </span>
                  )}
                  {!active && <span className="ip-fw-since" style={{ color: "var(--text-tertiary)", fontStyle: "italic" }}>Not active</span>}
                  <button
                    className="ip-fw-link"
                    onClick={() => setActivePage("policies")}
                    style={{ opacity: active ? 1 : 0.5 }}
                  >
                    {fw.activePolicies} policies →
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </AppShell>
  );
}
