/**
 * Module M5: Loan and Settlement Management
 * Routes: /loans, /loans/:id, /loans/ledger, /loans/settlements, /loans/release
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderAsOfStamp, renderTableSkeleton } from '../components/shared.js';
import { formatINR, formatDate } from '../formatters.js';

export async function renderLoansView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Records</span>
        <span class="breadcrumb-separator">/</span>
        <span>Loans & Settlements</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Credit Facilities & Settlement Management</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Consolidated borrowings, claims reconciliation, DRT/NCLT proceedings, and security release workflows.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/loans/release" class="btn btn-secondary btn-sm">
            🔓 Security Release Protocol
          </a>
          <a href="#/loans/settlements" class="btn btn-secondary btn-sm">
            Settlement Tracker (Kanban)
          </a>
          <a href="#/loans/ledger" class="btn btn-primary btn-sm">
            📊 Exposure Ledger & Audit
          </a>
        </div>
      </div>
    </div>

    <!-- Lender Exposure Summary Strip -->
    <div id="lenders-strip" style="margin-bottom:24px;"></div>

    <!-- Loan Facilities Table -->
    <div id="loans-table-container">
      ${renderTableSkeleton(6, 7)}
    </div>
  `;

  const [loans, lenders] = await Promise.all([
    api.getLoans(),
    api.getLenders()
  ]);

  // Render Lender cards
  const strip = document.getElementById('lenders-strip');
  if (strip) {
    strip.innerHTML = `
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px;">
        ${lenders.slice(0, 4).map(len => `
          <div class="card" style="padding:16px; margin-bottom:0;">
            <div style="font-size:11px; font-weight:700; color:var(--text-tertiary); text-transform:uppercase;">${len.type}</div>
            <div style="font-size:14px; font-weight:700; margin:4px 0; color:var(--text-main);">${len.name}</div>
            <div style="font-size:18px; font-weight:700; color:var(--primary);" class="amount">${formatINR(len.claimedTotal)}</div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-top:8px;">
              <span style="font-size:11px; color:var(--text-muted);">${len.facilityCount} Facilities</span>
              ${renderStatusBadge(len.status)}
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  // Render Loan Facilities Table
  const tableTarget = document.getElementById('loans-table-container');
  if (tableTarget) {
    tableTarget.innerHTML = `
      <div class="table-container">
        <div class="table-toolbar">
          <input type="text" class="table-search-input" placeholder="Search facility ID, lender, borrower..." />
          <div class="filter-chip-group">
            <span class="filter-chip active">All Facilities (${loans.length})</span>
            <span class="filter-chip">In Recovery</span>
            <span class="filter-chip">OTS Pending</span>
            <span class="filter-chip">Standard</span>
          </div>
        </div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Facility ID</th>
              <th>Lender</th>
              <th>Borrower Entity</th>
              <th>Sanction Limit</th>
              <th>Outstanding Claim</th>
              <th>Primary Collateral</th>
              <th>Status</th>
              <th style="text-align:right;">Actions</th>
            </tr>
          </thead>
          <tbody>
            ${loans.map(l => `
              <tr onclick="window.location.hash='#/loans/${l.id}'">
                <td style="font-weight:700; color:var(--primary);">${l.id}</td>
                <td>
                  <div style="font-weight:600;">${l.lenderName}</div>
                  <div style="font-size:11px; color:var(--text-tertiary);">${l.facilityNumber}</div>
                </td>
                <td>${l.borrowerName}</td>
                <td class="amount tabular-nums" style="font-weight:600;">${formatINR(l.sanctionAmount)} ${renderSourceChip(l.sources?.[0]?.docId || 'DOC-012', 'Sanction Letter', 2)}</td>
                <td class="amount tabular-nums" style="font-weight:700; color:var(--color-danger);">${formatINR(l.outstandingClaim)} ${renderSourceChip(l.sources?.[1]?.docId || 'DOC-013', 'Claim Statement', 1)}</td>
                <td style="font-size:12px;">
                  ${l.securities?.map(s => `<div>🏞️ ${s.name} (${renderStatusBadge(s.status)})</div>`).join('') || 'None'}
                </td>
                <td>${renderStatusBadge(l.status)}</td>
                <td style="text-align:right;">
                  <a href="#/loans/${l.id}" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">Inspect →</a>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  }
}

export async function renderLoanDetailView(container, loanId) {
  const loan = await api.getLoanById(loanId);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/loans">Loans</a>
        <span class="breadcrumb-separator">/</span>
        <span>${loan.id}</span>
      </div>
      <div class="page-title-row">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h1 class="page-title">${loan.lenderName} — ${loan.facilityNumber}</h1>
            ${renderStatusBadge(loan.status)}
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Borrower: <strong>${loan.borrowerName}</strong> • Type: ${loan.type}
          </p>
        </div>
        <div class="page-actions">
          ${renderAsOfStamp(loan.asOfDate)}
        </div>
      </div>
    </div>

    <!-- Loan Sub-Tabs -->
    <div class="tabs-nav">
      <button class="tab-btn active" onclick="window.switchLoanTab('overview')">Overview & Terms</button>
      <button class="tab-btn" onclick="window.switchLoanTab('claims')">Claims & Breakup</button>
      <button class="tab-btn" onclick="window.switchLoanTab('security')">Pledged Security (${loan.securities?.length || 0})</button>
      <button class="tab-btn" onclick="window.switchLoanTab('proceedings')">Court Proceedings (${loan.proceedings?.length || 0})</button>
      <button class="tab-btn" onclick="window.switchLoanTab('settlement')">Settlement History</button>
    </div>

    <div id="loan-tab-container">
      <div class="card">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Sanction & Interest Terms</h3>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; font-size:13px;">
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Sanction Date</span>
              <span>${loan.sanctionDate}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Sanction Amount</span>
              <span class="amount" style="font-weight:700;">${formatINR(loan.sanctionAmount)} ${renderSourceChip(loan.sources?.[0]?.docId || 'DOC-012', 'Sanction Letter', 2)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Sanctioned Interest Rate</span>
              <span>${loan.interestRate}</span>
            </div>
          </div>
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Outstanding Claim Balance</span>
              <span class="amount" style="font-weight:700; color:var(--color-danger);">${formatINR(loan.outstandingClaim)} ${renderSourceChip(loan.sources?.[1]?.docId || 'DOC-013', 'Claim Statement', 1)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Guarantors</span>
              <div>${loan.guarantors?.map(g => `<div>${g.name} (${g.type})</div>`).join('') || 'None'}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  window.switchLoanTab = (tab) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    const target = document.getElementById('loan-tab-container');
    if (!target) return;

    if (tab === 'claims') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Claim Breakdown as of ${loan.asOfDate}</h3>
          <table class="data-table">
            <thead><tr><th>Component</th><th>Amount Claimed</th><th>Source Citation</th><th>Notes</th></tr></thead>
            <tbody>
              <tr><td>Principal Outstanding</td><td class="amount tabular-nums" style="font-weight:700;">${formatINR(loan.principalOutstanding)}</td><td>${renderSourceChip('DOC-013', 'NNB Demand Notice', 2)}</td><td>Principal drew against construction milestones</td></tr>
              <tr><td>Accrued Regular Interest</td><td class="amount tabular-nums">${formatINR(loan.interestOutstanding)}</td><td>${renderSourceChip('DOC-013', 'NNB Demand Notice', 2)}</td><td>Interest calculated at MCLR + 3.10%</td></tr>
              <tr><td>Penal Interest / Charges</td><td class="amount tabular-nums" style="color:var(--color-danger); font-weight:bold;">${formatINR(loan.penalInterest)}</td><td>${renderSourceChip('DOC-013', 'NNB Demand Notice', 3)}</td><td><span class="status-badge attention">Disputed Compounding</span></td></tr>
              <tr style="background:var(--bg-subtle); font-weight:bold;"><td>Total Claim</td><td class="amount tabular-nums" style="color:var(--color-danger); font-size:16px;">${formatINR(loan.outstandingClaim)}</td><td colspan="2">${renderAsOfStamp(loan.asOfDate)}</td></tr>
            </tbody>
          </table>
        </div>
      `;
    } else if (tab === 'security') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Pledged Security & Mortgages</h3>
          <table class="data-table">
            <thead><tr><th>Parcel ID</th><th>Asset Name</th><th>Mortgage Nature</th><th>Status</th><th>Action</th></tr></thead>
            <tbody>
              ${(loan.securities || []).map(s => `
                <tr>
                  <td><a href="#/land/${s.parcelId}" style="font-weight:bold;">🏞️ ${s.parcelId}</a></td>
                  <td>${s.name}</td>
                  <td>${s.mortgageType}</td>
                  <td>${renderStatusBadge(s.status)}</td>
                  <td><a href="#/loans/release" class="btn btn-secondary btn-sm">Release Security →</a></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (tab === 'proceedings') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Judicial & Recovery Proceedings</h3>
          ${(loan.proceedings || []).map(p => `
            <div style="padding:16px; border:1px solid var(--border-subtle); border-radius:8px; margin-bottom:12px; background:var(--bg-subtle);">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <div style="font-weight:700; font-size:14px;"><a href="#/matters/${p.matterId}">${p.caseNumber}</a> • ${p.forum}</div>
                <span class="status-badge attention">Next Hearing: ${formatDate(p.nextHearing)}</span>
              </div>
              <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">Current Stage: <strong>${p.stage}</strong></div>
            </div>
          `).join('') || '<p style="color:var(--text-muted);">No active judicial proceedings initiated for this facility.</p>'}
        </div>
      `;
    } else {
      renderLoanDetailView(container, loanId);
    }
  };
}

export async function renderExposureLedgerView(container) {
  const loans = await api.getLoans();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/loans">Loans</a>
        <span class="breadcrumb-separator">/</span>
        <span>Exposure Ledger</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Consolidated Exposure Ledger & Audit Reconciliation</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Lender-wise sanctioned vs claimed vs ledger balances. Mismatches highlight disputed penal interest and compounding.
          </p>
        </div>
        <div class="page-actions">
          ${renderAsOfStamp('30 Sep 2026')}
        </div>
      </div>
    </div>

    <!-- Reconciliation Discrepancy Alert Strip (Section 5 Edge Case) -->
    <div style="background:var(--color-danger-bg); border:1px solid var(--color-danger-border); padding:16px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
      <div style="display:flex; align-items:center; gap:12px;">
        <span style="font-size:24px;">🚩</span>
        <div>
          <strong style="color:var(--color-danger-text); font-size:14px;">Reconciliation Anomaly Detected: Facility LN-002 (Coastal Finance Ltd)</strong>
          <div style="font-size:12px; color:var(--color-danger-text); margin-top:2px;">
            Bank demands <strong>₹ 42.10 Cr</strong>; Company Ledger records <strong>₹ 38.60 Cr</strong>. Discrepancy of <strong>₹ 3.50 Cr</strong> represents unconstitutional penal compounding under RBI norms.
          </div>
        </div>
      </div>
      <span class="status-badge discrepancy" title="Unreconciled difference: ₹ 3.50 Cr">Does not reconcile</span>
    </div>

    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Facility ID</th>
            <th>Lender</th>
            <th>Sanctioned</th>
            <th>Bank Claim</th>
            <th>Paid to Date</th>
            <th>Company Ledger</th>
            <th>Reconciliation Status</th>
          </tr>
        </thead>
        <tbody>
          ${loans.map(l => `
            <tr>
              <td><a href="#/loans/${l.id}" style="font-weight:700;">${l.id}</a></td>
              <td><strong>${l.lenderName}</strong></td>
              <td class="amount tabular-nums">${formatINR(l.sanctionAmount)}</td>
              <td class="amount tabular-nums" style="font-weight:bold; color:var(--color-danger);">${formatINR(l.outstandingClaim)}</td>
              <td class="amount tabular-nums">${formatINR(l.totalPaid)}</td>
              <td class="amount tabular-nums">${formatINR(l.companyLedgerBalance || l.outstandingClaim)}</td>
              <td>
                ${l.reconciliationBadge ? `
                  <span class="status-badge discrepancy" title="${l.reconciliationExplanation}">
                    Does not reconcile (₹ 3.50 Cr)
                  </span>
                ` : `<span class="status-badge verified">Reconciled</span>`}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export async function renderSettlementsView(container) {
  const loans = await api.getLoans();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/loans">Loans</a>
        <span class="breadcrumb-separator">/</span>
        <span>Settlement Tracker</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">One-Time Settlement (OTS) Pipeline</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Stage-by-stage progression from Offer to No-Dues Received.
          </p>
        </div>
        <div class="page-actions">
          <span class="status-badge calculated">Calculated Ranking • Not a valuation</span>
        </div>
      </div>
    </div>

    <!-- Priority Ranking Panel: Settlements that free the most valuable assets -->
    <div class="card" style="border-left: 4px solid var(--primary); margin-bottom:24px;">
      <div style="font-weight:700; font-size:14px; margin-bottom:6px;">
        🎯 Top Settlements that Free the Most Valuable Assets
      </div>
      <div style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">
        Ranked by unencumbered asset value liberated per rupee of settlement cash outflow (Calculated metric; not a certified valuation).
      </div>
      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:12px;">
        <div style="background:var(--bg-subtle); padding:12px; border-radius:8px; border:1px solid var(--border-subtle);">
          <div style="font-weight:700; font-size:13px; color:var(--primary);">1. Apex Housing Finance (LN-003)</div>
          <div style="font-size:12px; color:var(--text-main); margin:4px 0;">Frees: <strong>Devanahalli Tech Park Parcel P-005 (30.4 acres)</strong></div>
          <div style="font-size:11px; color:var(--text-muted);">Proposed OTS: ₹ 122.00 Cr | Asset Est. Value: ₹ 240.00 Cr</div>
        </div>
        <div style="background:var(--bg-subtle); padding:12px; border-radius:8px; border:1px solid var(--border-subtle);">
          <div style="font-weight:700; font-size:13px; color:var(--primary);">2. Northern National Bank (LN-001)</div>
          <div style="font-size:12px; color:var(--text-main); margin:4px 0;">Frees: <strong>Hinjewadi Maan Land P-001 (12.5 acres) & Panvel (P-004)</strong></div>
          <div style="font-size:11px; color:var(--text-muted);">Proposed OTS: ₹ 85.00 Cr | Assets Est. Value: ₹ 230.00 Cr</div>
        </div>
      </div>
    </div>

    <!-- Settlement Kanban Board -->
    <div style="display:grid; grid-template-columns: repeat(6, 1fr); gap:12px; overflow-x:auto;">
      ${['Offer', 'Negotiation', 'Management decision', 'Agreed', 'Paid', 'No-dues received'].map(stage => {
        const stageLoans = loans.filter(l => (l.settlementStage || 'Negotiation').toLowerCase() === stage.toLowerCase());
        return `
          <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); border-radius:8px; padding:12px; min-width:200px;">
            <div style="font-size:11px; font-weight:700; text-transform:uppercase; color:var(--text-muted); margin-bottom:8px; display:flex; justify-content:space-between;">
              <span>${stage}</span>
              <span>(${stageLoans.length})</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:8px;">
              ${stageLoans.map(l => `
                <div class="card" style="padding:10px; margin-bottom:0; cursor:pointer;" onclick="window.location.hash='#/loans/${l.id}'">
                  <div style="font-weight:700; font-size:12px;">${l.id}</div>
                  <div style="font-size:11px; color:var(--text-muted);">${l.lenderName}</div>
                  <div style="font-size:12px; font-weight:600; color:var(--color-danger); margin-top:4px;">${formatINR(l.outstandingClaim)}</div>
                </div>
              `).join('') || '<div style="font-size:11px; color:var(--text-tertiary); text-align:center; padding:12px 0;">No facilities</div>'}
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

export async function renderSecurityReleaseView(container) {
  const [loans, parcels] = await Promise.all([
    api.getLoans(),
    api.getParcels()
  ]);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/loans">Loans</a>
        <span class="breadcrumb-separator">/</span>
        <span>Security Release Protocol</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Security Charge Discharge & Release</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Formal execution protocol: Upload No-Dues Certificate, select mortgaged collateral, and discharge parcel charges across the group registry.
          </p>
        </div>
      </div>
    </div>

    <!-- Stepper Flow for Security Release -->
    <div class="card" style="max-width:760px; margin:0 auto; padding:28px;">
      <div style="font-size:16px; font-weight:700; margin-bottom:16px;">Release Security on Loan Facility</div>
      
      <div class="form-group">
        <label class="form-label">1. Select Loan Facility Settled</label>
        <select id="release-loan-select" class="form-control" onchange="window.updateSecList(this.value)">
          <option value="LN-001">LN-001: Northern National Bank (Parcels P-001, P-004)</option>
          <option value="LN-002">LN-002: Coastal Finance Ltd (Parcel P-003)</option>
          <option value="LN-003">LN-003: Apex Housing Finance (Parcel P-005)</option>
        </select>
      </div>

      <div class="form-group" style="margin-top:16px;">
        <label class="form-label">2. Select Collateral Land Parcels to Release</label>
        <div id="release-parcels-checkboxes" style="background:var(--bg-subtle); padding:12px; border-radius:8px;">
          <label style="display:flex; align-items:center; gap:8px; font-size:13px; margin-bottom:8px;">
            <input type="checkbox" id="chk-p001" checked />
            <strong>P-001</strong> — Hinjewadi Maan Land (12.5 acres)
          </label>
          <label style="display:flex; align-items:center; gap:8px; font-size:13px;">
            <input type="checkbox" id="chk-p004" checked />
            <strong>P-004</strong> — Panvel Logistics Hub Land (15.0 acres)
          </label>
        </div>
      </div>

      <div class="form-group" style="margin-top:16px;">
        <label class="form-label">3. Upload Bank No-Dues Certificate (Mandatory)</label>
        <input type="file" id="no-dues-file" class="form-control" />
        <small style="color:var(--text-tertiary); font-size:11px;">Must be signed by authorized bank recovery officer with bank seal.</small>
      </div>

      <div style="margin-top:24px; padding-top:16px; border-top:1px solid var(--border-subtle); display:flex; justify-content:flex-end;">
        <button type="button" class="btn btn-primary" onclick="window.executeSecurityRelease()">
          Execute Security Discharge →
        </button>
      </div>
    </div>
  `;

  window.executeSecurityRelease = async () => {
    const loanId = document.getElementById('release-loan-select')?.value || 'LN-001';
    await api.releaseSecurity(loanId, 'P-001', 'Bank No-Dues Certificate REF/2026/8912');
    await api.releaseSecurity(loanId, 'P-004', 'Bank No-Dues Certificate REF/2026/8912');
    window.MeridianApp.showToast('Security released! Parcels P-001 & P-004 updated to Free in Land Registry.', 'success');
    window.location.hash = '#/land';
  };
}
