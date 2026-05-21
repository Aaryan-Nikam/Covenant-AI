import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Settings.css";

type SettingsTab = "general" | "proxy" | "notifications" | "danger";

export function Settings() {
  const [tab, setTab] = useState<SettingsTab>("general");
  const [activePage, setActivePage] = useState<any>("settings");

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Settings</div>
          <div className="ip-page-subtitle">Organization and proxy configuration</div>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-settings-layout">
          {/* Settings nav */}
          <div className="ip-settings-nav">
            {([
              ["general", "General"],
              ["proxy", "Proxy Config"],
              ["notifications", "Notifications"],
              ["danger", "Danger Zone"],
            ] as [SettingsTab, string][]).map(([id, label]) => (
              <button
                key={id}
                className={`ip-settings-nav-item${tab === id ? " ip-settings-nav-item--active" : ""}${id === "danger" ? " ip-settings-nav-item--danger" : ""}`}
                onClick={() => setTab(id)}
              >
                {label}
              </button>
            ))}
          </div>

          {/* Settings content */}
          <div className="ip-settings-body">
            {tab === "general" && <GeneralSettings />}
            {tab === "proxy" && <ProxySettings />}
            {tab === "notifications" && <NotificationSettings />}
            {tab === "danger" && <DangerZone />}
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function SettingsSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="ip-sheet ip-settings-section">
      <div className="ip-settings-section-title">{title}</div>
      {children}
    </div>
  );
}

function SettingsRow({ label, desc, children }: { label: string; desc?: string; children: React.ReactNode }) {
  return (
    <div className="ip-settings-row">
      <div className="ip-settings-row-left">
        <div className="ip-settings-row-label">{label}</div>
        {desc && <div className="ip-settings-row-desc">{desc}</div>}
      </div>
      <div className="ip-settings-row-right">{children}</div>
    </div>
  );
}

function GeneralSettings() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <SettingsSection title="Organization">
        <SettingsRow label="Organization name" desc="Displayed in reports and audit logs">
          <input className="ip-input" defaultValue="Acme Corp" style={{ width: 280 }} />
        </SettingsRow>
        <SettingsRow label="Default tenant ID" desc="Used when no tenant is specified in requests">
          <input className="ip-input ip-mono" defaultValue="tenant_a3f2d1c8" style={{ width: 280, fontFamily: "var(--font-mono)", fontSize: 12 }} />
        </SettingsRow>
        <SettingsRow label="Time zone" desc="Used for timestamps in reports and the audit log">
          <select className="ip-input" style={{ width: 280 }}>
            <option>UTC (Coordinated Universal Time)</option>
            <option>US/Eastern</option>
            <option>US/Pacific</option>
          </select>
        </SettingsRow>
        <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 12, borderTop: "1px solid var(--border-default)" }}>
          <button className="ip-btn-primary">Save changes</button>
        </div>
      </SettingsSection>

      <SettingsSection title="Audit Log Retention">
        <SettingsRow label="Log retention period" desc="Logs older than this period are automatically deleted">
          <select className="ip-input" style={{ width: 280 }}>
            <option>90 days</option>
            <option>180 days</option>
            <option>1 year</option>
            <option>Indefinite</option>
          </select>
        </SettingsRow>
        <SettingsRow label="Export before deletion" desc="Automatically export logs to S3 before deletion">
          <label className="ip-toggle">
            <input type="checkbox" />
            <span className="ip-toggle-track" />
            <span className="ip-toggle-thumb" />
          </label>
        </SettingsRow>
      </SettingsSection>
    </div>
  );
}

