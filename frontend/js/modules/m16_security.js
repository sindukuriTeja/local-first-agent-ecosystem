/**
 * Module M16: Security, Audit and Privacy, Immutable Audit Log, Privacy Rules, Backup Health
 * Routes: /security, /security/audit
 */
import { api } from '../services/api.js';
import { renderStatusBadge, renderTableSkeleton } from '../components/shared.js';

let activeSecTab = 'audit'; // 'audit' | 'privacy' | 'backup'

export async function renderSecurityView(container) {
  const auditLogs = await api.getAuditLogs();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>System</span>
        <span class="breadcrumb-separator">/</span>
        <span>Security & Audit</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Enterprise Security, Audit & Privacy Governance</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Cryptographically sealed immutable audit trails, data loss prevention (DLP), and zero-trust perimeter health.
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-secondary btn-sm" onclick="window.requestAuditExport()">
            🔒 Export Audit Log (Needs Manager Approval)
          </button>
        </div>
      </div>
    </div>

    <!-- Pinned Critical Alert: Cross-Company Access Prevention (Section 16 Specification) -->
    <div style="background:var(--color-danger-bg); border: 2px solid var(--color-danger-border); padding:16px 20px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
      <div style="display:flex; align-items:center; gap:12px;">
        <span style="font-size:24px;">🚨</span>
        <div>
          <div style="font-weight:700; color:var(--color-danger-text); font-size:13px; text-transform:uppercase; letter-spacing:0.04em;">HIGHEST SEVERITY AUDIT EVENT: CROSS-COMPANY ISOLATION GUARD ACTIVATED</div>
          <div style="font-size:12px; color:var(--color-danger-text); margin-top:2px;">
            Access attempt by External Counsel (Adv. Harish Salve) to unassigned associate parcel records (COMP-005 Sunrise Developers) was intercepted and quarantined by RoleGate Policy S.4.
          </div>
        </div>
      </div>
      <span class="status-badge rejected">Threat Quarantined</span>
    </div>

    <!-- Security Sub-Tabs -->
    <div class="tabs-nav">
      <button class="tab-btn ${activeSecTab === 'audit' ? 'active' : ''}" onclick="window.setSecTab('audit')">Immutable Audit Log (${auditLogs.length})</button>
      <button class="tab-btn ${activeSecTab === 'privacy' ? 'active' : ''}" onclick="window.setSecTab('privacy')">Privacy Rules & Field Redaction</button>
      <button class="tab-btn ${activeSecTab === 'backup' ? 'active' : ''}" onclick="window.setSecTab('backup')">Backup & Disaster Recovery</button>
    </div>

    <div id="security-tab-content">
      ${renderAuditLogTable(auditLogs)}
    </div>
  `;

  window.setSecTab = (tab) => {
    activeSecTab = tab;
    const target = document.getElementById('security-tab-content');
    if (!target) return;

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    if (tab === 'audit') {
      target.innerHTML = renderAuditLogTable(auditLogs);
    } else if (tab === 'privacy') {
      target.innerHTML = renderPrivacyRulesTab();
    } else if (tab === 'backup') {
      target.innerHTML = renderBackupStatusTab();
    }
  };

  window.requestAuditExport = () => {
    window.MeridianApp.showToast('Audit log export request queued in Approvals for Manager sign-off.', 'warning');
  };
}

export function renderAuditLogView(container) {
  renderSecurityView(container);
}

function renderAuditLogTable(logs) {
  return `
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" placeholder="Search actor, action, record, or module..." />
        <div style="display:flex; align-items:center; gap:8px; font-size:12px; color:var(--text-muted);">
          <span>🔒 Read-Only Ledger • Records cannot be modified or deleted.</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>Actor (User / Agent)</th>
            <th>Action Category</th>
            <th>Affected Record</th>
            <th>Sources / Details</th>
            <th>Security Seal</th>
          </tr>
        </thead>
        <tbody>
          ${logs.map(l => `
            <tr>
              <td style="font-size:12px; color:var(--text-muted);">${l.timestamp}</td>
              <td>
                <div style="font-weight:600; color:var(--text-main);">${l.actor}</div>
                <div style="font-size:10px; color:var(--text-tertiary);">${l.actorType} • IP: ${l.ip}</div>
              </td>
              <td><strong>${l.action}</strong></td>
              <td><span style="font-family:var(--font-mono); font-size:12px; color:var(--primary);">${l.record}</span></td>
              <td style="font-size:12px; color:var(--text-muted); max-width:320px;">
                ${l.details}
                ${l.sourceUsed ? `<div style="font-size:10px; color:var(--text-tertiary); margin-top:2px;">Source: ${l.sourceUsed}</div>` : ''}
              </td>
              <td>
                <span style="font-size:11px; background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:2px 6px; border-radius:4px; display:inline-flex; align-items:center; gap:4px;">
                  🔒 Sealed
                </span>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderPrivacyRulesTab() {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">Data Loss Prevention (DLP) & Privacy Safeguards</h3>
      <p style="font-size:13px; color:var(--text-muted); margin-bottom:16px;">
        Automatic redaction filters enforced before any prompt or query crosses the private enterprise enclave to external legal APIs.
      </p>

      <div style="display:flex; flex-direction:column; gap:16px;">
        <label style="display:flex; justify-content:space-between; align-items:center; padding:12px; background:var(--bg-subtle); border-radius:6px;">
          <div>
            <strong>Company & Personal Name Redaction</strong>
            <div style="font-size:12px; color:var(--text-muted);">Replaces Meridian group company names, director names, and individual borrower parties with generic tokens.</div>
          </div>
          <input type="checkbox" checked />
        </label>

        <label style="display:flex; justify-content:space-between; align-items:center; padding:12px; background:var(--bg-subtle); border-radius:6px;">
          <div>
            <strong>Monetary Values & Claim Amounts Redaction</strong>
            <div style="font-size:12px; color:var(--text-muted);">Redacts sanction limits, outstanding claim crores, and settlement haircuts before dispatch.</div>
          </div>
          <input type="checkbox" checked />
        </label>

        <label style="display:flex; justify-content:space-between; align-items:center; padding:12px; background:var(--bg-subtle); border-radius:6px;">
          <div>
            <strong>Court Case Numbers & Specific Survey Parcel Numbers</strong>
            <div style="font-size:12px; color:var(--text-muted);">Converts specific OA/CP suit numbers into abstract legal propositions.</div>
          </div>
          <input type="checkbox" checked />
        </label>
      </div>
    </div>
  `;
}

function renderBackupStatusTab() {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">Disaster Recovery & Encrypted Snapshot Health</h3>
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px; margin-bottom:20px;">
        <div style="padding:16px; background:var(--color-success-bg); border:1px solid var(--color-success-border); border-radius:8px;">
          <div style="font-size:11px; font-weight:700; color:var(--color-success-text); text-transform:uppercase;">Backup Health Status</div>
          <div style="font-size:18px; font-weight:700; color:var(--color-success-text); margin:4px 0;">Healthy (Green)</div>
          <div style="font-size:11px; color:var(--color-success-text);">Automated schedule: Every 6 hours</div>
        </div>
        <div style="padding:16px; background:var(--bg-subtle); border:1px solid var(--border-subtle); border-radius:8px;">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Last Snapshot</div>
          <div style="font-size:14px; font-weight:700; margin:4px 0;">28 Oct 2026, 12:00 PM</div>
          <div style="font-size:11px; color:var(--text-muted);">Size: 4.8 GB • SHA-256 Verified</div>
        </div>
        <div style="padding:16px; background:var(--bg-subtle); border:1px solid var(--border-subtle); border-radius:8px;">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase;">Last Restore Verification</div>
          <div style="font-size:14px; font-weight:700; margin:4px 0;">26 Oct 2026 (Pass)</div>
          <div style="font-size:11px; color:var(--color-success-text);">Zero corruption detected</div>
        </div>
      </div>
    </div>
  `;
}
