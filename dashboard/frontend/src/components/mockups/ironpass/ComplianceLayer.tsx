import React, { useEffect, useMemo, useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./ComplianceLayer.css";
import {
  fetchProductMap,
  fetchRulesets,
  runComplianceScan,
  updateActiveRulesets,
  type ProductMapResponse,
  type ScanResponsePayload,
} from "../../../lib/api";

const SAMPLE_SCAN_TEXT =
  "Customer card 4111111111111111 and SSN 123-45-6789 appear in this request.";

const FALLBACK_PRODUCT_MAP: ProductMapResponse = {
  generated_at: "2026-05-06T00:00:00Z",
  core_compliance_layer: {
    name: "Core Compliance Layer",
    description:
      "Traffic interception, policy enforcement, secure tokenization, audit evidence, and governance controls.",
    kpis: {
      tenant_id: "demo_tenant",
      total_requests: 48291,
      total_blocked: 214,
      requests_24h: 2187,
      active_vault_tokens: 3847,
      avg_latency_ms: 138.0,
      block_rate: 0.4,
      active_rulesets_count: 3,
    },
    rulesets: {
      active_count: 3,
      active_rulesets: ["pci_dss", "hipaa", "gdpr"],
      available_count: 4,
      available_rulesets: ["gdpr", "hipaa", "pci_dss", "soc2"],
    },
    features: [
      {
        id: "proxy_interception",
        name: "Provider Proxy Interception",
        status: "live",
        routes: [
          "/openai/v1/chat/completions",
          "/anthropic/v1/messages",
          "/google/v1/models/{model}:generateContent",
          "/proxy/scan",
        ],
      },
      {
        id: "policy_enforcement",
        name: "Ruleset Detection + Actions",
        status: "live",
        routes: ["/proxy/rulesets", "/proxy/rulesets/{ruleset_id}", "/proxy/rulesets/active"],
      },
      {
        id: "immutable_audit",
        name: "Immutable Audit + Chain Verification",
        status: "live",
        routes: ["/dashboard/audit", "/dashboard/audit/verify", "/v1/logs"],
      },
      {
        id: "vault_security",
        name: "Token Vault and De-tokenization",
        status: "live",
        routes: ["/dashboard/overview"],
      },
      {
        id: "tenant_governance",
        name: "Tenant Governance + Access Control",
        status: "live",
        routes: ["/v1/admin/tenants", "/v1/admin/tenants/{tenant_id}"],
      },
    ],
  },
  operations_function_suite: {
    name: "Operations Functions",
    description: "High-ticket business workflows.",
    implemented_count: 4,
    planned_count: 5,
    functions: [],
  },
  management_capabilities: [],
};

function formatRuleset(rule: string) {
  return rule.replaceAll("_", "-").toUpperCase();
}

export function ComplianceLayer() {
  const [activePage, setActivePage] = useState<any>("compliance-layer");
  const [data, setData] = useState<ProductMapResponse | null>(null);
  const [availableRulesets, setAvailableRulesets] = useState<string[]>([]);
  const [selectedRulesets, setSelectedRulesets] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [apiLive, setApiLive] = useState(false);
  const [savingRulesets, setSavingRulesets] = useState(false);
  const [rulesetStatus, setRulesetStatus] = useState<string>("");

  const [scanInput, setScanInput] = useState("");
  const [scanTargetUrl, setScanTargetUrl] = useState("https://api.openai.com/v1/chat/completions");
  const [scanRunning, setScanRunning] = useState(false);
  const [scanResult, setScanResult] = useState<ScanResponsePayload | null>(null);
  const [scanError, setScanError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [mapResp, rulesetsResp] = await Promise.all([
          fetchProductMap(),
          fetchRulesets(),
        ]);
        if (cancelled) return;

        setData(mapResp);
        const available = rulesetsResp.rulesets.map((item) => item.id);
        const active = rulesetsResp.rulesets
          .filter((item) => item.is_active)
          .map((item) => item.id);
        setAvailableRulesets(available);
        setSelectedRulesets(active);
        setApiLive(true);
      } catch {
        // Keep fallback data when backend is unavailable
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  const map = data ?? FALLBACK_PRODUCT_MAP;
  const kpis = map.core_compliance_layer.kpis;
  const features = map.core_compliance_layer.features ?? [];
  const resolvedAvailableRulesets =
    availableRulesets.length > 0
      ? availableRulesets
      : map.core_compliance_layer.rulesets.available_rulesets;
  const isFallbackMode = !apiLive && !loading;

  const sortedSelectedRulesets = useMemo(
    () => [...selectedRulesets].sort(),
    [selectedRulesets]
  );

  function toggleRuleset(rule: string) {
    setRulesetStatus("");
    setSelectedRulesets((current) =>
      current.includes(rule)
        ? current.filter((item) => item !== rule)
        : [...current, rule]
    );
  }

  async function handleSaveRulesets() {
    setSavingRulesets(true);
    setRulesetStatus("");
    try {
      const updated = await updateActiveRulesets(sortedSelectedRulesets);
      setSelectedRulesets(updated.active_rulesets);
      setRulesetStatus("Active rulesets updated.");

      const refreshed = await fetchProductMap();
      setData(refreshed);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Failed to update rulesets";
      setRulesetStatus(message);
    } finally {
      setSavingRulesets(false);
    }
  }

  async function handleRunScan() {
    if (!scanInput.trim()) return;
    setScanRunning(true);
    setScanError("");
    setScanResult(null);

    try {
      const result = await runComplianceScan({
        content: scanInput,
        rulesets: sortedSelectedRulesets,
        target_url: scanTargetUrl || undefined,
        metadata: { source: "core_layer_playground" },
      });
      setScanResult(result);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Scan failed";
      setScanError(message);
    } finally {
      setScanRunning(false);
    }
  }

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Core Compliance Layer</div>
          <div className="ip-page-subtitle">
            Foundational interception, policy enforcement, audit, vault, and governance controls
            {apiLive && (
              <span style={{ marginLeft: 8, fontSize: 11, color: "var(--status-passed-dot)" }}>
                ● Live
              </span>
            )}
            {isFallbackMode && (
              <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-tertiary)" }}>
                ● Demo fallback
              </span>
            )}
          </div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost" onClick={() => (window.location.hash = "operations-functions")}>
            Open Function Suite →
          </button>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-kpi-row">
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Tenant Requests</div>
            <div className="ip-kpi-value">{kpis.total_requests.toLocaleString()}</div>
            <div className="ip-kpi-delta">requests processed via proxy</div>
          </div>
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Block Rate</div>
            <div className="ip-kpi-value">{kpis.block_rate}%</div>
            <div className="ip-kpi-delta">policy enforcement strictness</div>
          </div>
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Active Rulesets</div>
            <div className="ip-kpi-value">{selectedRulesets.length}</div>
            <div className="ip-kpi-delta">tenant-level activated controls</div>
          </div>
          <div className="ip-sheet ip-kpi-card">
            <div className="ip-kpi-label">Vault Tokens</div>
            <div className="ip-kpi-value">{kpis.active_vault_tokens.toLocaleString()}</div>
            <div className="ip-kpi-delta">active protected references</div>
          </div>
        </div>

        <div className="ip-layer-grid">
          <div className="ip-sheet ip-layer-panel">
            <div className="ip-section-heading">Layer Features</div>
            <div className="ip-layer-features-grid">
              {features.map((feature) => (
                <div key={feature.id} className="ip-layer-feature-card">
                  <div className="ip-layer-feature-head">
                    <div style={{ fontWeight: 600 }}>{feature.name}</div>
                    <span className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>
                      {feature.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="ip-layer-route-list">
                    {feature.routes.map((route) => (
                      <code key={route}>{route}</code>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="ip-sheet ip-layer-panel">
            <div className="ip-section-heading">Ruleset Manager</div>
            <div className="ip-layer-ruleset-block">
              <div className="ip-layer-subtitle">Select Active Rulesets</div>
              <div className="ip-layer-ruleset-checks">
                {resolvedAvailableRulesets.map((rule) => {
                  const selected = selectedRulesets.includes(rule);
                  return (
                    <label key={rule} className="ip-layer-rule-check">
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => toggleRuleset(rule)}
                      />
                      <span>{formatRuleset(rule)}</span>
                    </label>
                  );
                })}
              </div>
              <div style={{ marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
                <button
                  className="ip-btn-primary"
                  onClick={handleSaveRulesets}
                  disabled={savingRulesets || isFallbackMode}
                  style={{ opacity: savingRulesets || isFallbackMode ? 0.6 : 1 }}
                >
                  {savingRulesets ? "Saving..." : "Save Rulesets"}
                </button>
                {rulesetStatus && (
                  <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{rulesetStatus}</span>
                )}
              </div>
            </div>

            <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
              <button className="ip-btn-ghost" onClick={() => (window.location.hash = "frameworks")}>
                Frameworks
              </button>
              <button className="ip-btn-ghost" onClick={() => (window.location.hash = "policies")}>
                Policies
              </button>
              <button className="ip-btn-ghost" onClick={() => (window.location.hash = "guardrails")}>
                Guardrails
              </button>
              <button className="ip-btn-ghost" onClick={() => (window.location.hash = "governance")}>
                Governance
              </button>
            </div>
          </div>
        </div>

        <div className="ip-sheet ip-layer-panel" style={{ marginTop: 16 }}>
          <div className="ip-section-heading">Compliance Playground</div>
          <div style={{ display: "grid", gap: 8 }}>
            <input
              className="ip-input"
              value={scanTargetUrl}
              onChange={(event) => setScanTargetUrl(event.target.value)}
              placeholder="Target URL for audit context"
            />
            <textarea
              className="ip-input"
              style={{ minHeight: 120, resize: "vertical" }}
              value={scanInput}
              onChange={(event) => setScanInput(event.target.value)}
              placeholder="Paste prompt/content to scan"
            />
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="ip-btn-ghost"
                onClick={() => setScanInput(SAMPLE_SCAN_TEXT)}
              >
                Load Sample
              </button>
              <button
                className="ip-btn-primary"
                onClick={handleRunScan}
                disabled={scanRunning || isFallbackMode}
                style={{ opacity: scanRunning || isFallbackMode ? 0.6 : 1 }}
              >
                {scanRunning ? "Scanning..." : "Run Scan"}
              </button>
            </div>
          </div>

          {scanError && (
            <div className="ip-layer-playground-error">{scanError}</div>
          )}

          {scanResult && (
            <div className="ip-layer-playground-results">
              <div className="ip-layer-playground-meta">
                <span className="ip-tag">{scanResult.was_blocked ? "BLOCKED" : "PASSED"}</span>
                <span className="ip-mono">latency {scanResult.latency_ms}ms</span>
                <span className="ip-mono">audit {scanResult.audit_id.slice(0, 10)}...</span>
              </div>

              <div className="ip-layer-playground-subhead">Sanitized Output</div>
              <pre>{scanResult.sanitized_content}</pre>

              <div className="ip-layer-playground-subhead">Violations</div>
              {scanResult.violations.length === 0 && (
                <div style={{ color: "var(--text-tertiary)" }}>No violations detected.</div>
              )}
              {scanResult.violations.map((violation, idx) => (
                <div key={`${violation.type}-${idx}`} className="ip-layer-violation-row">
                  <span className="ip-tag">{violation.type}</span>
                  <span>{violation.action}</span>
                  <span className="ip-mono">{violation.ruleset}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
