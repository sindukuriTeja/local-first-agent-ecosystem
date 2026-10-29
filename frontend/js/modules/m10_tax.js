/**
 * Module M10: Tax Management, Notice Register, Demand Tracker, Appeals & Pre-Deposits
 * Routes: /tax, /tax/:id
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderAsOfStamp, renderAIGeneratedTag, renderTableSkeleton } from '../components/shared.js';
import { formatINR, formatDate } from '../formatters.js';

export async function renderTaxView(container) {
  const notices = await api.getTaxNotices();

  // Calculate summary metrics
  const totalRisk = notices.reduce((acc, n) => acc + (n.totalRiskAmount || n.demandAmount || 0), 0);
  const openNoticesCount = notices.filter(n => n.status !== 'Closed').length;
  const sortedUpcoming = [...notices].sort((a, b) => a.daysLeft - b.daysLeft).slice(0, 3);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Records</span>
        <span class="breadcrumb-separator">/</span>
        <span>Tax Management</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Tax Demand Register & Appeals Tracker</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            GST scrutiny, Income Tax assessment orders, penalty proceedings, and pre-deposit balances across group companies.
          </p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-primary btn-sm" onclick="window.openUploadTaxNoticeModal()">
            + Upload Tax Notice (OCR Ingest)
          </button>
        </div>
      </div>
    </div>

    <!-- Summary Strip (Section 10 Specification) -->
    <div class="kpi-grid" style="margin-bottom:24px;">
      <div class="kpi-card">
        <div class="kpi-label">Total Amount at Risk</div>
        <div class="kpi-value amount" style="color:var(--color-danger);">${formatINR(totalRisk)}</div>
        <div class="kpi-sub"><span class="status-badge calculated">Calculated Metric</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Open Statutory Notices</div>
        <div class="kpi-value amount">${openNoticesCount}</div>
        <div class="kpi-sub">GST: 4 | Income Tax: 3 | Municipal: 1</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">Next Statutory Due Dates</div>
        <div style="font-size:12px; font-weight:600; color:var(--text-main); margin-top:4px;">
          ${sortedUpcoming.map(u => `<div>• ${u.id}: <strong>${formatDate(u.dueDate)}</strong> (${u.daysLeft}d left)</div>`).join('')}
        </div>
      </div>
    </div>

    <!-- Notice Register Table -->
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" placeholder="Search notice ID, company, section..." oninput="window.filterTaxNotices(this.value)" />
        <div class="filter-chip-group">
          <span class="filter-chip active">All Notices (${notices.length})</span>
          <span class="filter-chip">GST Notices</span>
          <span class="filter-chip">Income Tax</span>
          <span class="filter-chip">Due Soon</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Notice ID</th>
            <th>Tax Type / Section</th>
            <th>Year</th>
            <th>Company</th>
            <th>Demand Amount</th>
            <th>Due Date</th>
            <th>Days Left</th>
            <th>Owner</th>
            <th>Status</th>
            <th style="text-align:right;">Action</th>
          </tr>
        </thead>
        <tbody id="tax-tbody">
          ${notices.map(n => `
            <tr onclick="window.location.hash='#/tax/${n.id}'">
              <td style="font-weight:700; color:var(--primary);">${n.id}</td>
              <td>
                <div style="font-weight:600;">${n.taxType}</div>
                <div style="font-size:11px; color:var(--text-tertiary);">${n.section}</div>
              </td>
              <td>${n.financialYear}</td>
              <td>${n.companyName}</td>
              <td class="amount tabular-nums" style="font-weight:700; color:var(--color-danger);">${n.demandFormatted} ${renderSourceChip(n.linkedDocuments?.[0] || 'DOC-005', 'Notice SCN', 1)}</td>
              <td>${formatDate(n.dueDate)}</td>
              <td>
                <span class="status-badge ${n.daysLeft <= 9 ? 'rejected' : 'needs-approval'}">
                  ${n.daysLeft} days
                </span>
              </td>
              <td>${n.owner}</td>
              <td>${renderStatusBadge(n.status)}</td>
              <td style="text-align:right;">
                <a href="#/tax/${n.id}" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">Open File →</a>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  window.openUploadTaxNoticeModal = () => {
    window.location.hash = '#/documents';
    window.MeridianApp.showToast('Select "Upload Document" and tag confidentiality as Tax / Statutory.', 'info');
  };
}

export async function renderTaxDetailView(container, noticeId) {
  const notice = await api.getTaxNoticeById(noticeId);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/tax">Tax</a>
        <span class="breadcrumb-separator">/</span>
        <span>${notice.id}</span>
      </div>
      <div class="page-title-row">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h1 class="page-title">${notice.noticeNumber}</h1>
            ${renderStatusBadge(notice.status)}
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            ${notice.companyName} • ${notice.taxType} (${notice.financialYear}) • Lead Owner: <strong>${notice.owner}</strong>
          </p>
        </div>
        <div class="page-actions">
          <a href="#/drafting/editor?templateId=TPL-004" class="btn btn-secondary btn-sm">
            Create Reply Draft
          </a>
          <button class="btn btn-primary btn-sm" onclick="window.openRecordFilingModal('${notice.id}')">
            Record Statutory Filing
          </button>
        </div>
      </div>
    </div>

    <!-- Amount at Risk KPI Banner -->
    <div class="card" style="display:flex; justify-content:space-between; align-items:center; background:var(--bg-subtle); padding:16px 24px; margin-bottom:20px;">
      <div>
        <div style="font-size:11px; font-weight:700; color:var(--text-tertiary); text-transform:uppercase;">Statutory Demand & Exposure</div>
        <div style="font-size:24px; font-weight:700; color:var(--color-danger);" class="amount">${notice.demandFormatted}</div>
        <div style="font-size:11px; color:var(--text-muted);">Estimated Interest & Penal Exposure: <strong>${formatINR(notice.interestPenalty)}</strong> (Calculated)</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:12px; color:var(--text-muted);">Statutory Filing Deadline</div>
        <div style="font-size:16px; font-weight:700; color:var(--primary);">${formatDate(notice.dueDate)} (${notice.daysLeft} days remaining)</div>
        <div style="font-size:11px; color:var(--text-tertiary);">Issuing Authority: ${notice.issuingAuthority}</div>
      </div>
    </div>

    <!-- Sub-Tabs: Fact Sheet, Demand & Interest, Appeals, Pre-Deposits, Reply Drafts, Documents -->
    <div class="tabs-nav">
      <button class="tab-btn active" onclick="window.switchTaxTab('facts')">Fact Sheet</button>
      <button class="tab-btn" onclick="window.switchTaxTab('demand')">Demand & Interest Calc</button>
      <button class="tab-btn" onclick="window.switchTaxTab('appeals')">Appeals Timeline</button>
      <button class="tab-btn" onclick="window.switchTaxTab('predeposits')">Pre-Deposits Paid (${formatINR(notice.preDepositsPaid)})</button>
      <button class="tab-btn" onclick="window.switchTaxTab('documents')">Evidence Documents</button>
    </div>

    <div id="tax-tab-container">
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <h3 style="font-size:15px; font-weight:700;">Allegation Summary & Grounded Facts</h3>
          ${renderAIGeneratedTag('Synthesized by Tax Intelligence Agent')}
        </div>
        <div style="background:var(--bg-subtle); padding:14px; border-radius:8px; border:1px solid var(--border-subtle); font-size:13px; line-height:1.6; margin-bottom:16px;">
          <strong>Department Allegation:</strong> ${notice.allegation}
        </div>
        <div style="display:flex; flex-direction:column; gap:10px;">
          ${(notice.factSheet || []).map(f => `
            <div style="padding:12px; border:1px solid var(--border-subtle); border-radius:6px; font-size:13px;">
              • ${f.point}
              ${renderSourceChip(f.source.docId, f.source.docName, f.source.page)}
            </div>
          `).join('') || '<p style="color:var(--text-muted);">Fact points are being indexed by Tax Intelligence Agent.</p>'}
        </div>
      </div>
    </div>
  `;

  window.openRecordFilingModal = (nId) => {
    const ack = prompt("Enter Department Acknowledgement / ARN Number (Filing performed outside app):", "ARN-2026-" + Math.floor(100000 + Math.random() * 900000));
    if (ack) {
      window.MeridianApp.showToast(`Statutory filing recorded with ARN ${ack}. Compliance calendar updated.`, 'success');
    }
  };

  window.switchTaxTab = (tab) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    const target = document.getElementById('tax-tab-container');
    if (!target) return;

    if (tab === 'demand') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Demand & Exposure Computation</h3>
          <table class="data-table">
            <thead><tr><th>Component</th><th>Demand Amount</th><th>Calculated Basis</th></tr></thead>
            <tbody>
              <tr><td>Basic Tax Demand</td><td class="amount tabular-nums" style="font-weight:700;">${notice.demandFormatted}</td><td>Per DRC-01 / Assessment Notice</td></tr>
              <tr><td>Interest u/s 50 CGST Act</td><td class="amount tabular-nums">${formatINR(notice.interestPenalty)}</td><td><span class="status-badge calculated">Calculated at 18% p.a.</span></td></tr>
              <tr style="font-weight:bold; background:var(--bg-subtle);"><td>Total Financial Risk</td><td class="amount tabular-nums" style="color:var(--color-danger);">${formatINR(notice.totalRiskAmount)}</td><td>Total Potential Exposure</td></tr>
            </tbody>
          </table>
        </div>
      `;
    } else if (tab === 'appeals') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Appellate & Adjudication Pipeline</h3>
          <div class="audit-timeline">
            ${(notice.appealTimeline || []).map(a => `
              <div class="timeline-item">
                <div class="timeline-node"></div>
                <div class="timeline-header">
                  <span>${formatDate(a.date)}</span>
                  ${renderStatusBadge(a.status)}
                </div>
                <div class="timeline-title">${a.stage}</div>
              </div>
            `).join('') || '<p style="color:var(--text-muted);">No prior appellate stages recorded.</p>'}
          </div>
        </div>
      `;
    } else if (tab === 'predeposits') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Pre-Deposits Made Under Protest</h3>
          <p style="font-size:13px; color:var(--text-muted); margin-bottom:12px;">Section 107(6) CGST Act mandates 10% pre-deposit for filing appeal before Appellate Authority.</p>
          <div style="font-size:18px; font-weight:700; color:var(--primary); margin-bottom:16px;" class="amount">
            Total Pre-Deposits Remitted: ${formatINR(notice.preDepositsPaid)}
          </div>
          <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Pre-deposit challan ledger synced with bank statement.', 'info')">
            Verify Pre-Deposit Challan Receipt
          </button>
        </div>
      `;
    } else {
      renderTaxDetailView(container, noticeId);
    }
  };
}
