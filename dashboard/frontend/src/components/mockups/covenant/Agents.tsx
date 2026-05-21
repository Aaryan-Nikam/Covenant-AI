import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Agents.css";

interface Agent {
  id: string;
  name: string;
  environment: "production" | "staging" | "development";
  requests7d: number;
  blocked7d: number;
  avgLatency: number;
  lastSeen: string;
  status: "active" | "idle" | "inactive";
  rulesets: string[];
}

const agents: Agent[] = [
  { id: "agent_prod_v2_a9f3", name: "Production Agent v2", environment: "production", requests7d: 28471, blocked7d: 142, avgLatency: 138, lastSeen: "2 min ago", status: "active", rulesets: ["PCI-DSS", "HIPAA"] },
  { id: "agent_analytics_v1", name: "Analytics Agent", environment: "production", requests7d: 14220, blocked7d: 18, avgLatency: 94, lastSeen: "14 min ago", status: "active", rulesets: ["GDPR"] },
  { id: "agent_stg_b7c2_x1", name: "Staging Agent", environment: "staging", requests7d: 4891, blocked7d: 47, avgLatency: 162, lastSeen: "1 hr ago", status: "idle", rulesets: ["PCI-DSS", "HIPAA", "GDPR"] },
  { id: "agent_prod_c4d3", name: "Customer Support Bot", environment: "production", requests7d: 892, blocked7d: 7, avgLatency: 112, lastSeen: "3 hr ago", status: "active", rulesets: ["HIPAA"] },
  { id: "agent_dev_test", name: "Dev Test Agent", environment: "development", requests7d: 234, blocked7d: 0, avgLatency: 78, lastSeen: "2 days ago", status: "inactive", rulesets: [] },
];

const envColor: Record<Agent["environment"], string> = {
  production: "var(--status-passed-text)",
  staging: "var(--status-masked-text)",
  development: "var(--text-secondary)",
};
const envBg: Record<Agent["environment"], string> = {
  production: "var(--status-passed-bg)",
  staging: "var(--status-masked-bg)",
  development: "var(--bg-elevated)",
};
const statusDot: Record<Agent["status"], string> = {
  active: "var(--status-passed-dot)",
  idle: "var(--status-masked-dot)",
  inactive: "var(--text-tertiary)",
};

export function Agents() {
  const [selected, setSelected] = useState<string | null>("agent_prod_v2_a9f3");
  const [activePage, setActivePage] = useState<any>("agents");
  const selectedAgent = agents.find(a => a.id === selected);

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Agents</div>
          <div className="ip-page-subtitle">Registered proxy agents and their activity</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost">Register agent</button>
        </div>
      </div>

      <div className="ip-content" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        {/* Summary row */}
        <div className="ip-agents-summary">
          {[
            { label: "Total Agents", value: agents.length },
            { label: "Active Now", value: agents.filter(a => a.status === "active").length },
            { label: "Total Requests (7d)", value: "48,708" },
            { label: "Avg Latency", value: "117ms" },
          ].map(s => (
            <div key={s.label} className="ip-sheet ip-agent-stat">
              <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{s.label}</div>
              <div style={{ fontSize: 24, fontWeight: 500, color: "var(--text-primary)", marginTop: 4 }}>{s.value}</div>
            </div>
          ))}
        </div>

        {/* Main table */}
        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
          <table className="ip-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Environment</th>
                <th>Requests (7d)</th>
                <th>Blocked (7d)</th>
                <th>Avg Latency</th>
                <th>Last Seen</th>
                <th>Rulesets</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {agents.map(a => (
                <tr
                  key={a.id}
                  style={{ cursor: "pointer" }}
                  onClick={() => setSelected(selected === a.id ? null : a.id)}
                >
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ width: 7, height: 7, borderRadius: "50%", background: statusDot[a.status], flexShrink: 0, display: "inline-block" }} />
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>{a.name}</div>
                        <div className="ip-mono" style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{a.id.slice(0, 14)}...</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span style={{ fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 4, background: envBg[a.environment], color: envColor[a.environment] }}>
                      {a.environment}
                    </span>
                  </td>
                  <td className="ip-mono" style={{ fontSize: 13 }}>{a.requests7d.toLocaleString()}</td>
                  <td>
                    <span style={{ fontSize: 13, color: a.blocked7d > 0 ? "var(--status-blocked-text)" : "var(--text-tertiary)" }} className="ip-mono">{a.blocked7d}</span>
                  </td>
                  <td>
                    <span className={`ip-mono ip-latency--${a.avgLatency < 200 ? "normal" : "warn"}`} style={{ fontSize: 13 }}>{a.avgLatency}ms</span>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{a.lastSeen}</td>
                  <td>
                    <div style={{ display: "flex", gap: 4 }}>
                      {a.rulesets.length === 0
                        ? <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>None</span>
                        : a.rulesets.slice(0, 2).map(r => <span key={r} className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>{r}</span>)
                      }
                    </div>
                  </td>
                  <td><button className="ip-icon-btn">⋯</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Detail panel */}
        {selectedAgent && (
          <div className="ip-sheet ip-agent-detail">
            <div className="ip-agent-detail-header">
              <div>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{selectedAgent.name}</div>
                <div className="ip-mono" style={{ fontSize: 11, color: "var(--text-tertiary)", marginTop: 2 }}>{selectedAgent.id}</div>
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="ip-btn-ghost" style={{ fontSize: 12, padding: "5px 12px" }}>View logs →</button>
                <button className="ip-btn-ghost" style={{ fontSize: 12, padding: "5px 12px" }}>Edit rulesets</button>
              </div>
            </div>
            <div className="ip-agent-detail-grid">
              {[
                ["Status", <span style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12 }}><span style={{ width: 6, height: 6, borderRadius: "50%", background: statusDot[selectedAgent.status], display: "inline-block" }} />{selectedAgent.status}</span>],
                ["Environment", selectedAgent.environment],
                ["Requests (7d)", selectedAgent.requests7d.toLocaleString()],
                ["Blocked (7d)", selectedAgent.blocked7d],
                ["Avg Latency", `${selectedAgent.avgLatency}ms`],
                ["Last Seen", selectedAgent.lastSeen],
                ["Active Rulesets", selectedAgent.rulesets.join(", ") || "None"],
              ].map(([label, value]) => (
                <div key={String(label)} className="ip-agent-detail-row">
                  <span className="ip-agent-detail-label">{label}</span>
                  <span className="ip-agent-detail-value">{value}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
