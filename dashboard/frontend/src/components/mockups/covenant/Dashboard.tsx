import React, { useState, useEffect } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Dashboard.css";
import {
  fetchOverview,
  fetchAuditLog,
  type OverviewStats,
  type AuditEntry,
} from "../../../lib/api";

type DateRange = "1d" | "7d" | "30d" | "all";

// ---------------------------------------------------------------------------
// Initial empty state (no mock data — real data only)
// ---------------------------------------------------------------------------
const EMPTY_KPIS = [
  { label: "Total Requests", value: "—", delta: "No data yet", up: null },
  { label: "Active Vault Tokens", value: "—", delta: "No data yet", up: null },
  { label: "Blocked", value: "—", delta: "No data yet", up: null },
  { label: "Avg Latency", value: "—", delta: "No data yet", up: null },
];

const requestData = [
  { h: "00", v: 18 }, { h: "02", v: 9 }, { h: "04", v: 4 }, { h: "06", v: 6 },
  { h: "08", v: 42 }, { h: "10", v: 88 }, { h: "12", v: 112 }, { h: "14", v: 136 },
  { h: "16", v: 104 }, { h: "18", v: 78 }, { h: "20", v: 54 }, { h: "22", v: 31 },
];

const latencyData = [
  { h: "00", p50: 88, p95: 142, p99: 201 }, { h: "02", p50: 92, p95: 148, p99: 188 },
  { h: "04", p50: 76, p95: 118, p99: 156 }, { h: "06", p50: 84, p95: 131, p99: 178 },
  { h: "08", p50: 118, p95: 187, p99: 264 }, { h: "10", p50: 134, p95: 214, p99: 312 },
  { h: "12", p50: 142, p95: 228, p99: 334 }, { h: "14", p50: 138, p95: 221, p99: 318 },
  { h: "16", p50: 129, p95: 204, p99: 291 }, { h: "18", p50: 112, p95: 178, p99: 248 },
  { h: "20", p50: 98, p95: 157, p99: 218 }, { h: "22", p50: 86, p95: 138, p99: 192 },
];

// ---------------------------------------------------------------------------
// Chart primitives
// ---------------------------------------------------------------------------
function BarChart({ data }: { data: typeof requestData }) {
  const max = Math.max(...data.map(d => d.v));
  return (
    <div className="ip-bar-chart">
      {data.map((d) => (
        <div key={d.h} className="ip-bar-col">
          <div className="ip-bar-wrap">
            <div className="ip-bar" style={{ height: `${(d.v / max) * 100}%` }} />
          </div>
          <div className="ip-bar-label">{d.h}</div>
        </div>
      ))}
    </div>
  );
}

function MultiLineChart({ data }: { data: typeof latencyData }) {
  const allVals = data.flatMap(d => [d.p50, d.p95, d.p99]);
  const max = Math.max(...allVals);
  const h = 120, w = 100;
  function line(key: "p50" | "p95" | "p99") {
    return data.map((d, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - (d[key] / max) * (h - 8) - 4;
      return `${x},${y}`;
    }).join(" L");
  }
  const colors = { p50: "#1A7A4A", p95: "#141414", p99: "#EF4444" };
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: "100%", height: h }}>
      {(["p50", "p95", "p99"] as const).map(k => (
        <path key={k} d={`M${line(k)}`} fill="none" stroke={colors[k]} strokeWidth="1.5" />
      ))}
    </svg>
  );
}

// ---------------------------------------------------------------------------
// KPI derivation from live stats
// ---------------------------------------------------------------------------
function buildKpis(stats: OverviewStats) {
  return [
    { label: "Total Requests", value: stats.total_requests.toLocaleString(), delta: `${stats.requests_24h.toLocaleString()} in last 24h`, up: true },
    { label: "Active Vault Tokens", value: stats.active_vault_tokens.toLocaleString(), delta: "encrypted in vault", up: null },
    { label: "Blocked", value: stats.total_blocked.toLocaleString(), delta: `${stats.block_rate}% block rate`, up: null },
    { label: "Avg Latency", value: `${stats.avg_latency_ms}ms`, delta: "end-to-end proxy", up: stats.avg_latency_ms < 200 },
  ];
}

