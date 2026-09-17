import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./GDPR.css";

export function GDPR() {
  const [activeTab, setActiveTab] = useState<"map" | "erasure" | "retention">("map");

  return (
    <AppShell activePage="gdpr">
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">GDPR Data Rights</div>
          <div className="ip-page-subtitle">
            Manage Data Subject Access Requests (DSAR), Right to Erasure, and Retention Policies
          </div>
        </div>
        <div className="ip-page-header-actions">
          {activeTab === "map" && (
            <button 
              className="ip-btn-primary" 
              onClick={() => {
                // In a real app, you'd include the auth token.
                // For the mockup we can just link to it or fetch it.
                // Since this is a mockup without a real token injected here,
                // we'll do a simple window.open or fetch.
                const token = sessionStorage.getItem("covenant_api_key") || "";
                fetch("http://localhost:8000/gdpr/data-map/export", {
                  headers: {
                    "Authorization": token ? `Bearer ${token}` : ""
                  }
                })
                .then(res => res.blob())
                .then(blob => {
                  const url = window.URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "covenant_gdpr_datamap.pdf";
                  a.click();
                  window.URL.revokeObjectURL(url);
                })
                .catch(err => console.error("Export failed", err));
              }}
            >
              Export Data Map (PDF)
            </button>
          )}
        </div>
      </div>

      <div className="gdpr-tabs">
        <button 
          className={`gdpr-tab ${activeTab === "map" ? "active" : ""}`}
          onClick={() => setActiveTab("map")}
        >
          Data Map
        </button>
        <button 
          className={`gdpr-tab ${activeTab === "erasure" ? "active" : ""}`}
          onClick={() => setActiveTab("erasure")}
        >
          Erasure Queue
        </button>
        <button 
          className={`gdpr-tab ${activeTab === "retention" ? "active" : ""}`}
          onClick={() => setActiveTab("retention")}
        >
          Retention Policies
        </button>
      </div>

      <div className="ip-content">
        {activeTab === "map" && <DataMap />}
        {activeTab === "erasure" && <ErasureQueue />}
        {activeTab === "retention" && <RetentionPolicy />}
      </div>
    </AppShell>
  );
}

function DataMap() {
  const mockMap = [
    { type: "PERSON", count: 4210, processing_purpose: "AI Model Proxy Inference", legal_basis: "Legitimate Interest" },
    { type: "EMAIL", count: 2841, processing_purpose: "AI Model Proxy Inference", legal_basis: "Legitimate Interest" },
    { type: "ORG", count: 1240, processing_purpose: "AI Model Proxy Inference", legal_basis: "Legitimate Interest" },
    { type: "PHONE", count: 850, processing_purpose: "AI Model Proxy Inference", legal_basis: "Legitimate Interest" }
  ];

  return (
    <div className="ip-sheet">
      <div className="gdpr-section-title">Mapped Data Entities</div>
      <p className="gdpr-section-desc">
        A real-time index of all PII detected and processed by Covenant AI across all connected models.
      </p>
      
      <table className="ip-table mt-4">
        <thead>
          <tr>
            <th>Entity Type</th>
            <th>Records Processed</th>
            <th>Processing Purpose</th>
            <th>Legal Basis (Art. 6)</th>
          </tr>
        </thead>
        <tbody>
          {mockMap.map(r => (
            <tr key={r.type}>
              <td><span className="ip-tag">{r.type}</span></td>
              <td><span className="ip-mono">{r.count.toLocaleString()}</span></td>
              <td>{r.processing_purpose}</td>
              <td>{r.legal_basis}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ErasureQueue() {
  const mockQueue = [
    { id: "req_f829h1", subject: "e9a28c31f4", status: "completed", deleted: 42, date: "2026-09-12 10:14" },
    { id: "req_a938c2", subject: "c4b918df2e", status: "pending", deleted: 0, date: "2026-09-12 11:22" },
  ];

  return (
    <div className="ip-sheet">
      <div className="gdpr-section-title">Erasure Requests (Right to be Forgotten)</div>
      <p className="gdpr-section-desc">
        Submit hashed data subject identifiers to purge all associated PII from audit logs and vault storage.
      </p>
      
      <div style={{ marginTop: 16, marginBottom: 24, display: "flex", gap: 12 }}>
        <input 
          type="text" 
          placeholder="Enter hashed data subject ID..." 
          className="ip-input" 
          style={{ width: 300 }}
        />
        <button className="ip-btn-primary">Submit Erasure Request</button>
      </div>

      <table className="ip-table">
        <thead>
          <tr>
            <th>Request ID</th>
            <th>Data Subject (Hash)</th>
            <th>Status</th>
            <th>Records Deleted</th>
            <th>Requested At</th>
          </tr>
        </thead>
        <tbody>
          {mockQueue.map(r => (
            <tr key={r.id}>
              <td><span className="ip-mono" style={{fontSize: 12}}>{r.id}</span></td>
              <td><span className="ip-mono" style={{fontSize: 12}}>{r.subject}...</span></td>
              <td>
                <span className={`ip-badge ip-badge--${r.status === "completed" ? "passed" : "masked"}`}>
                  <span className="ip-badge-dot" />
                  {r.status.toUpperCase()}
                </span>
              </td>
              <td>{r.deleted}</td>
              <td><span className="ip-mono" style={{fontSize: 12}}>{r.date}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RetentionPolicy() {
  return (
    <div className="ip-sheet">
      <div className="gdpr-section-title">Data Retention Policy</div>
      <p className="gdpr-section-desc">
        Configure how long audit logs and vaulted PII are retained before automatic secure deletion.
      </p>
      
      <div className="gdpr-form-group" style={{ marginTop: 24 }}>
        <label>Default Retention Period</label>
        <select className="ip-input" style={{ width: 200, marginTop: 8 }}>
          <option value="7">7 Days</option>
          <option value="30" selected>30 Days</option>
          <option value="90">90 Days</option>
          <option value="365">1 Year</option>
        </select>
        <p style={{ fontSize: 12, color: "var(--text-tertiary)", marginTop: 8 }}>
          Records exceeding this age are permanently purged via a daily scheduled job.
        </p>
      </div>

      <button className="ip-btn-primary" style={{ marginTop: 24 }}>Save Policy</button>
    </div>
  );
}
