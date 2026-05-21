import React, { useState } from "react";
import { AppShell } from "./_shared/AppShell";
import "./_shared/_shared.css";
import "./Team.css";

interface Member {
  id: string;
  name: string;
  email: string;
  role: "Owner" | "Admin" | "Viewer";
  initials: string;
  joined: string;
  lastActive: string;
  status: "active" | "pending";
}

const members: Member[] = [
  { id: "m1", name: "Aaryan Yadav", email: "aaryan@acmecorp.com", role: "Owner", initials: "AY", joined: "Jan 12, 2026", lastActive: "Just now", status: "active" },
  { id: "m2", name: "Deshraj Singh", email: "deshraj@acmecorp.com", role: "Admin", initials: "DS", joined: "Jan 12, 2026", lastActive: "2 hr ago", status: "active" },
  { id: "m3", name: "Priya Sharma", email: "priya@acmecorp.com", role: "Viewer", initials: "PS", joined: "Mar 01, 2026", lastActive: "Yesterday", status: "active" },
  { id: "m4", name: "invite@pending.com", email: "invite@pending.com", role: "Viewer", initials: "?", joined: "—", lastActive: "—", status: "pending" },
];

const roleColor: Record<Member["role"], string> = {
  Owner: "var(--status-passed-text)",
  Admin: "#1D4ED8",
  Viewer: "var(--text-secondary)",
};
const roleBg: Record<Member["role"], string> = {
  Owner: "var(--status-passed-bg)",
  Admin: "#EFF6FF",
  Viewer: "var(--bg-elevated)",
};

const rolePerms = {
  Owner: ["Full access", "Billing & subscription", "Invite & remove members", "All data access"],
  Admin: ["Manage policies & frameworks", "View all logs", "Invite members (Viewer only)", "Issue & revoke API keys"],
  Viewer: ["View audit log", "View frameworks", "View violation reports", "Read-only"],
};

export function Team() {
  const [inviteOpen, setInviteOpen] = useState(false);
  const [activePage, setActivePage] = useState<any>("team");

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      <div className="ip-page-header">
        <div className="ip-page-header-left">
          <div className="ip-page-title">Team</div>
          <div className="ip-page-subtitle">Manage access and roles for your organization</div>
        </div>
        <div className="ip-page-header-actions">
          <button className="ip-btn-primary" onClick={() => setInviteOpen(true)}>Invite member</button>
        </div>
      </div>

      <div className="ip-content" style={{ display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Members table */}
        <div className="ip-sheet" style={{ padding: 0, overflow: "hidden" }}>
          <div className="ip-team-table-header">
            <span style={{ fontSize: 13, fontWeight: 500 }}>Members · {members.length}</span>
          </div>
          <table className="ip-table">
            <thead>
              <tr>
                <th>Member</th>
                <th>Role</th>
                <th>Joined</th>
                <th>Last Active</th>
                <th>Status</th>
                <th style={{ width: 40 }}></th>
              </tr>
            </thead>
            <tbody>
              {members.map(m => (
                <tr key={m.id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <div className="ip-member-avatar" style={{ opacity: m.status === "pending" ? 0.5 : 1 }}>
                        {m.initials}
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: m.status === "pending" ? 400 : 500, color: m.status === "pending" ? "var(--text-tertiary)" : "var(--text-primary)", fontStyle: m.status === "pending" ? "italic" : "normal" }}>{m.name}</div>
                        <div style={{ fontSize: 12, color: "var(--text-tertiary)" }}>{m.email}</div>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span style={{ fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 4, background: roleBg[m.role], color: roleColor[m.role] }}>
                      {m.role}
                    </span>
                  </td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{m.joined}</td>
                  <td style={{ fontSize: 13, color: "var(--text-secondary)" }}>{m.lastActive}</td>
                  <td>
                    {m.status === "pending"
                      ? <span className="ip-badge ip-badge--masked" style={{ fontSize: 11 }}><span className="ip-badge-dot" />Pending</span>
                      : <span className="ip-badge ip-badge--passed" style={{ fontSize: 11 }}><span className="ip-badge-dot" />Active</span>
                    }
                  </td>
                  <td>
                    {m.role !== "Owner" && <button className="ip-icon-btn">⋯</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Role permissions */}
        <div>
          <div className="ip-section-heading" style={{ marginBottom: 12 }}>Role Permissions</div>
          <div className="ip-roles-grid">
            {(["Owner", "Admin", "Viewer"] as Member["role"][]).map(role => (
              <div key={role} className="ip-sheet ip-role-card">
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
                  <span style={{ fontSize: 11, fontWeight: 500, padding: "2px 8px", borderRadius: 4, background: roleBg[role], color: roleColor[role] }}>{role}</span>
                </div>
                <ul className="ip-role-perms">
                  {rolePerms[role].map(p => (
                    <li key={p}>
                      <span className="ip-perm-check">✓</span> {p}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </div>

      {inviteOpen && (
        <>
          <div className="ip-modal-backdrop" onClick={() => setInviteOpen(false)} />
          <div className="ip-modal">
            <div className="ip-modal-header">
              <div style={{ fontSize: 15, fontWeight: 500 }}>Invite team member</div>
            </div>
            <div className="ip-modal-body">
              <div className="ip-modal-field">
                <label className="ip-modal-label">Email address</label>
                <input className="ip-input" placeholder="colleague@company.com" />
              </div>
              <div className="ip-modal-field">
                <label className="ip-modal-label">Role</label>
                <div className="ip-radio-group">
                  <label className="ip-radio"><input type="radio" name="role" /> Admin</label>
                  <label className="ip-radio"><input type="radio" name="role" defaultChecked /> Viewer</label>
                </div>
              </div>
            </div>
            <div className="ip-modal-footer">
              <button className="ip-btn-ghost" onClick={() => setInviteOpen(false)}>Cancel</button>
              <button className="ip-btn-primary">Send invite</button>
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}
