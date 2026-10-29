/**
 * Shared Building Blocks (Section 3)
 * Reusable UI components conforming to strict enterprise guidelines
 */

// 1. StatusBadge: Field states & labels (Color + Icon + Text)
export function renderStatusBadge(status) {
  const s = String(status || 'Unreviewed').trim();
  const lower = s.toLowerCase();

  let cls = 'unreviewed';
  let icon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`;

  if (lower.includes('verified') || lower.includes('approved') || lower.includes('active') || lower.includes('compliant') || lower === 'free') {
    cls = 'verified';
    icon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`;
  } else if (lower.includes('corrected')) {
    cls = 'corrected';
    icon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
  } else if (lower.includes('rejected') || lower.includes('unverified citation') || lower.includes('overdue') || lower.includes('discrepancy') || lower.includes('not reconcile')) {
    cls = 'rejected';
    icon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`;
  } else if (lower.includes('needs approval') || lower.includes('needs review') || lower.includes('attention') || lower.includes('disputed') || lower.includes('mortgaged') || lower.includes('attached') || lower.includes('pending')) {
    cls = 'needs-approval';
    icon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`;
  } else if (lower.includes('calculated') || lower.includes('scenario')) {
    cls = 'calculated';
    icon = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="8" y1="6" x2="16" y2="6"/><line x1="16" y1="14" x2="16" y2="18"/><path d="M8 10h.01M12 10h.01M16 10h.01M8 14h.01M12 14h.01M8 18h.01M12 18h.01"/></svg>`;
  }

  return `<span class="status-badge ${cls}" title="${s}">${icon} <span>${s}</span></span>`;
}

// 2. SourceChip: Pill showing doc name & page. Click opens Document Viewer
export function renderSourceChip(docId, docName = 'Source Document', page = 1) {
  const shortName = docName.length > 24 ? docName.substring(0, 22) + '...' : docName;
  return `<button type="button" class="source-chip" data-doc-id="${docId}" data-page="${page}" title="Open ${docName} at page ${page}" onclick="window.MeridianApp.openDocViewer('${docId}', ${page})">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
    <span>${shortName} : p.${page}</span>
  </button>`;
}

// 3. ConfidenceBar: 0 to 100% bar; below 80% shows amber hint
export function renderConfidenceBar(confidence = 90) {
  const c = Math.min(100, Math.max(0, Number(confidence) || 0));
  let fillCls = 'high';
  let hint = '';

  if (c < 80) {
    fillCls = c < 60 ? 'low' : 'medium';
    hint = `<span class="confidence-hint">Needs review</span>`;
  }

  return `<div class="confidence-container" title="${c}% confidence score">
    <div class="confidence-bar-track">
      <div class="confidence-bar-fill ${fillCls}" style="width: ${c}%"></div>
    </div>
    <span class="confidence-text">${c}%</span>
    ${hint}
  </div>`;
}

// 4. AsOfStamp: "Data as of 28 Oct 2026"
export function renderAsOfStamp(dateStr = '28 Oct 2026') {
  return `<span class="as-of-stamp" title="Authoritative data benchmark date">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
    Data as of ${dateStr}
  </span>`;
}

// 5. NotFoundState: Clear message, reason, and request button
export function renderNotFoundState(title = 'Record not found', reason = 'No authoritative source has been indexed for this inquiry.', requestCallback = null) {
  return `<div class="not-found-state">
    <div class="not-found-icon">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/></svg>
    </div>
    <div class="not-found-title">${title}</div>
    <div class="not-found-reason">${reason}</div>
    <button type="button" class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Information request submitted to Compliance Desk', 'info')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      Request Information
    </button>
  </div>`;
}

// 6. ApprovalBanner: Top strip for items awaiting human approval
export function renderApprovalBanner(message, reviewRoute = '#/approvals') {
  return `<div class="approval-banner">
    <div class="approval-banner-content">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
      <span><strong>Human Approval Required:</strong> ${message}</span>
    </div>
    <a href="${reviewRoute}" class="btn btn-sm btn-secondary" style="background:#fff; color:#92400E; border-color:#FDE68A;">
      Review in Inbox
    </a>
  </div>`;
}

// 7. ConfidentialityTag: Public, Internal, Confidential, Restricted
export function renderConfidentialityTag(level = 'Internal') {
  const l = String(level).toLowerCase();
  return `<span class="confidentiality-tag ${l}">${level}</span>`;
}

// 8. AIGeneratedTag: Small label on AI-produced draft/analysis
export function renderAIGeneratedTag(label = 'AI Generated (Draft - Needs Approval)') {
  return `<span class="ai-generated-tag" title="Generated by private AI model; awaiting human review">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>
    ${label}
  </span>`;
}

// 9. CrossLink: Clickable pill to link records across modules
export function renderCrossLink(type, id, label) {
  const routeMap = {
    loan: `#/loans/${id}`,
    parcel: `#/land/${id}`,
    matter: `#/matters/${id}`,
    company: `#/companies/${id}`,
    document: `#/documents/${id}`
  };
  const route = routeMap[type.toLowerCase()] || `#/home`;
  return `<a href="${route}" class="cross-link" title="Navigate to ${type} ${id}">
    <span>${label || id}</span>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="7" y1="17" x2="17" y2="7"/><polyline points="7 7 17 7 17 17"/></svg>
  </a>`;
}

// 10. Stepper: Multi-step flow visualization
export function renderStepper(steps, activeIndex = 0) {
  return `<div class="stepper">
    ${steps.map((st, i) => {
      let stateCls = '';
      let circleContent = i + 1;
      if (i < activeIndex) {
        stateCls = 'completed';
        circleContent = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><polyline points="20 6 9 17 4 12"/></svg>`;
      } else if (i === activeIndex) {
        stateCls = 'active';
      }
      return `<div class="step-item ${stateCls}">
        <div class="step-circle">${circleContent}</div>
        <div class="step-label">${st}</div>
      </div>`;
    }).join('')}
  </div>`;
}

// 11. RoleGate: Disables UI and shows request access if role unauthorized
export function renderRoleGate(allowedRoles, currentRole, contentHtml) {
  if (allowedRoles.includes('ALL') || allowedRoles.includes(currentRole)) {
    return contentHtml;
  }
  return `<div class="role-gate-blocked">
    <div style="font-size:24px; margin-bottom:8px;">🔒</div>
    <div style="font-weight:600; margin-bottom:4px;">Restricted Access</div>
    <div style="font-size:13px; color:var(--text-muted); margin-bottom:12px;">
      Your active role (<strong>${currentRole}</strong>) does not have authorization to view this section.
    </div>
    <button type="button" class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Access request dispatched to Administrator.', 'info')">
      Request Access
    </button>
  </div>`;
}

// 12. Skeleton loader for data tables
export function renderTableSkeleton(rows = 6, cols = 5) {
  return `<div class="table-container">
    <div class="table-toolbar">
      <div class="skeleton" style="width: 220px; height: 32px;"></div>
      <div class="skeleton" style="width: 140px; height: 32px;"></div>
    </div>
    <div style="padding: 16px;">
      ${Array(rows).fill(0).map(() => `
        <div style="display:flex; gap:16px; margin-bottom:12px;">
          ${Array(cols).fill(0).map(() => `<div class="skeleton" style="flex:1; height: 24px;"></div>`).join('')}
        </div>
      `).join('')}
    </div>
  </div>`;
}
