import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./ApiKeys.css";

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scope: "Full access" | "Read-only" | "Custom";
  created: string;
  expires: string | null;
  lastUsed: string;
  status: "active" | "revoked";
  expiringSoon?: boolean;
  expired?: boolean;
}

const keys: ApiKey[] = [
  {
    id: "k1", name: "Production", prefix: "dbnc_live_a3f2d1c8",
    scope: "Full access", created: "Jan 12, 2026", expires: null,
    lastUsed: "2 min ago", status: "active",
  },
  {
    id: "k2", name: "Staging", prefix: "dbnc_live_b8c1f4e9",
    scope: "Read-only", created: "Mar 01, 2026", expires: "Apr 30, 2026",
    lastUsed: "1 hr ago", status: "active", expiringSoon: true,
  },
  {
    id: "k3", name: "Analytics service", prefix: "dbnc_live_c7d2e9f1",
    scope: "Read-only", created: "Mar 14, 2026", expires: null,
    lastUsed: "Yesterday", status: "active",
  },
  {
    id: "k4", name: "Old production key", prefix: "dbnc_live_xxxx0000",
    scope: "Full access", created: "Dec 01, 2025", expires: "Feb 01, 2026",
    lastUsed: "—", status: "revoked", expired: true,
  },
];

const scopeDesc: Record<string, string> = {
  "Full access": "Read + write all proxy data",
  "Read-only": "View logs and reports only",
  "Custom": "Scoped permissions",
};

type ModalStep = "config" | "reveal" | "closed";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <button className="ip-copy-btn" onClick={handleCopy} title="Copy to clipboard">
      {copied ? "✓" : "⎘"}
    </button>
  );
}

