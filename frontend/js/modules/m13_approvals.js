/**
 * Module M13: Approvals and Review, Side-by-Side Review Screen, Delegation, Approval Rules
 * Routes: /approvals, /approvals/:id
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderAIGeneratedTag, renderTableSkeleton } from '../components/shared.js';

let activeApprovalType = 'All';

export async function renderApprovalsView(container) {
  const approvals = await api.getApprovals();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Work</span>
        <span class="breadcrumb-separator">/</span>
        <span>Approvals & Review</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Executive Approval & Review Inbox</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Human-in-the-loop review station for AI settlements, legal drafts, outgoing communications, and OCR extractions.
          </p>
        </div>
        <div class="page-actions">
          <!-- Away / Delegation Toggle -->
          <button class="btn btn-secondary btn-sm" onclick="window.openDelegationModal()">
            ✈️ Away Delegation: Off
          </button>
          <button class="btn btn-secondary btn-sm" onclick="window.openApprovalRulesModal()">
            Approval Rules Matrix
          </button>
          <button class="btn btn-primary btn-sm" onclick="window.bulkApproveLowRisk()">
            Bulk Review Low-Risk (2)
          </button>
        </div>
      </div>
    </div>

    <!-- Tabs by Approval Type (Section 13) -->
    <div class="tabs-nav">
      <button class="tab-btn ${activeApprovalType === 'All' ? 'active' : ''}" onclick="window.setApprovalFilter('All')">All Items (${approvals.length})</button>
      <button class="tab-btn ${activeApprovalType === 'Settlements' ? 'active' : ''}" onclick="window.setApprovalFilter('Settlements')">Settlements</button>
      <button class="tab-btn ${activeApprovalType === 'Drafts' ? 'active' : ''}" onclick="window.setApprovalFilter('Drafts')">Drafts</button>
      <button class="tab-btn ${activeApprovalType === 'Extracted fields' ? 'active' : ''}" onclick="window.setApprovalFilter('Extracted fields')">Extracted Fields</button>
      <button class="tab-btn ${activeApprovalType === 'Outgoing messages' ? 'active' : ''}" onclick="window.setApprovalFilter('Outgoing messages')">Outgoing Messages</button>
      <button class="tab-btn ${activeApprovalType === 'Filings' ? 'active' : ''}" onclick="window.setApprovalFilter('Filings')">Filings</button>
      <button class="tab-btn ${activeApprovalType === 'Reports' ? 'active' : ''}" onclick="window.setApprovalFilter('Reports')">Reports & Exports</button>
    </div>

    <!-- Inbox Table -->
    <div id="approvals-table-container">
      ${renderApprovalsTable(approvals)}
    </div>
  `;

  window.setApprovalFilter = (type) => {
    activeApprovalType = type;
    renderApprovalsView(container);
  };

  window.openDelegationModal = () => {
    const delegate = prompt("Enter delegate colleague email while you are away:", "finance@meridianinfra.in");
    if (delegate) {
      window.MeridianApp.showToast(`Delegation active: Review queue routed to ${delegate} until 05 Nov 2026.`, 'success');
    }
  };

  window.openApprovalRulesModal = () => {
    alert("Approval Rules Matrix:\n• Settlements > ₹ 10 Cr: Requires Manager / Board Member\n• Legal Drafts: Requires Lawyer\n• Telephony Voice Calls: Requires Administrator\n• Filings: Requires Company Secretary");
  };

  window.bulkApproveLowRisk = () => {
    window.MeridianApp.showToast('Bulk-approved 2 low-risk field items. Logged in audit history.', 'success');
  };
}

function renderApprovalsTable(approvals) {
  const filtered = activeApprovalType === 'All' ? approvals : approvals.filter(a => a.type === activeApprovalType);

  return `
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Approval Item Title</th>
            <th>Type</th>
            <th>Requested By</th>
            <th>Age</th>
            <th>Priority</th>
            <th>Target Role</th>
            <th>Status</th>
            <th style="text-align:right;">Decision</th>
          </tr>
        </thead>
        <tbody>
          ${filtered.map(a => `
            <tr onclick="window.location.hash='#/approvals/${a.id}'">
              <td>
                <div style="font-weight:700; color:var(--text-main);">${a.title}</div>
                <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">${a.summary}</div>
              </td>
              <td><span class="status-badge calculated">${a.type}</span></td>
              <td><strong>${a.requestedBy}</strong></td>
              <td style="font-size:12px; color:var(--text-tertiary);">${a.age}</td>
              <td><span class="status-badge ${a.priority === 'Urgent' ? 'rejected' : a.priority === 'High' ? 'needs-approval' : 'unreviewed'}">${a.priority}</span></td>
              <td><span style="font-size:12px; font-weight:600; color:var(--primary);">${a.targetRole}</span></td>
              <td>${renderStatusBadge(a.status)}</td>
              <td style="text-align:right;">
                <a href="#/approvals/${a.id}" class="btn btn-primary btn-sm" onclick="event.stopPropagation()">Review Screen →</a>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export async function renderApprovalReviewView(container, approvalId) {
  const approvals = await api.getApprovals();
  const item = approvals.find(a => a.id === approvalId) || approvals[0];

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/approvals">Approvals</a>
        <span class="breadcrumb-separator">/</span>
        <span>${item.id}</span>
      </div>
      <div class="page-title-row">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h1 class="page-title">${item.title}</h1>
            ${renderStatusBadge(item.status)}
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Requested by <strong>${item.requestedBy}</strong> • Target Role: ${item.targetRole}
          </p>
        </div>
      </div>
    </div>

    <!-- SideBySideReview Split View Layout (Section 3 Specification) -->
    <div class="split-view-container">
      <!-- Left: Source Evidence Document -->
      <div class="card" style="display:flex; flex-direction:column; padding:0; overflow:hidden;">
        <div style="padding:12px 16px; background:var(--bg-subtle); border-bottom:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
          <div style="font-weight:600; font-size:13px;">
            📄 Source Citation: ${item.sourceDocName} (Page ${item.sourcePage})
          </div>
          <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.openDocViewer('${item.sourceDocId}', ${item.sourcePage})">
            Open in Document Viewer
          </button>
        </div>
        <div class="doc-viewer-canvas" style="flex:1;">
          <div class="mock-pdf-page">
            <div style="border-bottom:2px solid #E5E7EB; padding-bottom:10px; margin-bottom:14px;">
              <h3 style="font-size:16px; font-weight:bold;">PRIMARY INSTRUMENT EXCERPT</h3>
              <div style="font-size:11px; color:#6B7280;">Document Reference: ${item.sourceDocId} • Page ${item.sourcePage}</div>
            </div>
            <div class="pdf-highlight" style="margin:20px 0; font-size:14px; font-weight:600;">
              Grounding Clause / Primary Proof:
              <br>
              ${item.summary}
            </div>
            <p style="font-size:12px; color:#4B5563; line-height:1.6;">
              Original covenants, interest schedules, or draft pleadings recorded in primary enterprise vault.
            </p>
          </div>
        </div>
      </div>

      <!-- Right: AI Output & Mandatory Comment Box -->
      <div class="card" style="display:flex; flex-direction:column; overflow:hidden; padding:20px;">
        <div style="margin-bottom:14px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="font-size:15px; font-weight:700;">AI Synthesized Recommendation</h3>
            ${renderAIGeneratedTag('Subject to Human Sign-Off')}
          </div>
          <p style="font-size:12px; color:var(--text-muted); margin-top:2px;">Review proposed action details below.</p>
        </div>

        <div style="flex:1; overflow-y:auto; background:var(--bg-subtle); border-radius:8px; padding:16px; margin-bottom:16px; border:1px solid var(--border-subtle); font-size:13px; line-height:1.6;">
          <pre style="white-space:pre-wrap; font-family:inherit;">${JSON.stringify(item.aiOutput, null, 2)}</pre>
        </div>

        <!-- Mandatory Comment Box -->
        <div class="form-group">
          <label class="form-label" style="font-weight:700;">Reviewer Audit Comment (Mandatory)</label>
          <textarea id="approval-comment-input" class="form-control" rows="2" placeholder="Record mandatory rationale for audit timeline (e.g. 'Approved following committee review')...">Approved in compliance with group authority delegation matrix.</textarea>
        </div>

        <!-- Action Buttons: Approve, Edit, Reject -->
        <div style="display:flex; justify-content:space-between; align-items:center; padding-top:12px; border-top:1px solid var(--border-subtle);">
          <button class="btn btn-danger" onclick="window.recordDecision('${item.id}', 'Rejected')">
            ✕ Reject
          </button>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-secondary" onclick="window.recordDecision('${item.id}', 'Corrected')">
              ✎ Edit & Correct
            </button>
            <button class="btn btn-primary" onclick="window.recordDecision('${item.id}', 'Approved')">
              ✓ Approve Decision
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  window.recordDecision = async (id, decision) => {
    const comment = document.getElementById('approval-comment-input')?.value.trim();
    if (!comment) {
      alert("A reviewer comment is mandatory before submitting a decision.");
      return;
    }
    await api.submitApprovalDecision(id, decision, comment);
    window.MeridianApp.showToast(`Decision recorded: ${decision}. Timeline updated in Audit Log.`, 'success');
    window.location.hash = '#/approvals';
  };
}
