import React from "react";
import logoUrl from "../../../assets/govern_logo.png";
import "./_shared/_shared.css";
import "./Workspaces.css";

const WORKSPACES = [
  {
    id: "healthcare",
    title: "Healthcare & Life Sciences",
    description: "HIPAA compliance, PHI scrubbing, and medical terminology safeguards.",
  },
  {
    id: "legal",
    title: "Legal & Compliance",
    description: "Attorney-client privilege detection, contract redlining rules.",
  },
  {
    id: "financial",
    title: "Banking & Financial Services",
    description: "PCI-DSS, AML/SAR monitoring, and financial covenant tracking.",
  },
  {
    id: "tech",
    title: "General Technology",
    description: "GDPR, SOC2 Type II, and standard prompt injection defenses.",
  }
];

export function Workspaces() {
  const handleSelect = (workspaceId: string) => {
    localStorage.setItem("covenant_workspace", workspaceId);
    window.location.hash = "compliance-layer";
  };

  return (
    <div className="ip-shell ip-workspaces-page">
      <div className="ip-workspaces-container">
        <div className="ip-workspaces-header">
          <div className="ip-workspaces-logo">
            <img src={logoUrl} alt="Covenant AI Logo" className="ip-logo-icon" style={{width: 32, height: 32, objectFit: 'contain'}} />
            <span className="ip-workspaces-logo-text">Covenant AI</span>
          </div>
          <div className="ip-workspaces-title">Select your Sector Workspace</div>
          <div className="ip-workspaces-subtitle">
            Choose an industry vertical to load tailored compliance frameworks and safeguards.
          </div>
        </div>

        <div className="ip-workspaces-grid">
          {WORKSPACES.map((ws) => (
            <div 
              key={ws.id} 
              className="ip-workspace-card"
              onClick={() => handleSelect(ws.id)}
            >
              <div className="ip-workspace-card-title">{ws.title}</div>
              <div className="ip-workspace-card-desc">{ws.description}</div>
              <div className="ip-workspace-card-action">Initialize Environment &rarr;</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