function ProxySettings() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <SettingsSection title="Proxy Endpoint">
        <SettingsRow label="Proxy URL" desc="Point your agents at this URL instead of the LLM provider directly">
          <div style={{ display: "flex", gap: 8, width: 320 }}>
            <input className="ip-input ip-mono" value="https://api.covenant.io/v1" readOnly style={{ fontFamily: "var(--font-mono)", fontSize: 12, flex: 1 }} />
            <button className="ip-btn-ghost" style={{ padding: "7px 10px", flexShrink: 0 }}>Copy</button>
          </div>
        </SettingsRow>
        <SettingsRow label="Target model provider" desc="The LLM provider requests are forwarded to after sanitization">
          <select className="ip-input" style={{ width: 280 }}>
            <option>OpenAI</option>
            <option>Anthropic</option>
            <option>Azure OpenAI</option>
            <option>Custom endpoint</option>
          </select>
        </SettingsRow>
      </SettingsSection>

      <SettingsSection title="Performance">
        <SettingsRow label="Request timeout" desc="Maximum time to wait for a response before returning an error">
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input className="ip-input" type="number" defaultValue={30} style={{ width: 80 }} />
            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>seconds</span>
          </div>
        </SettingsRow>
        <SettingsRow label="NER scan enabled" desc="Enable Named Entity Recognition for more accurate PII detection">
          <label className="ip-toggle">
            <input type="checkbox" defaultChecked />
            <span className="ip-toggle-track" />
            <span className="ip-toggle-thumb" />
          </label>
        </SettingsRow>
        <SettingsRow label="Cache identical requests" desc="Return cached sanitized responses for identical payloads within 60s">
          <label className="ip-toggle">
            <input type="checkbox" />
            <span className="ip-toggle-track" />
            <span className="ip-toggle-thumb" />
          </label>
        </SettingsRow>
      </SettingsSection>
    </div>
  );
}

function NotificationSettings() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <SettingsSection title="Alerts">
        <SettingsRow label="Violation alerts" desc="Get notified when a request is blocked by a policy">
          <label className="ip-toggle">
            <input type="checkbox" defaultChecked />
            <span className="ip-toggle-track" />
            <span className="ip-toggle-thumb" />
          </label>
        </SettingsRow>
        <SettingsRow label="Error rate threshold" desc="Alert when error rate exceeds this percentage in any 5-minute window">
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input className="ip-input" type="number" defaultValue={1} style={{ width: 80 }} />
            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>%</span>
          </div>
        </SettingsRow>
        <SettingsRow label="Latency threshold" desc="Alert when p95 latency exceeds this value">
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input className="ip-input" type="number" defaultValue={500} style={{ width: 80 }} />
            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>ms</span>
          </div>
        </SettingsRow>
      </SettingsSection>

      <SettingsSection title="Delivery">
        <SettingsRow label="Email notifications" desc="Send alerts to team members by email">
          <label className="ip-toggle">
            <input type="checkbox" defaultChecked />
            <span className="ip-toggle-track" />
            <span className="ip-toggle-thumb" />
          </label>
        </SettingsRow>
        <SettingsRow label="Slack webhook" desc="Post alerts to a Slack channel">
          <input className="ip-input" placeholder="https://hooks.slack.com/..." style={{ width: 280 }} />
        </SettingsRow>
        <SettingsRow label="Review digest" desc="Send a weekly summary of violations and policy activity">
          <label className="ip-toggle">
            <input type="checkbox" />
            <span className="ip-toggle-track" />
            <span className="ip-toggle-thumb" />
          </label>
        </SettingsRow>
        <div style={{ display: "flex", justifyContent: "flex-end", paddingTop: 12, borderTop: "1px solid var(--border-default)" }}>
          <button className="ip-btn-primary">Save changes</button>
        </div>
      </SettingsSection>
    </div>
  );
}

function DangerZone() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="ip-sheet ip-danger-card">
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>Flush audit log</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Permanently delete all audit log entries. This action cannot be undone. Export your log first.</div>
        </div>
        <button className="ip-btn-destructive" style={{ flexShrink: 0 }}>Flush log</button>
      </div>
      <div className="ip-sheet ip-danger-card">
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, marginBottom: 4 }}>Revoke all API keys</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Immediately invalidate all active API keys. All agents will lose access instantly.</div>
        </div>
        <button className="ip-btn-destructive" style={{ flexShrink: 0 }}>Revoke all keys</button>
      </div>
      <div className="ip-sheet ip-danger-card" style={{ borderColor: "#FECACA" }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--status-blocked-text)", marginBottom: 4 }}>Delete organization</div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Permanently delete this organization and all its data — logs, policies, keys, and agents. This is irreversible.</div>
        </div>
        <button className="ip-btn-destructive" style={{ flexShrink: 0 }}>Delete org</button>
      </div>
    </div>
  );
}
