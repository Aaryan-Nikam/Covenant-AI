import React, { useState, useEffect } from "react";
import { AppShell } from "./_shared/AppShell";
import {
  fetchSLAPolicies,
  createSLAPolicy,
  deleteSLAPolicy,
  updateSLAPolicy,
  fetchSLABreaches,
  fetchSLALiveMetrics,
} from "../../../lib/api";
import "./SLA.css";

const METRIC_TYPES = [
  { value: "LATENCY_P95", label: "Latency P95 (ms)" },
  { value: "LATENCY_P99", label: "Latency P99 (ms)" },
  { value: "ERROR_RATE", label: "Error Rate (%)" },
  { value: "BLOCK_RATE", label: "Block Rate (%)" },
  { value: "COST_PER_SESSION", label: "Cost / Session (USD)" },
];

export function SLA() {
  const [activeTab, setActiveTab] = useState<"policies" | "breaches" | "live">("live");

  return (
    <AppShell activePage="sla">
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">SLA Monitoring</div>
          <div className="ip-page-subtitle">
            Define performance thresholds for your AI agent. Get notified when traffic breaches your SLAs.
          </div>
        </div>
      </div>

      <div className="gdpr-tabs">
        <button className={`gdpr-tab ${activeTab === "live" ? "active" : ""}`} onClick={() => setActiveTab("live")}>
          Live Metrics
        </button>
        <button className={`gdpr-tab ${activeTab === "policies" ? "active" : ""}`} onClick={() => setActiveTab("policies")}>
          Policies
        </button>
        <button className={`gdpr-tab ${activeTab === "breaches" ? "active" : ""}`} onClick={() => setActiveTab("breaches")}>
          Breach History
        </button>
      </div>

      <div className="ip-content">
        {activeTab === "live" && <LiveMetrics />}
        {activeTab === "policies" && <Policies />}
        {activeTab === "breaches" && <BreachHistory />}
      </div>
    </AppShell>
  );
}

// ---------------------------------------------------------------------------
// Live Metrics
// ---------------------------------------------------------------------------

