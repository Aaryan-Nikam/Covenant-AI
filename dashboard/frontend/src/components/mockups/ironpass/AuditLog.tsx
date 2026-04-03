import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./AuditLog.css";

type OutcomeType = "passed" | "masked" | "blocked" | "error";

interface LogEntry {
  id: string;
  timestamp: string;
  tenant: string;
  agentId: string;
  outcome: OutcomeType;
  detected: string[];
  latency: number;
  model: string;
  ruleset: string;
  action: string;
}

const mockLogs: LogEntry[] = [
  { id: "log_a1b2c3d4", timestamp: "Apr 01, 2026 · 14:32:07", tenant: "Acme Corp", agentId: "agent_prod_v2_a9f3", outcome: "masked", detected: ["CREDIT_CARD", "NAME"], latency: 142, model: "gpt-4o", ruleset: "PCI-DSS v1.2", action: "mask" },
  { id: "log_e5f6g7h8", timestamp: "Apr 01, 2026 · 14:31:54", tenant: "Acme Corp", agentId: "agent_prod_v2_a9f3", outcome: "passed", detected: [], latency: 38, model: "gpt-4o", ruleset: "—", action: "pass" },
  { id: "log_i9j0k1l2", timestamp: "Apr 01, 2026 · 14:31:22", tenant: "Globex Ltd", agentId: "agent_stg_b7c2_x1", outcome: "blocked", detected: ["SSN", "DATE_OF_BIRTH", "IBAN"], latency: 201, model: "claude-3-5-sonnet", ruleset: "HIPAA + PCI-DSS", action: "block" },
  { id: "log_m3n4o5p6", timestamp: "Apr 01, 2026 · 14:30:48", tenant: "Initech", agentId: "agent_prod_c4d3", outcome: "masked", detected: ["PHONE"], latency: 97, model: "gpt-4o-mini", ruleset: "GDPR v2.1", action: "mask" },
  { id: "log_q7r8s9t0", timestamp: "Apr 01, 2026 · 14:30:31", tenant: "Acme Corp", agentId: "agent_prod_v2_a9f3", outcome: "passed", detected: [], latency: 44, model: "gpt-4o", ruleset: "—", action: "pass" },
  { id: "log_u1v2w3x4", timestamp: "Apr 01, 2026 · 14:29:55", tenant: "Globex Ltd", agentId: "agent_stg_b7c2_x1", outcome: "error", detected: [], latency: 589, model: "claude-3-5-sonnet", ruleset: "—", action: "error" },
  { id: "log_y5z6a7b8", timestamp: "Apr 01, 2026 · 14:29:12", tenant: "Initech", agentId: "agent_prod_c4d3", outcome: "masked", detected: ["CREDIT_CARD"], latency: 113, model: "gpt-4o-mini", ruleset: "PCI-DSS v1.2", action: "mask" },
  { id: "log_c9d0e1f2", timestamp: "Apr 01, 2026 · 14:28:44", tenant: "Acme Corp", agentId: "agent_analytics_v1", outcome: "passed", detected: [], latency: 29, model: "gpt-4o", ruleset: "—", action: "pass" },
  { id: "log_g3h4i5j6", timestamp: "Apr 01, 2026 · 14:27:38", tenant: "Globex Ltd", agentId: "agent_stg_b7c2_x1", outcome: "blocked", detected: ["SSN"], latency: 156, model: "claude-3-5-sonnet", ruleset: "HIPAA v3.0", action: "block" },
  { id: "log_k7l8m9n0", timestamp: "Apr 01, 2026 · 14:26:59", tenant: "Initech", agentId: "agent_prod_c4d3", outcome: "masked", detected: ["NAME", "PHONE"], latency: 188, model: "gpt-4o-mini", ruleset: "GDPR v2.1", action: "mask" },
  { id: "log_o1p2q3r4", timestamp: "Apr 01, 2026 · 14:26:21", tenant: "Acme Corp", agentId: "agent_prod_v2_a9f3", outcome: "passed", detected: [], latency: 52, model: "gpt-4o", ruleset: "—", action: "pass" },
  { id: "log_s5t6u7v8", timestamp: "Apr 01, 2026 · 14:25:47", tenant: "Acme Corp", agentId: "agent_analytics_v1", outcome: "masked", detected: ["CREDIT_CARD", "CVV"], latency: 267, model: "gpt-4o", ruleset: "PCI-DSS v1.2", action: "tokenize" },
];

const outcomeLabel: Record<OutcomeType, string> = { passed: "Passed", masked: "Masked", blocked: "Blocked", error: "Error" };

function Badge({ outcome }: { outcome: OutcomeType }) {
  return (
    <span className={`ip-badge ip-badge--${outcome}`}>
      <span className="ip-badge-dot" />
      {outcomeLabel[outcome]}
    </span>
  );
}

function LatencyCell({ ms }: { ms: number }) {
  const cls = ms < 200 ? "ip-latency--normal" : ms < 400 ? "ip-latency--warn" : "ip-latency--danger";
  return <span className={`ip-mono ${cls}`} style={{ fontSize: 12 }}>{ms}ms</span>;
}

