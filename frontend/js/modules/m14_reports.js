/**
 * Module M14: Reports and Dashboards, Board View, Debt, Land, Legal & Secretarial Dashboards, Report Builder
 * Routes: /reports, /reports/builder
 */
import { api } from '../services/api.js';
import { renderStatusBadge, renderAsOfStamp, renderSourceChip, renderAIGeneratedTag } from '../components/shared.js';
import { formatINR, formatArea, formatDate } from '../formatters.js';

let activeDashboardTab = 'board'; // 'board' | 'debt' | 'land' | 'legal' | 'secretarial' | 'scheduled'

export async function renderReportsView(container) {
  const [loans, parcels, matters, tax, filings, reports] = await Promise.all([
    api.getLoans(),
    api.getParcels(),
    api.getMatters(),
    api.getTaxNotices(),
    api.getFilings(),
    api.getReports()
  ]);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Insights</span>
        <span class="breadcrumb-separator">/</span>
        <span>Reports & Dashboards</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Executive Analytics & Board Reporting</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Consolidated portfolio metrics with clickable drill-down from board KPIs directly to source document citations.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/reports/builder" class="btn btn-primary btn-sm">
            + Custom Report Builder
          </a>
        </div>
      </div>
    </div>

    <!-- Dashboard Sub-Tabs -->
    <div class="tabs-nav">
      <button class="tab-btn ${activeDashboardTab === 'board' ? 'active' : ''}" onclick="window.setDashTab('board')">Board View (Executive)</button>
      <button class="tab-btn ${activeDashboardTab === 'debt' ? 'active' : ''}" onclick="window.setDashTab('debt')">Debt & Exposure</button>
      <button class="tab-btn ${activeDashboardTab === 'land' ? 'active' : ''}" onclick="window.setDashTab('land')">Land & Title Portfolio</button>
      <button class="tab-btn ${activeDashboardTab === 'legal' ? 'active' : ''}" onclick="window.setDashTab('legal')">Litigation & Tax</button>
      <button class="tab-btn ${activeDashboardTab === 'secretarial' ? 'active' : ''}" onclick="window.setDashTab('secretarial')">Secretarial & Filings</button>
      <button class="tab-btn ${activeDashboardTab === 'scheduled' ? 'active' : ''}" onclick="window.setDashTab('scheduled')">Scheduled Reports</button>
    </div>

    <!-- Active Dashboard Body -->
    <div id="dashboard-tab-body">
      ${renderBoardView(loans, parcels, matters, tax, filings)}
    </div>
  `;

  window.setDashTab = (tab) => {
    activeDashboardTab = tab;
    const body = document.getElementById('dashboard-tab-body');
    if (!body) return;

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    if (tab === 'board') {
      body.innerHTML = renderBoardView(loans, parcels, matters, tax, filings);
      initBoardCharts();
    } else if (tab === 'debt') {
      body.innerHTML = renderDebtDashboard(loans);
    } else if (tab === 'land') {
      body.innerHTML = renderLandDashboard(parcels);
    } else if (tab === 'legal') {
      body.innerHTML = renderLegalTaxDashboard(matters, tax);
    } else if (tab === 'secretarial') {
      body.innerHTML = renderSecretarialDashboard(filings);
    } else if (tab === 'scheduled') {
      body.innerHTML = renderScheduledReportsTab(reports);
    }
  };

  // Initialize Chart.js
  setTimeout(() => initBoardCharts(), 100);
}

function renderBoardView(loans, parcels, matters, tax, filings) {
  const totalDebtClaim = loans.reduce((acc, l) => acc + (l.outstandingClaim || 0), 0);
  const freeParcels = parcels.filter(p => p.status === 'Free');
  const encumberedParcels = parcels.filter(p => p.status !== 'Free');
  const taxRisk = tax.reduce((acc, t) => acc + (t.totalRiskAmount || t.demandAmount || 0), 0);
  const overdueFilings = filings.filter(f => f.status === 'Overdue');

  return `
    <div>
      <!-- Top Board KPI Row (Every number clickable) -->
      <div class="kpi-grid">
        <div class="kpi-card" onclick="window.location.hash='#/loans/ledger'" title="Click to drill down to Exposure Ledger">
          <div class="kpi-label">
            <span>Total Debt Exposure</span>
            <span>💳</span>
          </div>
          <div class="kpi-value amount" style="color:var(--color-danger);">${formatINR(totalDebtClaim)}</div>
          <div class="kpi-sub"><span class="status-badge discrepancy">Includes ₹ 3.50 Cr Disputed</span></div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/land'" title="Click to view free assets">
          <div class="kpi-label">
            <span>Assets Free of Charge</span>
            <span>🏞️</span>
          </div>
          <div class="kpi-value tabular-nums" style="color:var(--color-success);">${freeParcels.length} Parcels</div>
          <div class="kpi-sub">${formatArea(freeParcels.reduce((a, p) => a + p.areaAcres, 0))} unencumbered</div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/land/encumbrances'" title="Click to inspect encumbrance register">
          <div class="kpi-label">
            <span>Assets Encumbered</span>
            <span>🔒</span>
          </div>
          <div class="kpi-value tabular-nums" style="color:var(--color-warning);">${encumberedParcels.length} Parcels</div>
          <div class="kpi-sub">Mortgaged or DRT Attached</div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/matters'" title="Click to open litigation docket">
          <div class="kpi-label">
            <span>Open Court Cases</span>
            <span>⚖️</span>
          </div>
          <div class="kpi-value tabular-nums">${matters.length}</div>
          <div class="kpi-sub">DRT, NCLT, High Court</div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/tax'" title="Click to open tax notice register">
          <div class="kpi-label">
            <span>Tax Demand at Risk</span>
            <span>🧾</span>
          </div>
          <div class="kpi-value amount" style="color:var(--color-danger);">${formatINR(taxRisk)}</div>
          <div class="kpi-sub"><span class="status-badge calculated">Calculated Risk</span></div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/companies/filings'" title="Click to open filing tracker">
          <div class="kpi-label">
            <span>Filings Overdue</span>
            <span>⚠️</span>
          </div>
          <div class="kpi-value tabular-nums" style="color:var(--color-danger);">${overdueFilings.length}</div>
          <div class="kpi-sub">Form 8 (14 days delay)</div>
        </div>
      </div>

      <!-- Charts Row: Exposure by Lender (Bar) & Parcels by Status (Donut) -->
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px; margin-bottom:24px;">
        <div class="card" style="margin-bottom:0;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:15px; font-weight:700;">Debt Exposure by Lender (Claim vs Sanction)</h3>
            ${renderAsOfStamp('30 Sep 2026')}
          </div>
          <div style="height:260px; position:relative;">
            <canvas id="chart-lender-exposure"></canvas>
          </div>
        </div>

        <div class="card" style="margin-bottom:0;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="font-size:15px; font-weight:700;">Land Holding Status Breakdown</h3>
            <span style="font-size:12px; color:var(--text-muted);">164.6 Total Acres</span>
          </div>
          <div style="height:260px; position:relative;">
            <canvas id="chart-parcel-status"></canvas>
          </div>
        </div>
      </div>

      <!-- Actions Due in Next 30 Days Panel -->
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <h3 style="font-size:15px; font-weight:700;">Critical Actions Due in Next 30 Days</h3>
          <span style="font-size:12px; color:var(--text-tertiary);">Generated on: 28 Oct 2026</span>
        </div>
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div style="padding:12px; border-left:4px solid var(--color-danger); background:var(--bg-subtle); border-radius:4px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="color:var(--text-main);">DRT-I Mumbai Witness Cross-Examination (OA 142/2025)</strong>
              <div style="font-size:11px; color:var(--text-muted);">Due on 12 Nov 2026 • Counsel: Adv. Harish Salve Associates ${renderSourceChip('DOC-014', 'DRT Plaint', 2)}</div>
            </div>
            <a href="#/matters/M-2025-014" class="btn btn-secondary btn-sm">Open File →</a>
          </div>
          <div style="padding:12px; border-left:4px solid var(--color-warning); background:var(--bg-subtle); border-radius:4px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="color:var(--text-main);">GST Show Cause Notice DRC-01 Reply (Demand ₹ 1.84 Cr)</strong>
              <div style="font-size:11px; color:var(--text-muted);">Due in 9 days (06 Nov 2026) • Meridian Realty Pvt Ltd ${renderSourceChip('DOC-005', 'DRC-01 Notice', 2)}</div>
            </div>
            <a href="#/tax/TAX-081" class="btn btn-secondary btn-sm">Draft Reply →</a>
          </div>
        </div>
      </div>
    </div>
  `;
}

function initBoardCharts() {
  if (!window.Chart) return;

  const ctxBar = document.getElementById('chart-lender-exposure');
  if (ctxBar) {
    new Chart(ctxBar, {
      type: 'bar',
      data: {
        labels: ['Northern National', 'Coastal Finance', 'Apex Housing', 'Western Industrial', 'Bharat Commercial'],
        datasets: [
          {
            label: 'Sanctioned Limit (₹ Cr)',
            data: [85.00, 45.00, 120.00, 65.00, 50.00],
            backgroundColor: '#CBD5E1'
          },
          {
            label: 'Current Claim (₹ Cr)',
            data: [112.40, 42.10, 135.50, 78.90, 52.30],
            backgroundColor: '#4F46E5'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } }
      }
    });
  }

  const ctxDonut = document.getElementById('chart-parcel-status');
  if (ctxDonut) {
    new Chart(ctxDonut, {
      type: 'doughnut',
      data: {
        labels: ['Mortgaged (4)', 'Free (2)', 'Disputed (1)', 'Attached (1)'],
        datasets: [{
          data: [67.9, 53.2, 22.0, 15.0],
          backgroundColor: ['#F59E0B', '#10B981', '#EF4444', '#6366F1']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: 'bottom' } }
      }
    });
  }
}

function renderDebtDashboard(loans) {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Debt & Lender Exposure Pipeline</h3>
      <table class="data-table">
        <thead><tr><th>Lender</th><th>Sanction Limit</th><th>Claim Outstanding</th><th>Settlement Stage</th><th>Collateral Released</th></tr></thead>
        <tbody>
          ${loans.map(l => `
            <tr>
              <td><strong>${l.lenderName}</strong></td>
              <td class="amount tabular-nums">${formatINR(l.sanctionAmount)}</td>
              <td class="amount tabular-nums" style="font-weight:700; color:var(--color-danger);">${formatINR(l.outstandingClaim)}</td>
              <td>${renderStatusBadge(l.settlementStage || 'Negotiation')}</td>
              <td>${l.status.includes('Released') ? '<span class="status-badge verified">Released</span>' : 'Held in Mortgage'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderLandDashboard(parcels) {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Land Portfolio & Encumbrance Status</h3>
      <table class="data-table">
        <thead><tr><th>Parcel</th><th>Owner</th><th>Area</th><th>Estimated Value</th><th>Status</th><th>RERA Expiry</th></tr></thead>
        <tbody>
          ${parcels.map(p => `
            <tr>
              <td><a href="#/land/${p.id}"><strong>${p.id} (${p.surveyNumber})</strong></a></td>
              <td>${p.ownerCompanyName}</td>
              <td>${formatArea(p.areaAcres)}</td>
              <td class="amount tabular-nums">${formatINR(p.estimatedValue)}</td>
              <td>${renderStatusBadge(p.status)}</td>
              <td>${p.rera?.expiryDate || 'N/A'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderLegalTaxDashboard(matters, tax) {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Litigation Matters & Tax Claims at Risk</h3>
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
        <div>
          <h4 style="font-size:13px; font-weight:700; margin-bottom:8px;">Active Court Matters (${matters.length})</h4>
          ${matters.map(m => `<div style="padding:8px; background:var(--bg-subtle); border-radius:4px; margin-bottom:6px; font-size:12px;"><strong>${m.caseNumber}</strong> • ${m.title}</div>`).join('')}
        </div>
        <div>
          <h4 style="font-size:13px; font-weight:700; margin-bottom:8px;">Tax Scrutiny Notices (${tax.length})</h4>
          ${tax.map(t => `<div style="padding:8px; background:var(--bg-subtle); border-radius:4px; margin-bottom:6px; font-size:12px;"><strong>${t.id}</strong> • Demand: ${t.demandFormatted} (${t.daysLeft}d left)</div>`).join('')}
        </div>
      </div>
    </div>
  `;
}

function renderSecretarialDashboard(filings) {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Secretarial ROC Filings & Solvency Status</h3>
      <p style="font-size:13px; color:var(--text-muted); margin-bottom:12px;">Annual ROC filings AOC-4, MGT-7, Form 8, and statutory registers.</p>
      <a href="#/companies/filings" class="btn btn-secondary btn-sm">Open Full Filing Tracker →</a>
    </div>
  `;
}

function renderScheduledReportsTab(reports) {
  return `
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <h3 style="font-size:15px; font-weight:700;">Automated Scheduled Reports</h3>
        <button class="btn btn-primary btn-sm" onclick="window.MeridianApp.showToast('Schedule created', 'info')">+ Schedule New Report</button>
      </div>
      <table class="data-table">
        <thead><tr><th>Report Title</th><th>Frequency</th><th>Named Recipients</th><th>Next Execution</th><th>Format</th><th>Status</th></tr></thead>
        <tbody>
          ${reports.map(r => `
            <tr>
              <td><strong>${r.name}</strong></td>
              <td>${r.frequency}</td>
              <td style="font-size:12px;">${r.recipients.join(', ')}</td>
              <td>${formatDate(r.nextRun)}</td>
              <td><span class="status-badge calculated">${r.format}</span></td>
              <td>${renderStatusBadge(r.status)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export async function renderReportBuilderView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/reports">Reports</a>
        <span class="breadcrumb-separator">/</span>
        <span>Report Builder</span>
      </div>
      <h1 class="page-title">Custom Report Builder & Export</h1>
    </div>

    <div class="card" style="max-width:760px; margin:0 auto; padding:28px;">
      <div class="form-group">
        <label class="form-label">Select Report Template</label>
        <select class="form-control">
          <option>Consolidated Lender Exposure & Security Schedule</option>
          <option>30-Year Title Search & Parcel Due Diligence Package</option>
          <option>Group Litigation & Tax Contingent Liability Brief</option>
          <option>Annual Corporate Secretarial Compliance Status</option>
        </select>
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
        <div class="form-group">
          <label class="form-label">Filter Group Company</label>
          <select class="form-control">
            <option>All Group Companies</option>
            <option>Meridian Infra Holdings Ltd</option>
            <option>Meridian Realty Pvt Ltd</option>
            <option>Meridian Estates Pvt Ltd</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">As-On Benchmark Date</label>
          <input type="date" class="form-control" value="2026-09-30" />
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Intended Distribution</label>
        <label style="display:flex; align-items:center; gap:8px; font-size:13px; margin-top:6px;">
          <input type="checkbox" id="chk-external" onchange="window.toggleExternalNote(this.checked)" />
          To be shared outside the company (With Lenders, Valuers, or Court)
        </label>
        <div id="external-approval-note" style="display:none; font-size:12px; color:var(--color-warning-text); background:var(--color-warning-bg); padding:8px 12px; border-radius:6px; margin-top:8px;">
          ⚠️ <strong>Approval Gate:</strong> External exports require Manager / Board member sign-off in Approvals before distribution.
        </div>
      </div>

      <div style="margin-top:24px; padding-top:16px; border-top:1px solid var(--border-subtle); display:flex; justify-content:flex-end; gap:8px;">
        <button class="btn btn-secondary" onclick="window.exportReport('csv')">Export CSV</button>
        <button class="btn btn-secondary" onclick="window.exportReport('excel')">Export Excel</button>
        <button class="btn btn-secondary" onclick="window.exportReport('word')">Export Word</button>
        <button class="btn btn-primary" onclick="window.exportReport('pdf')">Export PDF →</button>
      </div>
    </div>
  `;

  window.toggleExternalNote = (checked) => {
    const el = document.getElementById('external-approval-note');
    if (el) el.style.display = checked ? 'block' : 'none';
  };

  window.exportReport = (fmt) => {
    const isExt = document.getElementById('chk-external')?.checked;
    if (isExt) {
      window.MeridianApp.showToast(`External report queued for Board Approval before release.`, 'warning');
    } else {
      window.MeridianApp.showToast(`Report exported successfully as ${fmt.toUpperCase()}.`, 'success');
    }
  };
}
