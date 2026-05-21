import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./TestConsole.css";

const SAMPLE_TEXT = `My card number is 4111111111111111 and my SSN is 123-45-6789. Please charge me $250 for my subscription renewal.`;

interface Detection {
  type: string;
  position: string;
  confidence: string;
  detectedBy: string;
  ruleset: string;
  action: string;
  original: string;
  sanitized: string;
}

const detections: Detection[] = [
  {
    type: "CREDIT_CARD",
    position: "17–32",
    confidence: "0.99",
    detectedBy: "Regex → Luhn validation",
    ruleset: "PCI-DSS",
    action: "Tokenize",
    original: "4111 1111 1111 1111",
    sanitized: "[TOKEN·cc_a3f2d1]",
  },
  {
    type: "SSN",
    position: "47–57",
    confidence: "0.96",
    detectedBy: "Regex",
    ruleset: "HIPAA",
    action: "Mask",
    original: "123-45-6789",
    sanitized: "[MASKED·SSN]",
  },
];

export function TestConsole() {
  const [inputText, setInputText] = useState("");
  const [hasRun, setHasRun] = useState(false);
  const [running, setRunning] = useState(false);
  const [activePage, setActivePage] = useState<any>("console");

  const handleRun = () => {
    if (!inputText.trim()) return;
    setRunning(true);
    setTimeout(() => {
      setRunning(false);
      setHasRun(true);
    }, 900);
  };

  const sanitizedOutput = `My card number is [TOKEN·cc_a3f2d1] and my SSN is [MASKED·SSN]. Please charge me $250 for my subscription renewal.`;

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Test Console</div>
          <div className="ip-page-subtitle">Active rulesets: <span className="ip-badge ip-badge--passed" style={{ fontSize: 11, marginLeft: 4 }}><span className="ip-badge-dot" />PCI-DSS</span> <span className="ip-badge ip-badge--passed" style={{ fontSize: 11, marginLeft: 4 }}><span className="ip-badge-dot" />HIPAA</span></div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-ghost">Change rulesets →</button>
        </div>
      </div>

      <div className="ip-content">
        <div className="ip-console-split">
          <div className="ip-console-left">
            <div className="ip-section-heading">Input</div>
            <div className="ip-console-input-wrap">
              <textarea
                className="ip-console-textarea"
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                placeholder={`Paste any text or agent message here...\nTry: "${SAMPLE_TEXT}"`}
                spellCheck={false}
              />
            </div>
            <div className="ip-console-actions">
              <span className="ip-console-hint">⌘↵ to run</span>
              <button
                className="ip-btn-primary"
                onClick={handleRun}
                disabled={running || !inputText.trim()}
                style={{ opacity: (running || !inputText.trim()) ? 0.5 : 1 }}
              >
                {running ? "Analyzing..." : "Run Analysis →"}
              </button>
            </div>

            {!hasRun && (
              <div className="ip-console-sample">
                <div className="ip-section-heading" style={{ marginBottom: 8 }}>Try a sample</div>
                <button
                  className="ip-sample-btn"
                  onClick={() => setInputText(SAMPLE_TEXT)}
                >
                  "{SAMPLE_TEXT.slice(0, 60)}..."
                </button>
              </div>
            )}
          </div>

          <div className="ip-console-right">
            {!hasRun ? (
              <div className="ip-console-empty">
                <div className="ip-console-empty-icon">
                  <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                    <rect x="4" y="8" width="24" height="16" rx="2" stroke="var(--text-tertiary)" strokeWidth="1.5" fill="none"/>
                    <path d="M9 13h14M9 17h10" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                </div>
                <div className="ip-console-empty-title">Results will appear here.</div>
                <div className="ip-console-empty-sub">Enter text on the left and run the analysis<br />to see exactly what Covenant AI would do.</div>
              </div>
            ) : (
              <div className="ip-console-results">
                <div className="ip-results-header">
                  <span className="ip-results-title">Analysis Complete</span>
                  <span className="ip-results-latency ip-mono">142ms</span>
                </div>

                <div className="ip-results-outcome">
                  <div className="ip-section-heading">Overall Outcome</div>
                  <div className="ip-badge ip-badge--masked" style={{ fontSize: 13, padding: "4px 10px" }}>
                    <span className="ip-badge-dot" />
                    2 detections · Action: Masked
                  </div>
                </div>

                <div className="ip-results-section">
                  <div className="ip-section-heading">Detections</div>
                  {detections.map((d) => (
                    <div key={d.type} className="ip-card" style={{ marginBottom: 10 }}>
                      <div className="ip-detection-type ip-mono">{d.type}</div>
                      <div className="ip-detection-meta">Position {d.position} · Confidence {d.confidence}</div>
                      <div className="ip-detection-meta">Detected by: {d.detectedBy}</div>
                      <div className="ip-detection-meta">Ruleset: {d.ruleset} · Action: {d.action}</div>
                      <div className="ip-detection-values">
                        <div className="ip-detection-row">
                          <span className="ip-detection-label">Original</span>
                          <span className="ip-mono ip-val-original">{d.original}</span>
                        </div>
                        <div className="ip-detection-row">
                          <span className="ip-detection-label">Sanitized</span>
                          <span className="ip-mono ip-val-sanitized">{d.sanitized}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="ip-results-section">
                  <div className="ip-section-heading">Sanitized Output</div>
                  <div className="ip-json-viewer">
                    <pre style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "#E2E8F0", whiteSpace: "pre-wrap", wordBreak: "break-all", margin: 0 }}>
                      {sanitizedOutput}
                    </pre>
                  </div>
                </div>

                <div className="ip-results-section">
                  <div className="ip-section-heading">Layer Timing</div>
                  <div className="ip-timing-table">
                    {[
                      ["Regex scan", "8ms"],
                      ["Luhn check", "2ms"],
                      ["NER scan", "89ms"],
                      ["Action apply", "4ms"],
                      ["Total", "142ms"],
                    ].map(([label, time]) => (
                      <div key={label} className={`ip-timing-row${label === "Total" ? " ip-timing-row--total" : ""}`}>
                        <span>{label}</span>
                        <span className="ip-mono">{time}</span>
                      </div>
                    ))}
                  </div>
                  <div className="ip-timing-note">NER layer triggered: Yes (regex had hits)</div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