function LiveMetrics() {
  const [metrics, setMetrics] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchSLALiveMetrics()
      .then((d) => setMetrics(d.metrics || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="ip-sheet"><p className="ip-empty-state">Loading live metrics...</p></div>;
  if (error) return <div className="ip-sheet"><p className="sla-error">Backend unreachable — {error}</p></div>;

  if (metrics.length === 0) {
    return (
      <div className="ip-sheet">
        <p className="ip-empty-state">No active SLA policies — create one in the Policies tab.</p>
      </div>
    );
  }

  return (
    <div className="sla-metrics-grid">
      {metrics.map((m) => (
        <div key={m.policy_id} className={`sla-metric-card sla-metric-card--${m.status}`}>
          <div className="sla-metric-header">
            <span className="sla-metric-name">{m.policy_name}</span>
            <span className={`sla-status-dot sla-status-dot--${m.status}`} />
          </div>
          <div className="sla-metric-type">{m.metric_type.replace(/_/g, " ")}</div>
          <div className="sla-metric-value">
            {m.current_value !== null
              ? Number(m.current_value).toFixed(3)
              : "—"}
          </div>
          <div className="sla-metric-threshold">Threshold: {m.threshold_value}</div>
          <div className="sla-metric-status-badge">
            {m.status === "ok" && <span className="ip-badge ip-badge--passed"><span className="ip-badge-dot" />OK</span>}
            {m.status === "breached" && <span className="ip-badge ip-badge--blocked"><span className="ip-badge-dot" />BREACHED</span>}
            {m.status === "no_data" && <span className="ip-badge ip-badge--masked"><span className="ip-badge-dot" />NO DATA</span>}
          </div>
          <div className="sla-metric-ts">Evaluated: {new Date(m.last_evaluated).toLocaleTimeString()}</div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Policies
// ---------------------------------------------------------------------------

function Policies() {
  const [policies, setPolicies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    metric_type: "LATENCY_P95",
    threshold_value: 500,
    window_minutes: 60,
    notification_email: "",
    webhook_url: "",
    is_active: true,
  });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    setLoading(true);
    fetchSLAPolicies()
      .then((d) => setPolicies(d.policies || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async () => {
    setSubmitting(true);
    try {
      await createSLAPolicy({
        ...form,
        threshold_value: Number(form.threshold_value),
        window_minutes: Number(form.window_minutes),
        notification_email: form.notification_email || undefined,
        webhook_url: form.webhook_url || undefined,
      });
      setShowForm(false);
      load();
    } catch (e: any) {
      alert("Error: " + e.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (policy: any) => {
    try {
      await updateSLAPolicy(policy.id, { is_active: !policy.is_active });
      load();
    } catch (e: any) {
      alert("Error: " + e.message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("Delete this policy?")) return;
    try {
      await deleteSLAPolicy(id);
      load();
    } catch (e: any) {
      alert(e.message);
    }
  };

  if (loading) return <div className="ip-sheet"><p className="ip-empty-state">Loading...</p></div>;

  return (
    <div className="ip-sheet">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
        <div className="gdpr-section-title">SLA Policies</div>
        <button className="ip-btn-primary" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Cancel" : "+ New Policy"}
        </button>
      </div>

      {showForm && (
        <div className="sla-form">
          <div className="sla-form-row">
            <label>Name</label>
            <input className="ip-input" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="e.g. Premium Tier Latency" />
          </div>
          <div className="sla-form-row">
            <label>Metric Type</label>
            <select className="ip-input" value={form.metric_type} onChange={e => setForm({ ...form, metric_type: e.target.value })}>
              {METRIC_TYPES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div className="sla-form-row">
            <label>Threshold</label>
            <input className="ip-input" type="number" value={form.threshold_value} onChange={e => setForm({ ...form, threshold_value: Number(e.target.value) })} />
          </div>
          <div className="sla-form-row">
            <label>Window (minutes)</label>
            <input className="ip-input" type="number" value={form.window_minutes} onChange={e => setForm({ ...form, window_minutes: Number(e.target.value) })} />
          </div>
          <div className="sla-form-row">
            <label>Notification Email</label>
            <input className="ip-input" value={form.notification_email} onChange={e => setForm({ ...form, notification_email: e.target.value })} placeholder="Optional" />
          </div>
          <div className="sla-form-row">
            <label>Webhook URL</label>
            <input className="ip-input" value={form.webhook_url} onChange={e => setForm({ ...form, webhook_url: e.target.value })} placeholder="Optional" />
          </div>
          <button className="ip-btn-primary" onClick={handleCreate} disabled={submitting} style={{ marginTop: 12 }}>
            {submitting ? "Creating..." : "Create Policy"}
          </button>
        </div>
      )}

      {error && <p className="sla-error">{error}</p>}

      {policies.length === 0 ? (
        <p className="ip-empty-state">No policies yet — create one above.</p>
      ) : (
        <table className="ip-table" style={{ marginTop: 16 }}>
          <thead>
            <tr>
              <th>Name</th>
              <th>Metric</th>
              <th>Threshold</th>
              <th>Window</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td><span className="ip-tag">{p.metric_type}</span></td>
                <td><span className="ip-mono">{p.threshold_value}</span></td>
                <td>{p.window_minutes}m</td>
                <td>
                  <span className={`ip-badge ip-badge--${p.is_active ? "passed" : "masked"}`}>
                    <span className="ip-badge-dot" />{p.is_active ? "Active" : "Paused"}
                  </span>
                </td>
                <td style={{ display: "flex", gap: 8 }}>
                  <button className="ip-btn-ghost" onClick={() => handleToggle(p)} style={{ fontSize: 12 }}>
                    {p.is_active ? "Pause" : "Activate"}
                  </button>
                  <button className="ip-btn-danger" onClick={() => handleDelete(p.id)} style={{ fontSize: 12 }}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Breach History
// ---------------------------------------------------------------------------

function BreachHistory() {
  const [breaches, setBreaches] = useState<any[]>([]);
  const [filter, setFilter] = useState<"" | "open" | "resolved">("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    fetchSLABreaches(filter || undefined)
      .then((d) => setBreaches(d.breaches || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [filter]);

  if (loading) return <div className="ip-sheet"><p className="ip-empty-state">Loading...</p></div>;

  return (
    <div className="ip-sheet">
      <div style={{ display: "flex", gap: 12, marginBottom: 16, alignItems: "center" }}>
        <div className="gdpr-section-title" style={{ flex: 1 }}>Breach History</div>
        <select className="ip-input" style={{ width: 140 }} value={filter} onChange={e => setFilter(e.target.value as any)}>
          <option value="">All</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
      </div>

      {error && <p className="sla-error">{error}</p>}

      {breaches.length === 0 ? (
        <p className="ip-empty-state">No breaches recorded — your agents are within SLA.</p>
      ) : (
        <table className="ip-table">
          <thead>
            <tr>
              <th>Policy</th>
              <th>Metric Value</th>
              <th>Threshold</th>
              <th>Breached At</th>
              <th>Status</th>
              <th>Resolved At</th>
            </tr>
          </thead>
          <tbody>
            {breaches.map((b) => (
              <tr key={b.id}>
                <td><span className="ip-mono" style={{ fontSize: 12 }}>{b.policy_id.slice(0, 8)}…</span></td>
                <td><span className="ip-mono" style={{ color: "var(--status-blocked-dot)" }}>{Number(b.metric_value).toFixed(3)}</span></td>
                <td>{b.threshold_value}</td>
                <td><span className="ip-mono" style={{ fontSize: 12 }}>{new Date(b.breached_at).toLocaleString()}</span></td>
                <td>
                  {b.resolved_at ? (
                    <span className="ip-badge ip-badge--passed"><span className="ip-badge-dot" />Resolved</span>
                  ) : (
                    <span className="ip-badge ip-badge--blocked"><span className="ip-badge-dot" />Ongoing</span>
                  )}
                </td>
                <td>
                  {b.resolved_at
                    ? <span className="ip-mono" style={{ fontSize: 12 }}>{new Date(b.resolved_at).toLocaleString()}</span>
                    : <span style={{ color: "var(--text-tertiary)" }}>—</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