export function ApiKeys() {
  const [modalStep, setModalStep] = useState<ModalStep>("closed");
  const [btnDisabled, setBtnDisabled] = useState(false);
  const [keyCopied, setKeyCopied] = useState(false);
  const [activePage, setActivePage] = useState<any>("api-keys");

  const openModal = () => { setModalStep("config"); setKeyCopied(false); };

  const handleGenerate = () => {
    setModalStep("reveal");
    setBtnDisabled(true);
    setTimeout(() => setBtnDisabled(false), 2000);
  };

  const handleCopied = () => {
    setKeyCopied(true);
    setTimeout(() => { setModalStep("closed"); setKeyCopied(false); }, 300);
  };

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">API Keys</div>
          <div className="ip-page-subtitle">Authentication credentials for Covenant AI proxy access</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-primary" onClick={openModal}>Issue new key</button>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
          <table className="ip-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Key prefix</th>
                <th>Scope</th>
                <th>Last used</th>
                <th>Created</th>
                <th>Expires</th>
                <th>Status</th>
                <th style={{ width: 48 }}></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id} style={{ opacity: key.status === "revoked" ? 0.55 : 1 }}>
                  <td style={{ fontWeight: 500 }}>{key.name}</td>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                      <span className="ip-mono" style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                        {key.prefix}…
                      </span>
                      {key.status === "active" && <CopyButton text={key.prefix} />}
                    </div>
                  </td>
                  <td>
                    <div>
                      <div style={{ fontSize: 13 }}>{key.scope}</div>
                      <div style={{ fontSize: 11, color: "var(--text-tertiary)" }}>{scopeDesc[key.scope]}</div>
                    </div>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{key.lastUsed}</td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{key.created}</td>
                  <td>
                    <span style={{
                      fontSize: 13,
                      color: key.expired
                        ? "var(--status-blocked-text)"
                        : key.expiringSoon
                        ? "var(--status-masked-text)"
                        : "var(--text-secondary)",
                      fontWeight: key.expiringSoon ? 500 : 400,
                    }}>
                      {key.expires ?? "Never"}
                      {key.expiringSoon && <div style={{ fontSize: 11, color: "var(--status-masked-text)" }}>Expires soon</div>}
                    </span>
                  </td>
                  <td>
                    <span className={`ip-badge ip-badge--${key.status === "active" ? "passed" : "error"}`}>
                      <span className="ip-badge-dot" />
                      {key.status === "active" ? "Active" : "Revoked"}
                    </span>
                  </td>
                  <td>
                    {key.status === "active" && <button className="ip-icon-btn">⋯</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Usage snippet */}
        <div className="ip-sheet ip-usage-snippet">
          <div className="ip-section-heading" style={{ marginBottom: 10 }}>Usage</div>
          <pre className="ip-usage-code">{`curl https://api.covenant.io/v1/chat/completions \\
  -H "Authorization: Bearer dbnc_live_a3f2d1c8..." \\
  -H "Content-Type: application/json" \\
  -d '{"model":"gpt-4o","messages":[...]}'`}</pre>
          <div style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 8 }}>
            Drop-in replacement for the OpenAI API — change only the base URL and add your Covenant AI key.
          </div>
        </div>
      </div>

      {/* Issue key modal */}
      {modalStep !== "closed" && (
        <>
          <div className="ip-modal-backdrop" onClick={() => setModalStep("closed")} />
          <div className="ip-modal">
            {modalStep === "config" && (
              <>
                <div className="ip-modal-header">
                  <div style={{ fontSize: 15, fontWeight: 500 }}>Issue new API key</div>
                </div>
                <div className="ip-modal-body">
                  <div className="ip-modal-field">
                    <label className="ip-modal-label">Key name</label>
                    <input className="ip-input" defaultValue="My agent" placeholder="e.g. Production agent" />
                    <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>For your reference only. Not transmitted with requests.</div>
                  </div>
                  <div className="ip-modal-field">
                    <label className="ip-modal-label">Scope</label>
                    <div className="ip-scope-options">
                      {[
                        { value: "Full access", desc: "Read and write all proxy data, manage settings" },
                        { value: "Read-only", desc: "View logs and reports only — no config changes" },
                      ].map(s => (
                        <label key={s.value} className="ip-scope-option">
                          <input type="radio" name="scope" defaultChecked={s.value === "Read-only"} />
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 500 }}>{s.value}</div>
                            <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>{s.desc}</div>
                          </div>
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="ip-modal-field">
                    <label className="ip-modal-label">Expiry</label>
                    <div className="ip-radio-group" style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
                      {["Never", "30 days", "90 days", "1 year"].map((v) => (
                        <label key={v} className="ip-radio" style={{ border: "1px solid var(--border-default)", borderRadius: 6, padding: "5px 10px" }}>
                          <input type="radio" name="expires" defaultChecked={v === "90 days"} /> {v}
                        </label>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="ip-modal-footer">
                  <button className="ip-btn-ghost" onClick={() => setModalStep("closed")}>Cancel</button>
                  <button className="ip-btn-primary" onClick={handleGenerate}>Generate key →</button>
                </div>
              </>
            )}

            {modalStep === "reveal" && (
              <>
                <div className="ip-modal-header">
                  <div style={{ fontSize: 15, fontWeight: 500 }}>API key created</div>
                </div>
                <div className="ip-modal-body">
                  <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12 }}>
                    Your new key is ready. Copy it now — it won't be shown again.
                  </div>
                  <div className="ip-key-reveal-box">
                    <span className="ip-mono" style={{ fontSize: 12 }}>dbnc_live_a3f2d1c8b9e4f7a2d1...</span>
                    <button
                      className="ip-btn-ghost"
                      style={{ padding: "4px 10px", fontSize: 12 }}
                      onClick={() => setKeyCopied(true)}
                    >
                      {keyCopied ? "Copied ✓" : "Copy ⎘"}
                    </button>
                  </div>
                  <div className="ip-key-warning">
                    <span style={{ color: "var(--status-masked-text)", fontWeight: 500 }}>⚠</span>
                    <span style={{ color: "var(--status-masked-text)", fontSize: 13 }}>
                      Store this key in a secrets manager (e.g. AWS Secrets Manager, HashiCorp Vault). Never commit it to source control.
                    </span>
                  </div>
                </div>
                <div className="ip-modal-footer">
                  <button
                    className={`ip-btn-primary${!keyCopied ? " ip-btn-disabled" : ""}`}
                    disabled={!keyCopied && btnDisabled}
                    style={{ opacity: !keyCopied && btnDisabled ? 0.5 : 1 }}
                    onClick={keyCopied ? handleCopied : undefined}
                  >
                    {!keyCopied ? "Copy your key first..." : "Done, I've saved it →"}
                  </button>
                </div>
              </>
            )}
          </div>
        </>
      )}
    </AppShell>
  );
}
