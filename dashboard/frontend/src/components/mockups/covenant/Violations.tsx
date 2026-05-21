import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Violations.css";

type Severity = "critical" | "high" | "medium";

interface Violation {
  id: string;
  outcome: "blocked" | "masked";
  severity: Severity;
  detected: string[];
  agentId: string;
  timestamp: string;
  timeAgo: string;
  ruleset: string;
  reviewed: boolean;
  similarToday: number;
  model: string;
  payload: string;
}

const violations: Violation[] = [
  {
    id: "v1", outcome: "blocked", severity: "critical",
    detected: ["CREDIT_CARD", "SSN"],
    agentId: "agent_prod_v2_a9f3", timestamp: "Apr 01, 2026 · 14:32:07",
    timeAgo: "2 min ago", ruleset: "PCI-DSS", reviewed: false, similarToday: 5, model: "gpt-4o",
    payload: `{\n  "model": "gpt-4o",\n  "messages": [\n    {\n      "role": "user",\n      "content": "Process payment for card 4111111111111111, SSN 123-45-6789"\n    }\n  ]\n}`,
  },
  {
    id: "v2", outcome: "blocked", severity: "high",
    detected: ["SSN"],
    agentId: "agent_stg_b7c2_x1", timestamp: "Apr 01, 2026 · 14:18:22",
    timeAgo: "14 min ago", ruleset: "HIPAA", reviewed: false, similarToday: 2, model: "claude-3-5-sonnet",
    payload: `{\n  "model": "claude-3-5-sonnet",\n  "messages": [\n    {\n      "role": "user",\n      "content": "Look up patient with SSN 987-65-4321"\n    }\n  ]\n}`,
  },
  {
    id: "v3", outcome: "masked", severity: "medium",
    detected: ["DATE_OF_BIRTH", "NAME"],
    agentId: "agent_prod_v2_a9f3", timestamp: "Apr 01, 2026 · 13:32:07",
    timeAgo: "1 hr ago", ruleset: "GDPR", reviewed: false, similarToday: 8, model: "gpt-4o",
    payload: `{\n  "model": "gpt-4o",\n  "messages": [\n    {\n      "role": "user",\n      "content": "Find records for John Doe, born 1985-03-15"\n    }\n  ]\n}`,
  },
  {
    id: "v4", outcome: "blocked", severity: "critical",
    detected: ["IBAN", "CREDIT_CARD"],
    agentId: "agent_analytics_v1", timestamp: "Apr 01, 2026 · 11:32:07",
    timeAgo: "3 hr ago", ruleset: "PCI-DSS", reviewed: true, similarToday: 1, model: "gpt-4o",
    payload: `{\n  "model": "gpt-4o",\n  "messages": [\n    {\n      "role": "user",\n      "content": "Transfer from IBAN DE89370400440532013000 card 5500005555555559"\n    }\n  ]\n}`,
  },
  {
    id: "v5", outcome: "blocked", severity: "high",
    detected: ["SSN"],
    agentId: "agent_prod_v2_a9f3", timestamp: "Apr 01, 2026 · 09:32:07",
    timeAgo: "5 hr ago", ruleset: "HIPAA", reviewed: true, similarToday: 3, model: "gpt-4o",
    payload: `{\n  "model": "gpt-4o",\n  "messages": [\n    {\n      "role": "user",\n      "content": "Patient SSN is 111-22-3333"\n    }\n  ]\n}`,
  },
];

const severityConfig: Record<Severity, { label: string; color: string; bg: string }> = {
  critical: { label: "Critical", color: "var(--status-blocked-text)", bg: "var(--status-blocked-bg)" },
  high: { label: "High", color: "var(--status-masked-text)", bg: "var(--status-masked-bg)" },
  medium: { label: "Medium", color: "#1D4ED8", bg: "#EFF6FF" },
};

const piiDetails: Record<string, string> = {
  CREDIT_CARD: "16-digit card number · confidence 0.99 · regex",
  SSN: "Social Security Number · confidence 0.99 · regex",
  DATE_OF_BIRTH: "Date value in ISO format · confidence 0.81 · NER",
  NAME: "Full name entity · confidence 0.87 · NER",
  IBAN: "International bank account number · confidence 0.97 · regex",
  PHONE: "Phone number · confidence 0.95 · regex",
};

