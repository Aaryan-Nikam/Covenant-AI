import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Dashboard.css";

type DateRange = "1d" | "7d" | "30d" | "all";

const kpis = [
  { label: "Total Requests", value: "48,291", delta: "+12% vs last period", up: true },
  { label: "Masked", value: "3,847", delta: "8.0% of requests", up: null },
  { label: "Blocked", value: "214", delta: "0.44% of requests", up: null },
  { label: "Avg Latency", value: "138ms", delta: "−6ms vs last period", up: true },
];

const requestData = [
  { h: "00", v: 18 }, { h: "02", v: 9 }, { h: "04", v: 4 }, { h: "06", v: 6 },
  { h: "08", v: 42 }, { h: "10", v: 88 }, { h: "12", v: 112 }, { h: "14", v: 136 },
  { h: "16", v: 104 }, { h: "18", v: 78 }, { h: "20", v: 54 }, { h: "22", v: 31 },
];

const latencyData = [
  { h: "00", p50: 88, p95: 142, p99: 201 },
  { h: "02", p50: 92, p95: 148, p99: 188 },
  { h: "04", p50: 76, p95: 118, p99: 156 },
  { h: "06", p50: 84, p95: 131, p99: 178 },
  { h: "08", p50: 118, p95: 187, p99: 264 },
  { h: "10", p50: 134, p95: 214, p99: 312 },
  { h: "12", p50: 142, p95: 228, p99: 334 },
  { h: "14", p50: 138, p95: 221, p99: 318 },
  { h: "16", p50: 129, p95: 204, p99: 291 },
  { h: "18", p50: 112, p95: 178, p99: 248 },
  { h: "20", p50: 98, p95: 157, p99: 218 },
  { h: "22", p50: 86, p95: 138, p99: 192 },
];

function MiniLineChart({ data, color = "#1A7A4A", height = 80 }: {
  data: number[];
  color?: string;
  height?: number;
}) {
  const max = Math.max(...data);
  const min = Math.min(...data);
  const range = max - min || 1;
  const w = 100;
  const h = height;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 8) - 4;
    return `${x},${y}`;
  });
  const pathD = `M${pts.join(" L")}`;
  const areaD = `M${pts[0]} L${pts.join(" L")} L${(data.length - 1) / (data.length - 1) * w},${h} L0,${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ width: "100%", height }}>
      <defs>
        <linearGradient id={`grad-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.12" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#grad-${color.replace("#", "")})`} />
      <path d={pathD} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

