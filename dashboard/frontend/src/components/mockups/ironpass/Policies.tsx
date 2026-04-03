import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Policies.css";

interface Policy {
  id: string;
  name: string;
  dataTypes: string[];
  trigger: "Request" | "Response" | "Both";
  action: "Mask" | "Tokenize" | "Block" | "Allow+Log";
  source: string;
  scope: string;
  enabled: boolean;
}

const policies: Policy[] = [
  { id: "p1", name: "Credit Card Detection", dataTypes: ["CREDIT_CARD", "CVV"], trigger: "Both", action: "Tokenize", source: "PCI-DSS", scope: "All agents", enabled: true },
  { id: "p2", name: "SSN Masking", dataTypes: ["SSN"], trigger: "Both", action: "Mask", source: "HIPAA", scope: "All agents", enabled: true },
  { id: "p3", name: "PHI Detection", dataTypes: ["DATE_OF_BIRTH", "NAME"], trigger: "Both", action: "Mask", source: "HIPAA", scope: "All agents", enabled: true },
  { id: "p4", name: "IBAN Block", dataTypes: ["IBAN"], trigger: "Request", action: "Block", source: "PCI-DSS", scope: "3 agents", enabled: true },
  { id: "p5", name: "Phone Number Log", dataTypes: ["PHONE"], trigger: "Both", action: "Allow+Log", source: "Custom", scope: "All agents", enabled: false },
  { id: "p6", name: "Employee ID Detection", dataTypes: ["EMPLOYEE_ID"], trigger: "Request", action: "Mask", source: "Custom", scope: "2 agents", enabled: true },
  { id: "p7", name: "GDPR Personal Data", dataTypes: ["NAME", "PHONE", "DATE_OF_BIRTH"], trigger: "Both", action: "Mask", source: "GDPR", scope: "All agents", enabled: true },
  { id: "p8", name: "Card Expiry Block", dataTypes: ["CARD_EXPIRY"], trigger: "Request", action: "Block", source: "PCI-DSS", scope: "All agents", enabled: true },
];

const actionColor: Record<Policy["action"], string> = {
  Mask: "var(--status-masked-text)",
  Tokenize: "#1D4ED8",
  Block: "var(--status-blocked-text)",
  "Allow+Log": "var(--status-passed-text)",
};

type DrawerSection = "detect" | "where" | "action" | "scope";

