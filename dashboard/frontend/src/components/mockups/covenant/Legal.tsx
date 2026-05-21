import React from "react";
import "./_shared/_shared.css";
import "./Legal.css";

const CONTRACTS = [
  { id: "C-9921", type: "MSA", party: "Acme Corp", risk: "Low", status: "Active" },
  { id: "C-9922", type: "DPA", party: "Globex Inc", risk: "High", status: "Review Required" },
  { id: "C-9923", type: "NDA", party: "Soylent Corp", risk: "Medium", status: "Active" },
];

const DSARS = [
  { id: "DSAR-101", subject: "John Doe", type: "Erasure", due: "2026-06-15", status: "In Progress" },
  { id: "DSAR-102", subject: "Jane Smith", type: "Access", due: "2026-06-12", status: "Overdue" },
];

import { AppShell } from "./_shared/AppShell";

export function Legal() {
  return (
    <AppShell>
      <div className="ip-page">
        <div className="ip-page-header">
          <div className="ip-page-header-left">
            <h1 className="ip-page-title">Legal & Contracts</h1>
            <p className="ip-page-subtitle">Manage automated contract analysis, legal holds, and DSAR fulfillment.</p>
          </div>
          <div className="ip-page-header-actions">
            <button className="ip-btn-primary">Upload Contract</button>
          </div>
        </div>

        <div className="ip-content">
          <div className="ip-legal-grid">
            
            <div className="ip-sheet">
              <div className="ip-section-heading">Contract Risk Analysis</div>
              <div className="ip-table-container">
                <table className="ip-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Type</th>
                      <th>Counterparty</th>
                      <th>Risk</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {CONTRACTS.map(c => (
                      <tr key={c.id}>
                        <td className="ip-mono">{c.id}</td>
                        <td>{c.type}</td>
                        <td>{c.party}</td>
                        <td>
                          <span className={`ip-badge ${c.risk === 'High' ? 'ip-badge--blocked' : c.risk === 'Medium' ? 'ip-badge--masked' : 'ip-badge--passed'}`}>
                            <span className="ip-badge-dot" /> {c.risk}
                          </span>
                        </td>
                        <td>{c.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="ip-sheet">
              <div className="ip-section-heading">Active DSAR Requests (GDPR / CCPA)</div>
              <div className="ip-table-container">
                <table className="ip-table">
                  <thead>
                    <tr>
                      <th>Ref</th>
                      <th>Type</th>
                      <th>Due Date</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {DSARS.map(d => (
                      <tr key={d.id}>
                        <td className="ip-mono">{d.id}</td>
                        <td>{d.type}</td>
                        <td>{d.due}</td>
                        <td>
                          <span className={`ip-tag ${d.status === 'Overdue' ? 'ip-tag--danger' : ''}`}>
                            {d.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      </div>
    </AppShell>
  );
}
