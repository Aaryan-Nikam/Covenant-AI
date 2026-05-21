import React, { useState, useEffect, useCallback } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./AuditLog.css";
import {
  fetchAuditLog,
  verifyAuditChain,
  type AuditEntry,
} from "../../../lib/api";

type OutcomeType = "passed" | "masked" | "blocked" | "error";

// ---------------------------------------------------------------------------
// Fallback mock data (dev mode without backend)
// ---------------------------------------------------------------------------
const MOCK_LOGS = [
  { entry_id: "log_a1b2c3d4", timestamp: "2026-04-01T14:32:07Z", agent_id: "agent_prod_v2_a9f3", outcome: "masked" as OutcomeType, detections_count: 2, actions_count: 2, was_blocked: false, latency_ms: 142, rulesets_used: ["pci_dss"] },
  { entry_id: "log_e5f6g7h8", timestamp: "2026-04-01T14:31:54Z", agent_id: "agent_prod_v2_a9f3", outcome: "passed" as OutcomeType, detections_count: 0, actions_count: 0, was_blocked: false, latency_ms: 38, rulesets_used: [] },
  { entry_id: "log_i9j0k1l2", timestamp: "2026-04-01T14:31:22Z", agent_id: "agent_stg_b7c2_x1", outcome: "blocked" as OutcomeType, detections_count: 3, actions_count: 1, was_blocked: true, latency_ms: 201, rulesets_used: ["hipaa", "pci_dss"] },
  { entry_id: "log_m3n4o5p6", timestamp: "2026-04-01T14:30:48Z", agent_id: "agent_prod_c4d3", outcome: "masked" as OutcomeType, detections_count: 1, actions_count: 1, was_blocked: false, latency_ms: 97, rulesets_used: ["gdpr"] },
  { entry_id: "log_q7r8s9t0", timestamp: "2026-04-01T14:30:31Z", agent_id: "agent_prod_v2_a9f3", outcome: "passed" as OutcomeType, detections_count: 0, actions_count: 0, was_blocked: false, latency_ms: 44, rulesets_used: [] },
  { entry_id: "log_u1v2w3x4", timestamp: "2026-04-01T14:29:55Z", agent_id: "agent_stg_b7c2_x1", outcome: "error" as OutcomeType, detections_count: 0, actions_count: 0, was_blocked: false, latency_ms: 589, rulesets_used: [] },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function Badge({ outcome }: { outcome: OutcomeType }) {
  return (
    <span className={`ip-badge ip-badge--${outcome}`}>
      <span className="ip-badge-dot" />
      {{ passed: "Passed", masked: "Masked", blocked: "Blocked", error: "Error" }[outcome]}
    </span>
  );
}

function LatencyCell({ ms }: { ms: number }) {
  const cls = ms < 200 ? "ip-latency--normal" : ms < 400 ? "ip-latency--warn" : "ip-latency--danger";
  return <span className={`ip-mono ${cls}`} style={{ fontSize: 12 }}>{ms}ms</span>;
}

function SummaryBar({ entries }: { entries: typeof MOCK_LOGS }) {
  const counts = entries.reduce(
    (acc, e) => { acc[e.outcome as OutcomeType] = (acc[e.outcome as OutcomeType] || 0) + 1; return acc; },
    { passed: 0, masked: 0, blocked: 0, error: 0 } as Record<OutcomeType, number>
  );
  const total = entries.length || 1;
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
          <div key={k} className="ip-summary-segment"
            style={{ width: `${(counts[k] / total) * 100}%`, background: colors[k] }}
            title={`${counts[k]} ${k}`} />
        ))}
      </div>
      <div className="ip-summary-counts">
        {(Object.keys(counts) as OutcomeType[]).map(k => (
          <span key={k} className="ip-summary-count">
            <span className="ip-summary-dot" style={{ background: colors[k] }} />
            {counts[k]} {{ passed: "Passed", masked: "Masked", blocked: "Blocked", error: "Error" }[k]}
          </span>
        ))}
        <span className="ip-summary-total">{entries.length} total</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------