function DataTypeTags({ types }: { types: string[] }) {
  if (types.length === 0) return <span style={{ fontSize: 13, color: "var(--text-tertiary)" }}>—</span>;
  const visible = types.slice(0, 2);
  const extra = types.length - 2;
  return (
    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
      {visible.map(t => <span key={t} className="ip-tag">{t}</span>)}
      {extra > 0 && <span className="ip-tag">+{extra}</span>}
    </div>
  );
}

function SummaryBar() {
  const counts = { passed: 5, masked: 5, blocked: 2, error: 1 };
  const total = Object.values(counts).reduce((a, b) => a + b, 0);
  const colors: Record<OutcomeType, string> = {
    passed: "var(--status-passed-dot)",
    masked: "var(--status-masked-dot)",
    blocked: "var(--status-blocked-dot)",
    error: "#94A3B8",
  };
  return (
    <div className="ip-log-summary-bar">
      <div className="ip-summary-stacked-bar">
        {(Object.keys(counts) as OutcomeType[]).map(k => (
          <div
            key={k}
            className="ip-summary-segment"
            style={{ width: `${(counts[k] / total) * 100}%`, background: colors[k] }}
            title={`${counts[k]} ${k}`}
          />
        ))}
      </div>
      <div className="ip-summary-counts">
        {(Object.keys(counts) as OutcomeType[]).map(k => (
          <span key={k} className="ip-summary-count">
            <span className="ip-summary-dot" style={{ background: colors[k] }} />
            {counts[k]} {outcomeLabel[k]}
          </span>
        ))}
        <span className="ip-summary-total">{total} total</span>
      </div>
    </div>
  );
}

const piiDetails: Record<string, { method: string; confidence: number; positions: string }> = {
  CREDIT_CARD: { method: "regex", confidence: 0.99, positions: "47–62" },
  NAME: { method: "NER", confidence: 0.87, positions: "12–22" },
  SSN: { method: "regex", confidence: 0.99, positions: "31–42" },
  DATE_OF_BIRTH: { method: "NER", confidence: 0.81, positions: "67–78" },
  IBAN: { method: "regex", confidence: 0.97, positions: "14–34" },
  PHONE: { method: "regex", confidence: 0.95, positions: "23–35" },
  CVV: { method: "regex", confidence: 0.99, positions: "18–21" },
};

function buildSanitizedPayload(entry: LogEntry): string {
  const content = entry.detected.length > 0
    ? `"Send info for card [MASKED·${entry.detected[0]}]${entry.detected[1] ? ` and ${entry.detected[1]} [MASKED·${entry.detected[1]}]` : ""}"`
    : `"What is the current time in New York?"`;
  return `{\n  "model": "${entry.model}",\n  "messages": [\n    {\n      "role": "user",\n      "content": ${content}\n    }\n  ],\n  "temperature": 0.7\n}`;
}