export function Violations() {
  const [selected, setSelected] = useState<string>("v1");
  const [reviewedMap, setReviewedMap] = useState<Record<string, boolean>>(
    Object.fromEntries(violations.map(v => [v.id, v.reviewed]))
  );
  const [activePage, setActivePage] = useState<any>("violations");
  const selectedViolation = violations.find(v => v.id === selected);

  const acknowledge = () => {
    if (selected) setReviewedMap(prev => ({ ...prev, [selected]: true }));
  };

  const unreviewed = violations.filter(v => !reviewedMap[v.id]).length;

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">
            Violations
            {unreviewed > 0 && <span className="ip-unreviewed-count">{unreviewed}</span>}
          </div>
          <div className="ip-page-subtitle">Blocked and flagged requests requiring review</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost" onClick={() => setReviewedMap(Object.fromEntries(violations.map(v => [v.id, true])))}>Mark all reviewed</button>
          <button className="ip-btn-ghost">Export</button>
        </div>
      </div>

      <div className="ip-content" style={{ padding: 0, display: "flex", overflow: "hidden" }}>
        {/* Left list */}
        <div className="ip-violations-list">
          {violations.map((v) => {
            const sv = severityConfig[v.severity];
            const isReviewed = reviewedMap[v.id];
            return (
              <div
                key={v.id}
                className={`ip-violation-item${selected === v.id ? " ip-violation-item--selected" : ""}${isReviewed ? " ip-violation-item--reviewed" : ""}`}
                onClick={() => setSelected(v.id)}
              >
                <div className="ip-viol-top-row">
                  <span className={`ip-badge ip-badge--${v.outcome}`}>
                    <span className="ip-badge-dot" />
                    {v.outcome === "blocked" ? "Blocked" : "Masked"}
                  </span>
                  <span className="ip-viol-severity" style={{ color: sv.color, background: sv.bg }}>
                    {sv.label}
                  </span>
                  {!isReviewed && <span className="ip-viol-unread-dot" />}
                </div>
                <div className="ip-viol-types">
                  {v.detected.slice(0, 2).map(t => (
                    <span key={t} className="ip-tag" style={{ fontWeight: isReviewed ? 400 : 600 }}>{t}</span>
                  ))}
                  {v.detected.length > 2 && <span className="ip-tag">+{v.detected.length - 2}</span>}
                </div>
                <div className="ip-viol-meta ip-mono" style={{ fontSize: 11 }}>
                  {v.agentId.slice(0, 14)}… · {v.timeAgo}
                </div>
                <div className="ip-viol-ruleset">{v.ruleset}</div>
              </div>
            );
          })}
        </div>

        {/* Right detail */}
        {selectedViolation && (() => {
          const sv = severityConfig[selectedViolation.severity];
          const isReviewed = reviewedMap[selectedViolation.id];
          return (
            <div className="ip-violations-detail">
              <div className="ip-detail-header">
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className={`ip-badge ip-badge--${selectedViolation.outcome}`}>
                    <span className="ip-badge-dot" />
                    {selectedViolation.outcome === "blocked" ? "Blocked" : "Masked"}
                  </span>
                  <span className="ip-viol-severity" style={{ color: sv.color, background: sv.bg }}>{sv.label}</span>
                </div>
                <div className="ip-mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>#{selectedViolation.id}</div>
              </div>

              {/* Context summary */}
              <div className="ip-drawer-section">
                <div className="ip-viol-context-row">
                  <div className="ip-viol-ctx-item">
                    <span className="ip-section-heading" style={{ marginBottom: 2 }}>Timestamp</span>
                    <span className="ip-mono" style={{ fontSize: 11, color: "var(--text-secondary)" }}>{selectedViolation.timestamp} UTC</span>
                  </div>
                  <div className="ip-viol-ctx-item">
                    <span className="ip-section-heading" style={{ marginBottom: 2 }}>Agent</span>
                    <span className="ip-mono" style={{ fontSize: 11, color: "var(--text-secondary)" }}>{selectedViolation.agentId.slice(0, 16)}…</span>
                  </div>
                  <div className="ip-viol-ctx-item">
                    <span className="ip-section-heading" style={{ marginBottom: 2 }}>Similar today</span>
                    <span style={{ fontSize: 13, color: selectedViolation.similarToday > 3 ? "var(--status-blocked-text)" : "var(--text-primary)", fontWeight: 500 }}>
                      {selectedViolation.similarToday}×
                    </span>
                  </div>
                  <div className="ip-viol-ctx-item">
                    <span className="ip-section-heading" style={{ marginBottom: 2 }}>Ruleset</span>
                    <span className="ip-tag" style={{ fontFamily: "var(--font-sans)", fontSize: 11 }}>{selectedViolation.ruleset}</span>
                  </div>
                </div>
              </div>

              {/* Detected PII */}
              <div className="ip-drawer-section">
                <div className="ip-section-heading">Detected PII</div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {selectedViolation.detected.map(type => (
                    <div key={type} className="ip-sheet" style={{ padding: "10px 12px" }}>
                      <div className="ip-mono" style={{ fontSize: 12, fontWeight: 600, marginBottom: 3 }}>{type}</div>
                      <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{piiDetails[type] ?? "confidence 0.90 · regex"}</div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Request Preview */}
              <div className="ip-drawer-section">
                <div className="ip-section-heading">Original Request</div>
                <div className="ip-json-viewer">
                  <pre style={{ fontFamily: "var(--font-mono)", fontSize: 11.5, color: "#E2E8F0", whiteSpace: "pre-wrap", wordBreak: "break-all", margin: 0 }}>
                    {selectedViolation.payload}
                  </pre>
                </div>
              </div>

              {/* Review actions */}
              <div className="ip-drawer-section">
                <div className="ip-section-heading">Review</div>
                {isReviewed ? (
                  <div className="ip-badge ip-badge--passed" style={{ fontSize: 12 }}>
                    <span className="ip-badge-dot" /> Acknowledged
                  </div>
                ) : (
                  <div className="ip-review-actions">
                    <button className="ip-btn-ghost" style={{ fontSize: 12, padding: "6px 12px" }}>False Positive</button>
                    <button className="ip-btn-primary" style={{ fontSize: 12, padding: "6px 12px" }} onClick={acknowledge}>Acknowledge</button>
                    <button className="ip-btn-ghost" style={{ fontSize: 12, padding: "6px 12px", color: "var(--status-blocked-text)", borderColor: "#FECACA" }}>Escalate</button>
                  </div>
                )}
              </div>
            </div>
          );
        })()}
      </div>
    </AppShell>
  );
}