export function AuditLog() {
  const [activePage, setActivePage] = useState<any>("audit");
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [apiLive, setApiLive] = useState(false);
  const [outcomeFilter, setOutcomeFilter] = useState("");
  const [agentFilter, setAgentFilter] = useState("");
  const [verifyStatus, setVerifyStatus] = useState<string | null>(null);
  const [verifying, setVerifying] = useState(false);
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetchAuditLog({
        limit: PAGE_SIZE,
        offset: page * PAGE_SIZE,
        outcome: outcomeFilter || undefined,
        agent_id: agentFilter || undefined,
      });
      setEntries(resp.entries);
      setTotal(resp.total);
      setApiLive(true);
    } catch {
      setEntries(MOCK_LOGS as AuditEntry[]);
      setTotal(MOCK_LOGS.length);
    } finally {
      setLoading(false);
    }
  }, [page, outcomeFilter, agentFilter]);

  useEffect(() => { load(); }, [load]);

  const handleVerify = async () => {
    setVerifying(true);
    setVerifyStatus(null);
    try {
      const report = await verifyAuditChain(100);
      setVerifyStatus(report.summary);
    } catch {
      setVerifyStatus("⚠️ Backend unreachable — cannot verify chain in demo mode.");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Audit Log</div>
          <div className="ip-page-subtitle">
            Cryptographically signed, tamper-evident record of all proxy traffic
            {apiLive && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--status-passed-dot)" }}>● Live</span>}
            {!apiLive && !loading && <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-tertiary)" }}>● Demo mode</span>}
          </div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost">Export CSV</button>
          <button className="ip-btn-ghost" onClick={handleVerify} disabled={verifying}>
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M6.5 1L2 3.5V7.5C2 9.9 4.1 11.9 6.5 12.7C8.9 11.9 11 9.9 11 7.5V3.5L6.5 1Z"
                stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" fill="none" />
            </svg>
            {verifying ? "Verifying…" : "Verify Chain"}
          </button>
        </div>
      </div>

      {verifyStatus && (
        <div style={{ margin: "0 24px 16px", padding: "12px 16px", background: "var(--bg-elevated)", borderRadius: 8, fontSize: 13, borderLeft: "3px solid var(--status-passed-dot)" }}>
          {verifyStatus}
        </div>
      )}

      <div className="ip-content" style={{ display: "flex", flexDirection: "column" }}>
        <SummaryBar entries={entries.length ? entries : MOCK_LOGS as AuditEntry[]} />

        <div className="ip-filter-bar">
          <select
            className="ip-filter-pill"
            value={outcomeFilter}
            onChange={e => { setOutcomeFilter(e.target.value); setPage(0); }}
            style={{ background: "transparent", border: "1px solid var(--border-default)", color: "inherit" }}
          >
            <option value="">All outcomes</option>
            <option value="passed">Passed</option>
            <option value="masked">Masked</option>
            <option value="blocked">Blocked</option>
            <option value="error">Error</option>
          </select>
          <input
            className="ip-filter-pill"
            style={{ border: "1px solid var(--border-default)", fontFamily: "var(--font-mono)", fontSize: 12, minWidth: 200, background: "transparent", color: "inherit" }}
            placeholder="Filter by agent ID..."
            value={agentFilter}
            onChange={e => { setAgentFilter(e.target.value); setPage(0); }}
          />
          {total > PAGE_SIZE && (
            <div style={{ marginLeft: "auto", display: "flex", gap: 8, alignItems: "center", fontSize: 13, color: "var(--text-secondary)" }}>
              <button className="ip-btn-ghost" style={{ padding: "4px 10px" }} disabled={page === 0} onClick={() => setPage(p => p - 1)}>← Prev</button>
              <span>Page {page + 1} · {total} entries</span>
              <button className="ip-btn-ghost" style={{ padding: "4px 10px" }} disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage(p => p + 1)}>Next →</button>
            </div>
          )}
        </div>

        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
          <div className="ip-table-container">
            <table className="ip-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Agent</th>
                  <th>Outcome</th>
                  <th>Rulesets</th>
                  <th>Detections</th>
                  <th>Latency</th>
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 6 }).map((_, j) => (
                        <td key={j}><div style={{ height: 16, borderRadius: 4, background: "var(--bg-elevated)", opacity: 0.6 }} /></td>
                      ))}
                    </tr>
                  ))
                  : entries.map((e) => (
                    <tr key={e.entry_id}>
                      <td><span className="ip-mono" style={{ fontSize: 12 }}>{new Date(e.timestamp).toLocaleString()}</span></td>
                      <td><span className="ip-mono" style={{ fontSize: 11, color: "var(--text-secondary)" }} title={e.agent_id}>{e.agent_id.slice(0, 16)}…</span></td>
                      <td><Badge outcome={e.outcome} /></td>
                      <td>
                        {e.rulesets_used.length === 0
                          ? <span style={{ color: "var(--text-tertiary)", fontSize: 13 }}>—</span>
                          : e.rulesets_used.slice(0, 2).map(r => <span key={r} className="ip-tag" style={{ marginRight: 4 }}>{r.toUpperCase()}</span>)
                        }
                      </td>
                      <td><span style={{ fontSize: 13 }}>{e.detections_count > 0 ? `${e.detections_count} type${e.detections_count > 1 ? "s" : ""}` : <span style={{ color: "var(--text-tertiary)" }}>—</span>}</span></td>
                      <td><LatencyCell ms={e.latency_ms} /></td>
                    </tr>
                  ))
                }
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
