import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Reports.css";

interface Report {
  id: string;
  name: string;
  type: string;
  generated: string;
  period: string;
  size: string;
}

const reports: Report[] = [
  { id: "r1", name: "PCI-DSS Compliance Report — Q1 2026", type: "Compliance", generated: "Apr 01, 2026", period: "Jan – Mar 2026", size: "2.4 MB" },
  { id: "r2", name: "HIPAA Audit Summary — March 2026", type: "Compliance", generated: "Apr 01, 2026", period: "Mar 2026", size: "1.1 MB" },
  { id: "r3", name: "PII Detection Analytics — March 2026", type: "Analytics", generated: "Apr 01, 2026", period: "Mar 2026", size: "840 KB" },
  { id: "r4", name: "Violation Incident Report — W13 2026", type: "Security", generated: "Mar 31, 2026", period: "Mar 24–30, 2026", size: "312 KB" },
  { id: "r5", name: "PCI-DSS Compliance Report — Q4 2025", type: "Compliance", generated: "Jan 02, 2026", period: "Oct – Dec 2025", size: "2.1 MB" },
  { id: "r6", name: "Agent Traffic Summary — February 2026", type: "Analytics", generated: "Mar 01, 2026", period: "Feb 2026", size: "560 KB" },
];

const reportTypes = ["All", "Compliance", "Analytics", "Security"];
const typeColor: Record<string, string> = {
  Compliance: "var(--status-passed-text)",
  Analytics: "#1D4ED8",
  Security: "var(--status-masked-text)",
};
const typeBg: Record<string, string> = {
  Compliance: "var(--status-passed-bg)",
  Analytics: "#EFF6FF",
  Security: "var(--status-masked-bg)",
};

export function Reports() {
  const [filter, setFilter] = useState("All");
  const [activePage, setActivePage] = useState<any>("reports");

  const filtered = filter === "All" ? reports : reports.filter(r => r.type === filter);

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Reports</div>
          <div className="ip-page-subtitle">Generated compliance and analytics reports</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-primary">Generate report</button>
        </div>
      </div>

      <div className="ip-content">
        {/* Scheduled reports */}
        <div className="ip-section-heading" style={{ marginBottom: 12 }}>Scheduled Reports</div>
        <div className="ip-reports-schedule-row">
          {[
            { icon: "⊞", label: "Monthly Compliance Summary", next: "May 01, 2026", freq: "Monthly" },
            { icon: "≋", label: "Weekly Violation Digest", next: "Apr 07, 2026", freq: "Weekly" },
            { icon: "◎", label: "Quarterly PCI-DSS Audit", next: "Jul 01, 2026", freq: "Quarterly" },
          ].map(s => (
            <div key={s.label} className="ip-sheet ip-scheduled-card">
              <div style={{ fontSize: 18, marginBottom: 8, color: "var(--text-secondary)" }}>{s.icon}</div>
              <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>{s.label}</div>
              <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{s.freq} · Next: {s.next}</div>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
          {reportTypes.map(t => (
            <button
              key={t}
              className={`ip-tg-btn${filter === t ? " ip-tg-btn--active" : ""}`}
              onClick={() => setFilter(t)}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Reports table */}
        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
          <table className="ip-table">
            <thead>
              <tr>
                <th>Report Name</th>
                <th>Type</th>
                <th>Period</th>
                <th>Generated</th>
                <th>Size</th>
                <th style={{ width: 80 }}></th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(r => (
                <tr key={r.id}>
                  <td style={{ fontWeight: 500, fontSize: 13 }}>{r.name}</td>
                  <td>
                    <span style={{ fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 4, background: typeBg[r.type], color: typeColor[r.type] }}>
                      {r.type}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{r.period}</td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{r.generated}</td>
                  <td className="ip-mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>{r.size}</td>
                  <td>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className="ip-btn-ghost" style={{ fontSize: 11, padding: "3px 10px" }}>Download</button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </AppShell>
  );
}