function BarChart({ data }: { data: typeof requestData }) {
  const max = Math.max(...data.map(d => d.v));
  return (
    <div className="ip-bar-chart">
      {data.map((d) => (
        <div key={d.h} className="ip-bar-col">
          <div className="ip-bar-wrap">
            <div
              className="ip-bar"
              style={{ height: `${(d.v / max) * 100}%` }}
            />
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
  const h = 120;
  const w = 100;

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

const recentLogs = [
  { timestamp: "14:32:07", tenant: "Acme Corp", outcome: "masked" as const, detected: ["CREDIT_CARD"], latency: 142 },
  { timestamp: "14:31:54", tenant: "Acme Corp", outcome: "passed" as const, detected: [], latency: 38 },
  { timestamp: "14:31:22", tenant: "Globex Ltd", outcome: "blocked" as const, detected: ["SSN"], latency: 201 },
  { timestamp: "14:30:48", tenant: "Initech", outcome: "masked" as const, detected: ["PHONE"], latency: 97 },
  { timestamp: "14:30:31", tenant: "Acme Corp", outcome: "passed" as const, detected: [], latency: 44 },
];

const exploreCards = [
  {
    icon: "⊞",
    title: "Audit Log",
    tag: null,
    desc: "Full cryptographically-signed request history. Every proxy event, tamper-evident.",
  },
  {
    icon: "≋",
    title: "Test Console",
    tag: "Try it",
    desc: "Paste any text and see exactly what Ironpass detects and sanitizes in real time.",
  },
  {
    icon: "◎",
    title: "Frameworks",
    tag: null,
    desc: "Activate PCI-DSS, HIPAA, GDPR and other compliance frameworks with one toggle.",
  },
  {
    icon: "⊡",
    title: "API Keys",
    tag: null,
    desc: "Issue and manage proxy credentials. Keys are shown once — store them securely.",
  },
];

export function Dashboard() {
  const [range, setRange] = useState<DateRange>("7d");
  const [activePage, setActivePage] = useState<any>("dashboard");

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Dashboard</div>
          <div className="ip-page-subtitle">Proxy traffic overview and system health</div>
        </div>
        <div className="ip-page-header-actions">
          <div className="ip-date-range-group">
            <button className="ip-btn-ghost ip-date-range-pill">Pick a date range ▾</button>
            {(["1d", "7d", "30d"] as DateRange[]).map(r => (
              <button
                key={r}
                className={`ip-date-tab${range === r ? " ip-date-tab--active" : ""}`}
                onClick={() => setRange(r)}
              >
                {r}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="ip-content">
        {/* KPI Row */}
        <div className="ip-kpi-row">
          {kpis.map((k) => (
            <div key={k.label} className="ip-sheet ip-kpi-card">
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
                <div className="ip-chart-count">48,291</div>
              </div>
              <button className="ip-btn-primary" style={{ fontSize: 12, padding: "6px 14px" }}>
                View Audit Log →
              </button>
            </div>
            <div className="ip-chart-body">
              <BarChart data={requestData} />
            </div>
            <div className="ip-chart-footer">
              <div className="ip-chart-legend">
                <span className="ip-legend-dot" style={{ background: "#1A7A4A" }} />
                <span>TOTAL REQUESTS</span>
              </div>
              <div className="ip-chart-breakdown">
                View Breakdown
                <label className="ip-toggle" style={{ marginLeft: 8 }}>
                  <input type="checkbox" />
                  <span className="ip-toggle-track" />
                  <span className="ip-toggle-thumb" />
                </label>
              </div>
            </div>
          </div>

          <div className="ip-sheet ip-chart-panel">
            <div className="ip-chart-header">
              <div>
                <div className="ip-chart-title">Latency</div>
                <div className="ip-chart-count">138ms avg</div>
              </div>
              <div className="ip-latency-legend">
                <span><span className="ip-legend-dot" style={{ background: "#1A7A4A" }} />p50</span>
                <span><span className="ip-legend-dot" style={{ background: "#141414" }} />p95</span>
                <span><span className="ip-legend-dot" style={{ background: "#EF4444" }} />p99</span>
              </div>
            </div>
            <div className="ip-chart-body">
              <MultiLineChart data={latencyData} />
            </div>
            <div className="ip-chart-footer">
              <div className="ip-chart-legend">
                <span className="ip-legend-dot" style={{ background: "#141414" }} />
                <span>LATENCY PERCENTILES</span>
              </div>
              <div className="ip-chart-breakdown">
                View Breakdown
                <label className="ip-toggle" style={{ marginLeft: 8 }}>
                  <input type="checkbox" />
                  <span className="ip-toggle-track" />
                  <span className="ip-toggle-thumb" />
                </label>
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
                <th>Tenant</th>
                <th>Outcome</th>
                <th>Detected</th>
                <th>Latency</th>
              </tr>
            </thead>
            <tbody>
              {recentLogs.map((log, i) => (
                <tr key={i}>
                  <td><span className="ip-mono" style={{ fontSize: 12 }}>{log.timestamp}</span></td>
                  <td><span style={{ fontSize: 13 }}>{log.tenant}</span></td>
                  <td>
                    <span className={`ip-badge ip-badge--${log.outcome}`}>
                      <span className="ip-badge-dot" />
                      {log.outcome.charAt(0).toUpperCase() + log.outcome.slice(1)}
                    </span>
                  </td>
                  <td>
                    {log.detected.length === 0
                      ? <span style={{ color: "var(--text-tertiary)", fontSize: 13 }}>—</span>
                      : log.detected.map(t => <span key={t} className="ip-tag">{t}</span>)
                    }
                  </td>
                  <td>
                    <span className={`ip-mono ip-latency--${log.latency < 200 ? "normal" : log.latency < 400 ? "warn" : "danger"}`} style={{ fontSize: 12 }}>
                      {log.latency}ms
                    </span>
                  </td>
                </tr>
              ))}
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
