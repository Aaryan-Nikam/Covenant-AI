import React from "react";
import "./_shared/_shared.css";
import "./GovAnalytics.css";

const METRICS = [
  { label: "Active Agent Instances", value: "14", trend: "+2", status: "passed" },
  { label: "Total LLM Tokens Used", value: "1.2M", trend: "0.1M", status: "neutral" },
  { label: "Avg Execution Latency", value: "240ms", trend: "-12ms", status: "passed" },
  { label: "Guardrail Blocks (24h)", value: "3", trend: "-1", status: "blocked" },
];

import { AppShell } from "./_shared/AppShell";

export function GovAnalytics() {
  return (
    <AppShell>
      <div className="ip-page">
        <div className="ip-page-header">
          <div className="ip-page-header-left">
            <h1 className="ip-page-title">Agent Analytics</h1>
            <p className="ip-page-subtitle">Governance metrics, execution telemetry, and security performance.</p>
          </div>
        </div>

        <div className="ip-content">
          <div className="ip-gov-metrics-grid">
            {METRICS.map((m) => (
              <div key={m.label} className="ip-card ip-metric-card">
                <div className="ip-metric-label">{m.label}</div>
                <div className="ip-metric-value-row">
                  <div className="ip-metric-value">{m.value}</div>
                  <div className={`ip-metric-trend ip-metric-trend--${m.status}`}>
                    {m.trend}
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="ip-sheet ip-gov-charts">
            <div className="ip-section-heading">Agent Execution Telemetry (Last 30 Days)</div>
            <div className="ip-gov-chart-placeholder">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" style={{ color: 'var(--text-tertiary)' }}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 3v18h18" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M18 17V9" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 17V5" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M8 17v-3" />
              </svg>
              <p>Telemetry visualization will render here once live connection is established.</p>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
