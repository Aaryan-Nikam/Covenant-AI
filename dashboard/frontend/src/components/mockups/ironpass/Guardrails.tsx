import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Guardrails.css";

interface Guardrail {
  id: string;
  name: string;
  description: string;
  checkType: "local" | "model";
  latency: string;
  action: "Block" | "Allow+Log";
  scope: string;
  enabled: boolean;
  section: "input" | "output";
  triggeredToday: number;
  lastTriggered: string | null;
}

const guardrails: Guardrail[] = [
  {
    id: "g1", name: "Prompt Injection Detection",
    description: "Detects attempts to override system prompts or inject malicious instructions via user-controlled input.",
    checkType: "local", latency: "~0ms", action: "Block", scope: "All agents",
    enabled: true, section: "input", triggeredToday: 14, lastTriggered: "2 min ago",
  },
  {
    id: "g2", name: "PII in System Prompt",
    description: "Detects sensitive personal data hardcoded in system prompts — a misconfiguration risk.",
    checkType: "local", latency: "~0ms", action: "Block", scope: "All agents",
    enabled: true, section: "input", triggeredToday: 3, lastTriggered: "1 hr ago",
  },
  {
    id: "g3", name: "Off-topic Request Filter",
    description: "Identifies requests that fall outside the agent's configured topic scope using a lightweight classifier.",
    checkType: "model", latency: "~150ms", action: "Allow+Log", scope: "3 agents",
    enabled: false, section: "input", triggeredToday: 0, lastTriggered: null,
  },
  {
    id: "g4", name: "Harmful Content Detection",
    description: "Flags agent responses containing harmful, violent, or illegal content before returning them to the user.",
    checkType: "model", latency: "~150ms", action: "Block", scope: "All agents",
    enabled: true, section: "output", triggeredToday: 2, lastTriggered: "4 hr ago",
  },
  {
    id: "g5", name: "Hallucination Flagging",
    description: "Flags responses that contain likely factual errors by comparing against a retrieval index.",
    checkType: "model", latency: "~200ms", action: "Allow+Log", scope: "2 agents",
    enabled: false, section: "output", triggeredToday: 0, lastTriggered: null,
  },
];

function GuardrailCard({ guardrail, onToggle }: { guardrail: Guardrail; onToggle: (id: string) => void }) {
  return (
    <div className={`ip-sheet ip-guardrail-card${!guardrail.enabled ? " ip-guardrail-card--disabled" : ""}`}>
      <div className="ip-guardrail-top">
        <div className="ip-guardrail-title-row">
          <div>
            <span className="ip-guardrail-name">{guardrail.name}</span>
            <div className="ip-guardrail-desc">{guardrail.description}</div>
          </div>
          <label className="ip-toggle" style={{ flexShrink: 0, marginLeft: 12 }}>
            <input type="checkbox" checked={guardrail.enabled} onChange={() => onToggle(guardrail.id)} />
            <span className="ip-toggle-track" />
            <span className="ip-toggle-thumb" />
          </label>
        </div>
      </div>

      <div className="ip-guardrail-meta-row">
        <div className="ip-guardrail-check-pill" style={{
          background: guardrail.checkType === "local" ? "var(--status-passed-bg)" : "var(--status-masked-bg)",
          color: guardrail.checkType === "local" ? "var(--status-passed-text)" : "var(--status-masked-text)",
        }}>
          {guardrail.checkType === "local" ? "Local" : "Model-assisted"}
          <span className="ip-mono" style={{ fontSize: 10, opacity: 0.8, marginLeft: 4 }}>{guardrail.latency}</span>
        </div>

        <div className="ip-guardrail-action-pill">
          Action: <strong>{guardrail.action}</strong>
        </div>

        <div className="ip-guardrail-scope-pill">{guardrail.scope}</div>

        {guardrail.enabled && (
          <div className="ip-guardrail-trigger-stat">
            {guardrail.triggeredToday > 0
              ? <><span style={{ fontWeight: 600, color: guardrail.action === "Block" ? "var(--status-blocked-text)" : "var(--status-masked-text)" }}>{guardrail.triggeredToday}×</span> today · last {guardrail.lastTriggered}</>
              : <span style={{ color: "var(--text-tertiary)" }}>No triggers today</span>
            }
          </div>
        )}
      </div>
    </div>
  );
}

export function Guardrails() {
  const [enabledMap, setEnabledMap] = useState<Record<string, boolean>>(
    Object.fromEntries(guardrails.map(g => [g.id, g.enabled]))
  );
  const [dismissedCallout, setDismissedCallout] = useState(false);
  const [activePage, setActivePage] = useState<any>("guardrails");

  const toggle = (id: string) => setEnabledMap(prev => ({ ...prev, [id]: !prev[id] }));

  const inputGuardrails = guardrails.filter(g => g.section === "input").map(g => ({ ...g, enabled: enabledMap[g.id] }));
  const outputGuardrails = guardrails.filter(g => g.section === "output").map(g => ({ ...g, enabled: enabledMap[g.id] }));

  const totalActive = Object.values(enabledMap).filter(Boolean).length;
  const totalTriggers = guardrails.reduce((acc, g) => acc + g.triggeredToday, 0);

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Guardrails</div>
          <div className="ip-page-subtitle">Behavioral controls for agent input and output</div>
        </div>
        <div className="ip-page-header-actions">
          <div className="ip-guardrail-summary-pills">
            <span className="ip-guardrail-pill">{totalActive} active</span>
            <span className="ip-guardrail-pill ip-guardrail-pill--warn">{totalTriggers} triggers today</span>
          </div>
          <button className="ip-btn-primary">New guardrail</button>
        </div>
      </div>

      <div className="ip-content">
        {!dismissedCallout && (
          <div className="ip-callout">
            <div className="ip-callout-content">
              <div className="ip-callout-title">Guardrails vs. Policies</div>
              <div className="ip-callout-body">
                <strong>Policies</strong> detect regulated data (PII, card numbers, SSNs). <strong>Guardrails</strong> detect behavior — prompt injection, off-topic requests, harmful outputs. Both run on every request, in order.
              </div>
            </div>
            <button className="ip-callout-dismiss" onClick={() => setDismissedCallout(true)}>×</button>
          </div>
        )}

        <div className="ip-guardrail-section">
          <div className="ip-guardrail-section-label">
            Input Guardrails
            <span className="ip-guardrail-section-count">— applied before the request reaches the model</span>
          </div>
          {inputGuardrails.map(g => <GuardrailCard key={g.id} guardrail={g} onToggle={toggle} />)}
        </div>

        <div className="ip-guardrail-divider" />

        <div className="ip-guardrail-section">
          <div className="ip-guardrail-section-label">
            Output Guardrails
            <span className="ip-guardrail-section-count">— applied to the model's response before returning it</span>
          </div>
          {outputGuardrails.map(g => <GuardrailCard key={g.id} guardrail={g} onToggle={toggle} />)}
        </div>
      </div>
    </AppShell>
  );
}