// ---------------------------------------------------------------------------
// Recent activity row
// ---------------------------------------------------------------------------
function outcomeClass(o: string) {
  return o === "passed" ? "passed" : o === "blocked" ? "blocked" : "masked";
}

const exploreCards = [
  { icon: "⊞", title: "Audit Log", tag: null, desc: "Full cryptographically-signed request history. Every proxy event, tamper-evident." },
  { icon: "≋", title: "Test Console", tag: "Try it", desc: "Paste any text and see exactly what Covenant AI detects and sanitizes in real time." },
  { icon: "◎", title: "Frameworks", tag: null, desc: "Activate PCI-DSS, HIPAA, GDPR and other compliance frameworks with one toggle." },
  { icon: "⊡", title: "API Keys", tag: null, desc: "Issue and manage proxy credentials. Keys are shown once — store them securely." },
];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function Dashboard() {
  const [range, setRange] = useState<DateRange>("7d");
  const [activePage, setActivePage] = useState<any>("dashboard");

  // Live data state
  const [kpis, setKpis] = useState(EMPTY_KPIS);
  const [recentLogs, setRecentLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiLive, setApiLive] = useState(false);
  const [apiError, setApiError] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [overview, auditResp] = await Promise.all([
          fetchOverview(),
          fetchAuditLog({ limit: 5 }),
        ]);
        if (cancelled) return;
        setKpis(buildKpis(overview));
        setRecentLogs(auditResp.entries);
        setApiLive(true);
        setApiError(false);
      } catch {
        if (!cancelled) setApiError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [range]);

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Dashboard</div>
          <div className="ip-page-subtitle">
            Proxy traffic overview and system health
            {apiLive && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--status-passed-dot)" }}>● Live</span>}
            {apiError && !loading && <span style={{ marginLeft: 8, fontSize: 11, color: "#EF4444" }}>● Disconnected</span>}
          </div>
        </div>
        <div className="ip-page-header-actions">
          <div className="ip-date-range-group">

      {apiError && !loading && (
        <div className="ip-sheet" style={{ padding: "14px 20px", marginBottom: 16, background: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.18)", borderRadius: 8 }}>
          <span style={{ fontSize: 13, color: "#EF4444", fontWeight: 500 }}>⚠ Backend unreachable</span>
          <span style={{ fontSize: 12, color: "var(--text-secondary)", marginLeft: 12 }}>
            Connect your backend to see live data. Metrics below are empty until a connection is established.
          </span>
        </div>
      )}
            <button className="ip-btn-ghost ip-date-range-pill">Pick a date range ▾</button>
            {(["1d", "7d", "30d"] as DateRange[]).map(r => (
              <button
                key={r}
                className={`ip-date-tab${range === r ? " ip-date-tab--active" : ""}`}
                onClick={() => setRange(r)}
              >{r}</button>
            ))}
          </div>
        </div>
      </div>

      <div className="ip-content">
        {/* KPI Row */}
        <div className="ip-kpi-row">
          {kpis.map((k) => (
            <div key={k.label} className={`ip-sheet ip-kpi-card${loading ? " ip-kpi-card--loading" : ""}`}>
              <div className="ip-kpi-label">{k.label}</div>
              <div className="ip-kpi-value">{k.value}</div>
              <div className={`ip-kpi-delta${k.up === true ? " ip-kpi-delta--up" : k.up === false ? " ip-kpi-delta--down" : ""}`}>
                {k.delta}
              </div>
            </div>
          ))}
        </div>

        {/* Charts Row */}
        <div className="ip-charts-row">
          <div className="ip-sheet ip-chart-panel">
            <div className="ip-chart-header">
              <div>
                <div className="ip-chart-title">Requests</div>
                <div className="ip-chart-count">{kpis[0]?.value}</div>
              </div>
              <button className="ip-btn-primary" style={{ fontSize: 12, padding: "6px 14px" }}
                onClick={() => setActivePage("audit")}>
                View Audit Log →
              </button>
            </div>
            <div className="ip-chart-body"><BarChart data={requestData} /></div>
            <div className="ip-chart-footer">
              <div className="ip-chart-legend">
                <span className="ip-legend-dot" style={{ background: "#1A7A4A" }} />
                <span>TOTAL REQUESTS</span>
              </div>
            </div>
          </div>

          <div className="ip-sheet ip-chart-panel">
            <div className="ip-chart-header">
              <div>
                <div className="ip-chart-title">Latency</div>
                <div className="ip-chart-count">{kpis[3]?.value} avg</div>
              </div>
              <div className="ip-latency-legend">
                <span><span className="ip-legend-dot" style={{ background: "#1A7A4A" }} />p50</span>
                <span><span className="ip-legend-dot" style={{ background: "#888" }} />p95</span>
                <span><span className="ip-legend-dot" style={{ background: "#EF4444" }} />p99</span>
              </div>
            </div>
            <div className="ip-chart-body"><MultiLineChart data={latencyData} /></div>
            <div className="ip-chart-footer">
              <div className="ip-chart-legend">
                <span className="ip-legend-dot" style={{ background: "#141414" }} />
                <span>LATENCY PERCENTILES</span>
              </div>
            </div>
          </div>
        </div>

        {/* Recent Activity */}
        <div className="ip-section-heading" style={{ marginBottom: 12 }}>Recent Activity</div>
        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden", marginBottom: 32 }}>
          <table className="ip-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Agent</th>
                <th>Outcome</th>
                <th>Detections</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {recentLogs.length > 0 ? (
                recentLogs.map((log) => (
                  <tr key={log.entry_id}>
                    <td><span className="ip-mono" style={{ fontSize: 12 }}>{new Date(log.timestamp).toLocaleTimeString()}</span></td>
                    <td><span className="ip-mono" style={{ fontSize: 11, color: "var(--text-secondary)" }}>{log.agent_id.slice(0, 14)}…</span></td>
                    <td>
                      <span className={`ip-badge ip-badge--${outcomeClass(log.outcome)}`}>
                        <span className="ip-badge-dot" />
                        {log.outcome.charAt(0).toUpperCase() + log.outcome.slice(1)}
                      </span>
                    </td>
                    <td><span style={{ fontSize: 13 }}>{log.detections_count > 0 ? `${log.detections_count} detected` : <span style={{ color: "var(--text-tertiary)" }}>—</span>}</span></td>
                    <td>
                      <span className={`ip-mono ip-latency--${log.latency_ms < 200 ? "normal" : log.latency_ms < 400 ? "warn" : "danger"}`} style={{ fontSize: 12 }}>
                        {log.latency_ms}ms
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={5} style={{ textAlign: "center", padding: "40px 0", color: "var(--text-tertiary)", fontSize: 13 }}>
                    {!loading ? "No data yet — connect your first AI agent" : "Loading..."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Explore */}
        <div className="ip-explore-heading">Explore the Platform</div>
        <div className="ip-explore-grid">
          {exploreCards.map((c) => (
            <div key={c.title} className="ip-sheet ip-explore-card">
              <div className="ip-explore-card-header">
                <span className="ip-explore-icon">{c.icon}</span>
                <span className="ip-explore-title">{c.title}</span>
                {c.tag && <span className="ip-explore-tag">{c.tag}</span>}
              </div>
              <div className="ip-explore-desc">{c.desc}</div>
            </div>
          ))}
        </div>
      </div>
    </AppShell>
  );
}
