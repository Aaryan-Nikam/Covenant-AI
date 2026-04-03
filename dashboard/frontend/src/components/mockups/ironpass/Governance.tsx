import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Governance.css";

type Tab = "changelog" | "snapshot" | "schedule";

const changeEvents = [
  { date: "Apr 01", time: "14:32", initials: "AY", action: "Activated HIPAA framework", hasDiff: false },
  { date: "Apr 01", time: "14:30", initials: "AY", action: "PCI-DSS · Tokenize action changed to Block for CVV", hasDiff: true },
  { date: "Mar 28", time: "11:14", initials: "AY", action: 'Created custom policy "Employee ID Detection"', hasDiff: false },
  { date: "Mar 25", time: "09:41", initials: "DS", action: "Issued new API key (Production)", hasDiff: false },
  { date: "Mar 22", time: "16:07", initials: "AY", action: "Activated GDPR framework", hasDiff: false },
  { date: "Mar 20", time: "10:33", initials: "DS", action: "GDPR · Allow+Log action changed to Mask for NAME", hasDiff: true },
  { date: "Mar 15", time: "14:00", initials: "AY", action: "PCI-DSS framework review completed", hasDiff: false },
];

const frameworks = [
  { name: "PCI-DSS", lastReviewed: "Mar 15, 2026", nextDue: "Jun 15, 2026", status: "on-track" as const },
  { name: "HIPAA", lastReviewed: "Jan 10, 2026", nextDue: "Apr 10, 2026", status: "due-soon" as const },
  { name: "GDPR", lastReviewed: "Dec 01, 2025", nextDue: "Mar 01, 2026", status: "overdue" as const },
  { name: "SOC2", lastReviewed: "—", nextDue: "—", status: "on-track" as const },
];

const statusConfig = {
  "on-track": { dot: "var(--status-passed-dot)", text: "On track", color: "var(--status-passed-text)" },
  "due-soon": { dot: "var(--status-masked-dot)", text: "Due soon", color: "var(--status-masked-text)" },
  "overdue": { dot: "var(--status-blocked-dot)", text: "Overdue", color: "var(--status-blocked-text)" },
};

function ChangeLog() {
  const [expandedDiff, setExpandedDiff] = useState<number | null>(null);

  return (
    <div className="ip-changelog">
      {changeEvents.map((ev, i) => {
        const showDate = i === 0 || changeEvents[i - 1].date !== ev.date;
        return (
          <div key={i} className="ip-changelog-event">
            <div className="ip-cl-date-col">
              {showDate && <div className="ip-cl-date">{ev.date}</div>}
              <div className="ip-cl-time">{ev.time}</div>
            </div>
            <div className="ip-cl-avatar">{ev.initials}</div>
            <div className="ip-cl-body">
              <div className="ip-cl-action">{ev.action}</div>
              {ev.hasDiff && (
                <button
                  className="ip-cl-diff-btn"
                  onClick={() => setExpandedDiff(expandedDiff === i ? null : i)}
                >
                  {expandedDiff === i ? "Hide diff ↑" : "View diff →"}
                </button>
              )}
              {expandedDiff === i && (
                <div className="ip-diff-block">
                  <div className="ip-diff-line ip-diff-remove">- action: "tokenize"</div>
                  <div className="ip-diff-line ip-diff-add">+ action: "block"</div>
                  <div className="ip-diff-line ip-diff-ctx">  target: "CVV"</div>
                  <div className="ip-diff-line ip-diff-ctx">  framework: "PCI-DSS"</div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function ConfigSnapshot() {
  return (
    <div className="ip-snapshot">
      <div className="ip-snapshot-header">
        <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
          Current configuration as of Apr 01, 2026 · 14:32 UTC
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="ip-btn-ghost" style={{ fontSize: 12, padding: "5px 12px" }}>Export JSON</button>
          <button className="ip-btn-ghost" style={{ fontSize: 12, padding: "5px 12px" }}>Export PDF</button>
        </div>
      </div>

      <div className="ip-sheet ip-snapshot-grid">
        {[
          { label: "Active Frameworks", value: "PCI-DSS, HIPAA, GDPR" },
          { label: "Active Policies", value: "23 policies (18 from frameworks, 5 custom)" },
          { label: "Active Guardrails", value: "4 guardrails" },
          { label: "Last Modified", value: "Apr 01, 2026 · 14:32 UTC by admin@company.com" },
        ].map(row => (
          <div key={row.label} className="ip-snapshot-row">
            <div className="ip-snapshot-label">{row.label}</div>
            <div className="ip-snapshot-value">{row.value}</div>
          </div>
        ))}
      </div>

      <div className="ip-section-heading" style={{ marginTop: 24, marginBottom: 12 }}>All Active Policies</div>
      <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
        <table className="ip-table">
          <thead>
            <tr>
              <th>Policy</th>
              <th>Source</th>
              <th>Action</th>
              <th>Scope</th>
            </tr>
          </thead>
          <tbody>
            {[
              ["Credit Card Detection", "PCI-DSS", "Tokenize", "All agents"],
              ["SSN Masking", "HIPAA", "Mask", "All agents"],
              ["PHI Detection", "HIPAA", "Mask", "All agents"],
              ["IBAN Block", "PCI-DSS", "Block", "3 agents"],
              ["Employee ID Detection", "Custom", "Mask", "2 agents"],
              ["GDPR Personal Data", "GDPR", "Mask", "All agents"],
            ].map(([name, src, action, scope]) => (
              <tr key={name}>
                <td style={{ fontWeight: 500, fontSize: 13 }}>{name}</td>
                <td><span className={src === "Custom" ? "" : "ip-tag"} style={{ fontFamily: "var(--font-sans)", fontSize: src === "Custom" ? 12 : undefined, color: src === "Custom" ? "var(--text-tertiary)" : undefined, fontStyle: src === "Custom" ? "italic" : undefined }}>{src}</span></td>
                <td style={{ fontSize: 13 }}>{action}</td>
                <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{scope}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReviewSchedule() {
  return (
    <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
      <table className="ip-table">
        <thead>
          <tr>
            <th>Framework</th>
            <th>Last Reviewed</th>
            <th>Next Due</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {frameworks.map(fw => {
            const s = statusConfig[fw.status];
            return (
              <tr key={fw.name}>
                <td style={{ fontWeight: 500 }}>{fw.name}</td>
                <td style={{ color: "var(--text-secondary)", fontSize: 13 }}>{fw.lastReviewed}</td>
                <td style={{ color: fw.status === "overdue" ? "var(--status-blocked-text)" : fw.status === "due-soon" ? "var(--status-masked-text)" : "var(--text-secondary)", fontSize: 13 }}>
                  {fw.nextDue}
                </td>
                <td>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, color: s.color }}>
                    <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.dot, display: "inline-block" }} />
                    {s.text}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function Governance() {
  const [tab, setTab] = useState<Tab>("changelog");
  const [activePage, setActivePage] = useState<any>("governance");

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Governance</div>
          <div className="ip-page-subtitle">Configuration history, change log, and compliance evidence</div>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-tabs">
          {([["changelog", "Change Log"], ["snapshot", "Configuration Snapshot"], ["schedule", "Review Schedule"]] as [Tab, string][]).map(([id, label]) => (
            <button
              key={id}
              className={`ip-tab${tab === id ? " ip-tab--active" : ""}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="ip-tab-content">
          {tab === "changelog" && <ChangeLog />}
          {tab === "snapshot" && <ConfigSnapshot />}
          {tab === "schedule" && <ReviewSchedule />}
        </div>
      </div>
    </AppShell>
  );
}