function DrawerTimeline({ entry }: { entry: LogEntry }) {
  const steps = [
    { label: "Received", time: "0ms", desc: "" },
    { label: "PII scan complete", time: "18ms", desc: "regex layer" },
    ...(entry.detected.length > 0 ? [{ label: "NER scan complete", time: "89ms", desc: "NER layer" }] : []),
    ...(entry.detected.length > 0 ? [{ label: "Action applied", time: "94ms", desc: entry.action }] : []),
    { label: `Forwarded to ${entry.model.startsWith("claude") ? "Anthropic" : "OpenAI"}`, time: `${entry.latency - 4}ms`, desc: "" },
    { label: "Response received", time: `${entry.latency - 1}ms`, desc: "" },
    { label: entry.action === "mask" ? "De-tokenized" : "Response returned", time: `${entry.latency}ms`, desc: "", final: true },
  ];

  return (
    <div className="ip-timeline">
      {steps.map((step, i) => (
        <div key={i} className="ip-timeline-step">
          <div className="ip-timeline-left">
            <div className={`ip-timeline-dot${(step as any).final ? " ip-timeline-dot--final" : ""}`} />
            {i < steps.length - 1 && <div className="ip-timeline-line" />}
          </div>
          <div className="ip-timeline-content">
            <span className="ip-timeline-label">{step.label}</span>
            {step.desc && <span className="ip-timeline-desc"> ({step.desc})</span>}
            <span className="ip-timeline-time">{step.time}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

function LogDetailDrawer({ entry, onClose }: { entry: LogEntry; onClose: () => void }) {
  return (
    <>
      <div className="ip-drawer-backdrop" onClick={onClose} />
      <div className="ip-drawer" style={{ width: 520 }}>
        <div className="ip-drawer-header">
          <button className="ip-drawer-close" onClick={onClose}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Close
          </button>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
            Log Entry · <span className="ip-mono" style={{ fontSize: 11 }}>#{entry.id.slice(4, 10)}</span>
          </div>
        </div>

        <div className="ip-drawer-section" style={{ paddingBottom: 8 }}>
          <div className="ip-mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>{entry.timestamp} UTC</div>
          <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
            <span className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>{entry.tenant}</span>
            <span className="ip-tag ip-mono" style={{ fontSize: 11 }}>{entry.agentId.slice(0, 16)}…</span>
            <span className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>{entry.model}</span>
          </div>
        </div>

        <div className="ip-drawer-section">
          <div className="ip-section-heading">Outcome</div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
            <Badge outcome={entry.outcome} />
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              {entry.ruleset !== "—" && <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{entry.ruleset}</span>}
              <span className="ip-mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>{entry.latency}ms total</span>
            </div>
          </div>
        </div>

        <div className="ip-drawer-section">
          <div className="ip-section-heading">Processing Timeline</div>
          <DrawerTimeline entry={entry} />
        </div>

        {entry.detected.length > 0 && (
          <div className="ip-drawer-section">
            <div className="ip-section-heading">Detected PII</div>
            <div className="ip-pii-list">
              {entry.detected.map(type => {
                const d = piiDetails[type] ?? { method: "regex", confidence: 0.90, positions: "0–10" };
                return (
                  <div key={type} className="ip-pii-item">
                    <div className="ip-pii-type">{type}</div>
                    <div className="ip-pii-meta">position {d.positions} · confidence {d.confidence} · {d.method}</div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <div className="ip-drawer-section">
          <div className="ip-section-heading">Sanitized Request Preview</div>
          <div className="ip-json-viewer">
            <pre>{buildSanitizedPayload(entry)}</pre>
          </div>
        </div>

        <div className="ip-drawer-section">
          <div className="ip-section-heading">Audit Integrity</div>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span className="ip-badge ip-badge--passed"><span className="ip-badge-dot" />Chain verified</span>
            <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>HMAC-SHA256</span>
          </div>
          <div className="ip-mono" style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 8, wordBreak: "break-all" }}>
            sha256:{entry.id.replace("log_", "")}...9c3e1d5b
          </div>
        </div>
      </div>
    </>
  );
}

export function AuditLog() {
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [activePage, setActivePage] = useState<any>("audit");

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Audit Log</div>
          <div className="ip-page-subtitle">Cryptographically signed, tamper-evident record of all proxy traffic</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost">Export CSV</button>
          <button className="ip-btn-ghost">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><path d="M6.5 1L2 3.5V7.5C2 9.9 4.1 11.9 6.5 12.7C8.9 11.9 11 9.9 11 7.5V3.5L6.5 1Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" fill="none"/></svg>
            Verify Chain
          </button>
        </div>
      </div>

      <div className="ip-content" style={{ display: "flex", flexDirection: "column" }}>
        <SummaryBar />

        <div className="ip-filter-bar">
          <button className="ip-filter-pill">Last 7 days ▾</button>
          <button className="ip-filter-pill">All outcomes ▾</button>
          <button className="ip-filter-pill">All data types ▾</button>
          <input
            className="ip-filter-pill"
            style={{ border: "1px solid var(--border-default)", fontFamily: "var(--font-mono)", fontSize: 12, minWidth: 180, background: "transparent" }}
            placeholder="Filter by agent ID..."
          />
          <div className="ip-filter-search">
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none"><circle cx="5.5" cy="5.5" r="4" stroke="var(--text-tertiary)" strokeWidth="1.3"/><path d="M9 9L11.5 11.5" stroke="var(--text-tertiary)" strokeWidth="1.3" strokeLinecap="round"/></svg>
            <input placeholder="Search logs..." />
          </div>
        </div>

        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
          <div className="ip-table-container">
            <table className="ip-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Tenant</th>
                  <th>Agent</th>
                  <th>Outcome</th>
                  <th>Detected</th>
                  <th>Latency</th>
                  <th style={{ width: 40 }}></th>
                </tr>
              </thead>
              <tbody>
                {mockLogs.map((log) => (
                  <tr
                    key={log.id}
                    style={{ cursor: "pointer", background: selectedLog?.id === log.id ? "var(--bg-elevated)" : undefined }}
                    onClick={() => setSelectedLog(log)}
                  >
                    <td><span className="ip-mono" style={{ fontSize: 12 }}>{log.timestamp}</span></td>
                    <td><span className="ip-tag" style={{ fontFamily: "var(--font-sans)", fontSize: 12 }}>{log.tenant}</span></td>
                    <td><span className="ip-mono" style={{ fontSize: 11, color: "var(--text-secondary)" }} title={log.agentId}>{log.agentId.slice(0, 12)}…</span></td>
                    <td><Badge outcome={log.outcome} /></td>
                    <td><DataTypeTags types={log.detected} /></td>
                    <td><LatencyCell ms={log.latency} /></td>
                    <td>
                      <button className="ip-icon-btn" onClick={(e) => { e.stopPropagation(); setSelectedLog(log); }}>→</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {selectedLog && <LogDetailDrawer entry={selectedLog} onClose={() => setSelectedLog(null)} />}
    </AppShell>
  );
}
