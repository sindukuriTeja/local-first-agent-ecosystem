/**
 * Module M4: Company Management, Profile, Group Tree, Filing Tracker
 * Routes: /companies, /companies/:id, /companies/tree, /companies/filings
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderTableSkeleton, renderAsOfStamp } from '../components/shared.js';
import { formatINR, formatDate } from '../formatters.js';

export async function renderCompaniesView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Records</span>
        <span class="breadcrumb-separator">/</span>
        <span>Companies</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Company Management</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Group legal entities, parent-subsidiary hierarchy, directorships, shareholding, and ROC compliance.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/companies/filings" class="btn btn-secondary btn-sm">
            Filing Tracker (1 Overdue)
          </a>
          <a href="#/companies/tree" class="btn btn-secondary btn-sm">
            🌳 Interactive Group Tree
          </a>
          <button type="button" class="btn btn-secondary btn-sm" onclick="window.downloadImportTemplate()">
            Download Template
          </button>
          <button type="button" class="btn btn-primary btn-sm" onclick="window.openBulkImportModal()">
            Bulk Import Companies
          </button>
        </div>
      </div>
    </div>

    <!-- Bulk Import Modal Container -->
    <div id="bulk-import-container" style="display:none; margin-bottom: 24px;">
      <div class="card" style="border: 2px dashed var(--primary); padding: 20px;">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:4px;">Bulk Import Companies & LLPs</h3>
        <p style="font-size:12px; color:var(--text-muted); margin-bottom:12px;">Upload CSV with columns: Name, CIN, Type, Parent, Authorized Capital, Paid-up Capital</p>
        <div style="display:flex; gap:12px; align-items:center;">
          <input type="file" id="bulk-csv-input" class="form-control" style="max-width:320px;" />
          <button type="button" class="btn btn-primary btn-sm" onclick="window.previewBulkUpload()">Preview & Validate</button>
          <button type="button" class="btn btn-secondary btn-sm" onclick="document.getElementById('bulk-import-container').style.display='none'">Cancel</button>
        </div>
        <div id="bulk-preview-table" style="margin-top:16px;"></div>
      </div>
    </div>

    <div id="companies-list-content">
      ${renderTableSkeleton(8, 7)}
    </div>
  `;

  const companies = await api.getCompanies();
  renderCompaniesTable(companies);

  window.downloadImportTemplate = () => {
    window.MeridianApp.showToast('Downloaded Meridian_Group_Company_Import_Template.csv', 'info');
  };

  window.openBulkImportModal = () => {
    const el = document.getElementById('bulk-import-container');
    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
  };

  window.previewBulkUpload = () => {
    const target = document.getElementById('bulk-preview-table');
    if (!target) return;
    target.innerHTML = `
      <div style="background:var(--bg-subtle); padding:12px; border-radius:6px; font-size:12px;">
        <div style="font-weight:600; color:var(--color-success-text); margin-bottom:4px;">✓ 3 Valid Rows Identified | 1 Row with Formatting Warning</div>
        <table class="data-table" style="background:#fff; margin-top:8px;">
          <thead><tr><th>Entity Name</th><th>CIN</th><th>Type</th><th>Validation</th></tr></thead>
          <tbody>
            <tr><td>Meridian Logistics Phase 2 Pvt Ltd</td><td>U70102MH2025PTC112233</td><td>Subsidiary</td><td><span class="status-badge verified">Valid</span></td></tr>
            <tr><td>Westcoast Warehousing LLP</td><td>LLPIN: AAD-1029</td><td>JV</td><td><span class="status-badge attention">Warning: Missing MOA</span></td></tr>
          </tbody>
        </table>
      </div>
    `;
  };
}

function renderCompaniesTable(companies) {
  const target = document.getElementById('companies-list-content');
  if (!target) return;

  target.innerHTML = `
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" placeholder="Search company name or CIN..." oninput="window.filterCompanyList(this.value)" />
        <div class="filter-chip-group">
          <span class="filter-chip active" onclick="window.filterCompanyType('all')">All Entities (${companies.length})</span>
          <span class="filter-chip" onclick="window.filterCompanyType('Parent')">Parent</span>
          <span class="filter-chip" onclick="window.filterCompanyType('Subsidiary')">Subsidiaries</span>
          <span class="filter-chip" onclick="window.filterCompanyType('JV')">Joint Ventures</span>
          <span class="filter-chip" onclick="window.filterCompanyType('Associate')">Associates</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Company Name</th>
            <th>CIN / LLPIN</th>
            <th>Type</th>
            <th>Paid-up Capital</th>
            <th>Next Filing Due</th>
            <th>Compliance Status</th>
            <th style="text-align:right;">Profile</th>
          </tr>
        </thead>
        <tbody id="company-tbody">
          ${companies.map(c => `
            <tr onclick="window.location.hash='#/companies/${c.id}'">
              <td>
                <div style="font-weight:700; color:var(--text-main);">${c.name}</div>
                <div style="font-size:11px; color:var(--text-tertiary);">Inc: ${c.incorporationDate} • Directors: ${c.directors?.length || 0}</div>
              </td>
              <td><span style="font-family:var(--font-mono); font-size:12px;">${c.cin}</span> ${renderSourceChip(c.sources?.[0]?.docId || 'DOC-001', 'ROC Cert', 1)}</td>
              <td><span class="status-badge calculated">${c.type}</span></td>
              <td class="amount tabular-nums" style="font-weight:600;">${formatINR(c.paidUpCapital)}</td>
              <td style="font-size:12px; color:var(--text-muted);">${c.nextFilingDue}</td>
              <td>${renderStatusBadge(c.complianceStatus)}</td>
              <td style="text-align:right;">
                <a href="#/companies/${c.id}" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">View Full Profile →</a>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export async function renderCompanyDetailView(container, companyId) {
  const company = await api.getCompanyById(companyId);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/companies">Companies</a>
        <span class="breadcrumb-separator">/</span>
        <span>${company.name}</span>
      </div>
      <div class="page-title-row">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h1 class="page-title">${company.name}</h1>
            ${renderStatusBadge(company.complianceStatus)}
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            ${company.cin} • Registered Office: ${company.registeredOffice} ${renderSourceChip(company.sources?.[1]?.docId || 'DOC-002', 'Form INC-22', 2)}
          </p>
        </div>
        <div class="page-actions">
          ${renderAsOfStamp('28 Oct 2026')}
        </div>
      </div>
    </div>

    <!-- Company Profile Sub-Tabs -->
    <div class="tabs-nav">
      <button class="tab-btn active" onclick="window.switchCompTab('overview')">Overview</button>
      <button class="tab-btn" onclick="window.switchCompTab('directors')">Directors & KMP (${company.directors?.length || 0})</button>
      <button class="tab-btn" onclick="window.switchCompTab('shareholding')">Shareholding Pattern</button>
      <button class="tab-btn" onclick="window.switchCompTab('filings')">Filings & Exceptions</button>
      <button class="tab-btn" onclick="window.switchCompTab('linked')">Linked Assets & Debts</button>
    </div>

    <div id="company-tab-container">
      <!-- Default: Overview Tab -->
      <div class="card">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Statutory Overview</h3>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; font-size:13px;">
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">CIN / Registration</span>
              <span><strong>${company.cin}</strong> ${renderSourceChip(company.sources?.[0]?.docId || 'DOC-001', 'Certificate', 1)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Entity Category</span>
              <span>${company.type}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Incorporation Date</span>
              <span>${company.incorporationDate}</span>
            </div>
          </div>
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Authorized Capital</span>
              <span class="amount" style="font-weight:600;">${formatINR(company.authorizedCapital)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Paid-up Capital</span>
              <span class="amount" style="font-weight:700;">${formatINR(company.paidUpCapital)} ${renderSourceChip('DOC-003', 'MGT-7 Return', 4)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Next Statutory Filing Due</span>
              <span style="color:var(--primary); font-weight:600;">${company.nextFilingDue}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  window.switchCompTab = (tab) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    const target = document.getElementById('company-tab-container');
    if (!target) return;

    if (tab === 'directors') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Directors & Key Managerial Personnel</h3>
          <table class="data-table">
            <thead><tr><th>DIN</th><th>Name</th><th>Designation</th><th>Appointed Date</th><th>Status</th></tr></thead>
            <tbody>
              ${(company.directors || []).map(d => `
                <tr>
                  <td style="font-family:var(--font-mono);">${d.din}</td>
                  <td><strong>${d.name}</strong></td>
                  <td>${d.designation}</td>
                  <td>${d.appointedDate}</td>
                  <td>${renderStatusBadge(d.status)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (tab === 'shareholding') {
      target.innerHTML = `
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <h3 style="font-size:15px; font-weight:700;">Shareholding Pattern</h3>
            <div style="font-size:12px; color:var(--text-muted);">As-on-date: <input type="date" value="2026-09-30" style="padding:2px 8px; border:1px solid var(--border-subtle); border-radius:4px;" /></div>
          </div>
          <table class="data-table">
            <thead><tr><th>Shareholder / Promoter</th><th>Category</th><th>Number of Shares</th><th>Holding Percentage</th></tr></thead>
            <tbody>
              ${(company.shareholding || []).map(sh => `
                <tr>
                  <td><strong>${sh.holder}</strong></td>
                  <td>${sh.category}</td>
                  <td class="tabular-nums">${sh.shares.toLocaleString('en-IN')}</td>
                  <td class="tabular-nums" style="font-weight:700; color:var(--primary);">${sh.percentage}%</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else if (tab === 'filings') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">ROC Compliance & Annual Returns</h3>
          <p style="font-size:13px; color:var(--text-muted); margin-bottom:12px;">Tracked against MCA portal filings AOC-4, MGT-7, and DIR-12.</p>
          <a href="#/companies/filings" class="btn btn-secondary btn-sm">Open Comprehensive Filing Tracker →</a>
        </div>
      `;
    } else if (tab === 'linked') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Cross-Linked Portfolio Assets</h3>
          <div style="display:flex; flex-direction:column; gap:12px; font-size:13px;">
            <div><strong>Linked Credit Facilities:</strong> ${(company.linkedLoans || []).map(l => `<a href="#/loans/${l}" style="margin-left:8px;">💳 ${l}</a>`).join(', ') || 'None'}</div>
            <div><strong>Registered Land Parcels:</strong> ${(company.linkedParcels || []).map(p => `<a href="#/land/${p}" style="margin-left:8px;">🏞️ ${p}</a>`).join(', ') || 'None'}</div>
            <div><strong>Active Litigation Matters:</strong> ${(company.linkedMatters || []).map(m => `<a href="#/matters/${m}" style="margin-left:8px;">⚖️ ${m}</a>`).join(', ') || 'None'}</div>
          </div>
        </div>
      `;
    } else {
      renderCompanyDetailView(container, companyId);
    }
  };
}

export async function renderGroupTreeView(container) {
  const companies = await api.getCompanies();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/companies">Companies</a>
        <span class="breadcrumb-separator">/</span>
        <span>Interactive Group Tree</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Meridian Infra Group — Entity Architecture</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Interactive corporate org chart showing parent, subsidiaries, joint ventures, and associates with zoom, pan, and exception filters.
          </p>
        </div>
        <div class="page-actions">
          <label style="font-size:12px; display:flex; align-items:center; gap:6px; cursor:pointer;">
            <input type="checkbox" id="tree-filter-exceptions" onchange="window.toggleTreeExceptions(this.checked)" />
            Show only entities with compliance exceptions
          </label>
        </div>
      </div>
    </div>

    <!-- Interactive Org Chart Card -->
    <div class="card" style="min-height:500px; background:radial-gradient(#E2E8F0 1px, transparent 1px); background-size: 20px 20px; position:relative; overflow:auto; padding:40px; text-align:center;">
      <!-- Root Node (Parent) -->
      <div style="display:inline-block; margin-bottom:40px;">
        <div class="card" style="display:inline-block; border:2px solid var(--primary); padding:16px 24px; box-shadow:var(--shadow-md); cursor:pointer; text-align:left;" onclick="window.MeridianApp.openQuickView('company', { id:'COMP-001', name:'Meridian Infra Holdings Ltd', type:'Parent' })">
          <div style="font-size:10px; font-weight:bold; color:var(--primary); text-transform:uppercase;">Parent Company (100% Core)</div>
          <div style="font-size:15px; font-weight:700; color:var(--text-main);">Meridian Infra Holdings Ltd</div>
          <div style="font-size:11px; color:var(--text-muted);">CIN: U45200MH2010PLC201948</div>
          <div style="margin-top:6px;">${renderStatusBadge('Compliant')}</div>
        </div>
      </div>

      <div style="width:2px; height:30px; background:var(--border-strong); margin:-30px auto 30px;"></div>

      <!-- Child Branches Grid -->
      <div style="display:flex; justify-content:center; gap:20px; flex-wrap:wrap;">
        <!-- Subsidiary 1 -->
        <div class="card tree-node" data-exception="false" style="width:240px; border-top:4px solid #16A34A; padding:14px; text-align:left; cursor:pointer;" onclick="window.location.hash='#/companies/COMP-002'">
          <div style="font-size:10px; font-weight:bold; color:#16A34A;">SUBSIDIARY (99%)</div>
          <div style="font-weight:700; font-size:13px; margin:4px 0;">Meridian Realty Pvt Ltd</div>
          <div style="font-size:11px; color:var(--text-muted);">Holds Hinjewadi Land (P-001)</div>
          <div style="margin-top:8px;">${renderStatusBadge('Attention Required')}</div>
        </div>

        <!-- Subsidiary 2 -->
        <div class="card tree-node" data-exception="false" style="width:240px; border-top:4px solid #16A34A; padding:14px; text-align:left; cursor:pointer;" onclick="window.location.hash='#/companies/COMP-003'">
          <div style="font-size:10px; font-weight:bold; color:#16A34A;">SUBSIDIARY (100%)</div>
          <div style="font-weight:700; font-size:13px; margin:4px 0;">Meridian Estates Pvt Ltd</div>
          <div style="font-size:11px; color:var(--text-muted);">Holds Whitefield Land (P-002)</div>
          <div style="margin-top:8px;">${renderStatusBadge('Compliant')}</div>
        </div>

        <!-- JV 1 (Exception: Overdue Filing) -->
        <div class="card tree-node" data-exception="true" style="width:240px; border-top:4px solid #DC2626; padding:14px; text-align:left; cursor:pointer; background:var(--color-danger-bg);" onclick="window.location.hash='#/companies/COMP-004'">
          <div style="font-size:10px; font-weight:bold; color:#DC2626;">JOINT VENTURE (50%) ⚠️</div>
          <div style="font-weight:700; font-size:13px; margin:4px 0; color:#B91C1C;">Meridian Projects LLP</div>
          <div style="font-size:11px; color:var(--color-danger-text);">Overdue Form 8 Solvency (14 days)</div>
          <div style="margin-top:8px;">${renderStatusBadge('Overdue Filing')}</div>
        </div>

        <!-- Associate 1 -->
        <div class="card tree-node" data-exception="true" style="width:240px; border-top:4px solid #D97706; padding:14px; text-align:left; cursor:pointer;" onclick="window.location.hash='#/companies/COMP-005'">
          <div style="font-size:10px; font-weight:bold; color:#D97706;">ASSOCIATE (33%)</div>
          <div style="font-weight:700; font-size:13px; margin:4px 0;">Sunrise Developers Pvt Ltd</div>
          <div style="font-size:11px; color:var(--text-muted);">Gachibowli Title Dispute (P-003)</div>
          <div style="margin-top:8px;">${renderStatusBadge('Under Litigation')}</div>
        </div>
      </div>
    </div>
  `;

  window.toggleTreeExceptions = (showOnlyExceptions) => {
    document.querySelectorAll('.tree-node').forEach(node => {
      if (showOnlyExceptions && node.dataset.exception !== 'true') {
        node.style.opacity = '0.2';
      } else {
        node.style.opacity = '1';
      }
    });
  };
}

export async function renderFilingTrackerView(container) {
  const filings = await api.getFilings();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/companies">Companies</a>
        <span class="breadcrumb-separator">/</span>
        <span>Filing Tracker</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Statutory Filing Tracker & Exceptions</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            MCA21 filing compliance, Form AOC-4, MGT-7, DIR-12, SRN tracking and evidence attachment.
          </p>
        </div>
      </div>
    </div>

    <!-- Overdue Exceptions Alert Strip (Section 5 Edge Case) -->
    <div style="background:var(--color-danger-bg); border:1px solid var(--color-danger-border); padding:14px 18px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
      <div style="display:flex; align-items:center; gap:10px;">
        <span style="font-size:20px;">⚠️</span>
        <div>
          <strong style="color:var(--color-danger-text); font-size:13px;">Critical Filing Exception: Form 8 Overdue by 14 Days</strong>
          <div style="font-size:12px; color:var(--color-danger-text);">Meridian Projects LLP statutory solvency statement was due on 14 Oct 2026. Delay penalty accruing daily.</div>
        </div>
      </div>
      <button class="btn btn-danger btn-sm" onclick="window.openMarkFiledModal('FIL-004')">
        Resolve & Record Filing
      </button>
    </div>

    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Company</th>
            <th>Form Type</th>
            <th>Financial Year</th>
            <th>Due Date</th>
            <th>SRN / Receipt</th>
            <th>Payment</th>
            <th>Status</th>
            <th style="text-align:right;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${filings.map(f => `
            <tr>
              <td><strong>${f.companyName}</strong></td>
              <td>${f.form}</td>
              <td>${f.financialYear}</td>
              <td style="font-size:12px; color:var(--text-muted);">${formatDate(f.dueDate)}</td>
              <td style="font-family:var(--font-mono); font-size:11px;">${f.srn || '—'}</td>
              <td>${f.paymentStatus === 'Paid' ? '<span style="color:var(--color-success); font-weight:600;">Paid</span>' : '<span style="color:var(--color-danger); font-weight:600;">Unpaid</span>'}</td>
              <td>${renderStatusBadge(f.status)}</td>
              <td style="text-align:right;">
                ${f.status !== 'Filed' ? `<button class="btn btn-secondary btn-sm" onclick="window.openMarkFiledModal('${f.id}')">Mark Filed</button>` : `<span style="font-size:11px; color:var(--color-success-text); font-weight:bold;">✓ Compliant</span>`}
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  window.openMarkFiledModal = (filingId) => {
    const srn = prompt("Enter MCA Service Request Number (SRN) / Challan Ref:", "F" + Math.floor(10000000 + Math.random() * 90000000));
    if (srn) {
      api.markFilingCompleted(filingId, { srn, ack: 'MCA-ACK-' + Date.now().toString().slice(-4) });
      window.MeridianApp.showToast(`Form ${filingId} recorded as filed with SRN ${srn}.`, 'success');
      renderFilingTrackerView(container);
    }
  };
}