function PolicyDrawer({ onClose }: { onClose: () => void }) {
  const [activeSection, setActiveSection] = useState<DrawerSection>("detect");
  const [detectionType, setDetectionType] = useState<"builtin" | "custom">("builtin");
  const [selectedAction, setSelectedAction] = useState<Policy["action"]>("Tokenize");
  const [testText, setTestText] = useState("");
  const [calibrated, setCalibrated] = useState(false);

  const actions: { value: Policy["action"]; label: string; desc: string }[] = [
    { value: "Mask", label: "Mask", desc: "Replace with [MASKED·TYPE]. Not reversible." },
    { value: "Tokenize", label: "Tokenize", desc: "Replace with vault token. Reversible. Stored securely." },
    { value: "Block", label: "Block", desc: "Reject the entire request. Returns 400 to agent." },
    { value: "Allow+Log", label: "Allow + Log", desc: "Pass through. Record detection. No modification." },
  ];

  return (
    <>
      <div className="ip-drawer-backdrop" onClick={onClose} />
      <div className="ip-drawer" style={{ width: 560 }}>
        <div className="ip-drawer-header">
          <button className="ip-drawer-close" onClick={onClose}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9 3L5 7L9 11" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>
            Close
          </button>
          <div style={{ fontSize: 14, fontWeight: 500 }}>New Policy</div>
        </div>

        {/* Section 1 — Detection */}
        <div className="ip-drawer-section">
          <div className="ip-section-heading">What to Detect</div>
          <div className="ip-policy-radio-row">
            <label className="ip-policy-radio-opt">
              <input type="radio" name="dtype" checked={detectionType === "builtin"} onChange={() => setDetectionType("builtin")} />
              Built-in data type
            </label>
            <label className="ip-policy-radio-opt">
              <input type="radio" name="dtype" checked={detectionType === "custom"} onChange={() => setDetectionType("custom")} />
              Custom pattern
            </label>
          </div>
          {detectionType === "builtin" ? (
            <select className="ip-input" style={{ marginTop: 10 }}>
              <option>Credit Card Number</option>
              <option>Social Security Number</option>
              <option>Date of Birth</option>
              <option>Full Name</option>
              <option>Phone Number</option>
              <option>IBAN</option>
              <option>Passport Number</option>
            </select>
          ) : (
            <div className="ip-custom-pattern">
              <input className="ip-input ip-mono" placeholder="^[0-9]{3}-[0-9]{2}-[0-9]{4}$" style={{ marginTop: 10, fontFamily: "var(--font-mono)", fontSize: 13 }} />
              <div className="ip-section-heading" style={{ marginTop: 16, marginBottom: 8 }}>Test Pattern</div>
              <textarea
                className="ip-input"
                rows={3}
                placeholder="Paste sample text to test..."
                value={testText}
                onChange={e => setTestText(e.target.value)}
                style={{ resize: "none", fontFamily: "var(--font-sans)" }}
              />
              <div className="ip-policy-threshold">
                <label className="ip-section-heading" style={{ marginBottom: 0 }}>Confidence threshold</label>
                <div className="ip-threshold-row">
                  <input type="range" min={50} max={100} defaultValue={85} className="ip-slider" />
                  <span className="ip-mono" style={{ fontSize: 12 }}>0.85</span>
                </div>
              </div>
              {testText && (
                <button className="ip-run-calibration" onClick={() => setCalibrated(true)}>
                  Run against calibration set →
                </button>
              )}
              {calibrated && (
                <div className="ip-calibration-result">
                  <div className="ip-cal-row ip-cal-pass">✓ 47/50 known PII samples detected</div>
                  <div className="ip-cal-row ip-cal-fail">✗ 3 missed · 2 false positives</div>
                  <div className="ip-cal-row" style={{ color: "var(--text-secondary)" }}>
                    Precision: 0.96 · Recall: 0.94
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Section 2 — Where */}
        <div className="ip-drawer-section">
          <div className="ip-section-heading">Apply To</div>
          <div className="ip-toggle-group-row">
            {["Request messages", "Response messages", "Both"].map(v => (
              <button key={v} className={`ip-tg-btn${v === "Both" ? " ip-tg-btn--active" : ""}`}>{v}</button>
            ))}
          </div>
          <div className="ip-section-heading" style={{ marginTop: 16, marginBottom: 8 }}>Message Scope</div>
          <div className="ip-toggle-group-row" style={{ flexWrap: "wrap" }}>
            {["All content", "System prompt only", "User messages only", "Assistant messages only"].map(v => (
              <button key={v} className={`ip-tg-btn${v === "All content" ? " ip-tg-btn--active" : ""}`}>{v}</button>
            ))}
          </div>
        </div>

        {/* Section 3 — Action */}
        <div className="ip-drawer-section">
          <div className="ip-section-heading">When Detected, Do This</div>
          <div className="ip-action-options">
            {actions.map(a => (
              <label
                key={a.value}
                className={`ip-action-option${selectedAction === a.value ? " ip-action-option--selected" : ""}`}
                onClick={() => setSelectedAction(a.value)}
              >
                <input type="radio" name="action" checked={selectedAction === a.value} onChange={() => setSelectedAction(a.value)} />
                <div>
                  <div className="ip-action-label">{a.label}</div>
                  <div className="ip-action-desc">{a.desc}</div>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Section 4 — Scope */}
        <div className="ip-drawer-section">
          <div className="ip-section-heading">Agent Scope</div>
          <div className="ip-radio-group">
            <label className="ip-radio">
              <input type="radio" name="scope" defaultChecked /> All agents
            </label>
            <label className="ip-radio">
              <input type="radio" name="scope" /> Specific agents
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="ip-drawer-section">
          <div className="ip-live-preview-header">
            <span className="ip-section-heading" style={{ marginBottom: 0 }}>Live Preview</span>
            <span style={{ fontSize: 12, color: "var(--text-tertiary)" }}>▾</span>
          </div>
          <textarea
            className="ip-input"
            rows={2}
            placeholder="Paste text here to see exactly what this policy does..."
            style={{ resize: "none", marginTop: 8, fontFamily: "var(--font-sans)" }}
          />
        </div>

        <div style={{ padding: "16px 20px", display: "flex", justifyContent: "flex-end", gap: 8, borderTop: "1px solid var(--border-default)" }}>
          <button className="ip-btn-ghost" onClick={onClose}>Cancel</button>
          <button className="ip-btn-primary">Save policy</button>
        </div>
      </div>
    </>
  );
}

export function Policies() {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [enabledMap, setEnabledMap] = useState<Record<string, boolean>>(
    Object.fromEntries(policies.map(p => [p.id, p.enabled]))
  );
  const [activePage, setActivePage] = useState<any>("policies");

  const toggle = (id: string) => setEnabledMap(prev => ({ ...prev, [id]: !prev[id] }));

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Policies</div>
          <div className="ip-page-subtitle">Individual detection and action rules</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-primary" onClick={() => setDrawerOpen(true)}>New policy</button>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
          <table className="ip-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Data Type(s)</th>
                <th>Trigger</th>
                <th>Action</th>
                <th>Source</th>
                <th>Scope</th>
                <th>Status</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {policies.map((p) => (
                <tr key={p.id}>
                  <td style={{ fontWeight: 500, fontSize: 13 }}>{p.name}</td>
                  <td>
                    <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                      {p.dataTypes.slice(0, 2).map(t => <span key={t} className="ip-tag">{t}</span>)}
                      {p.dataTypes.length > 2 && <span className="ip-tag">+{p.dataTypes.length - 2}</span>}
                    </div>
                  </td>
                  <td style={{ color: "var(--text-secondary)", fontSize: 13 }}>{p.trigger}</td>
                  <td>
                    <span style={{ fontSize: 13, fontWeight: 500, color: actionColor[p.action] }}>
                      {p.action}
                    </span>
                  </td>
                  <td>
                    {p.source === "Custom"
                      ? <span style={{ fontSize: 12, color: "var(--text-tertiary)", fontStyle: "italic" }}>Custom</span>
                      : <span className="ip-tag" style={{ fontFamily: "var(--font-sans)" }}>{p.source}</span>
                    }
                  </td>
                  <td style={{ color: "var(--text-secondary)", fontSize: 13 }}>{p.scope}</td>
                  <td>
                    <label className="ip-toggle">
                      <input type="checkbox" checked={enabledMap[p.id]} onChange={() => toggle(p.id)} />
                      <span className="ip-toggle-track" />
                      <span className="ip-toggle-thumb" />
                    </label>
                  </td>
                  <td>
                    <button className="ip-icon-btn">⋯</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {drawerOpen && <PolicyDrawer onClose={() => setDrawerOpen(false)} />}
    </AppShell>
  );
}
