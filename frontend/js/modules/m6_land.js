/**
 * Module M6: Land and Title Management, Title Chain, Encumbrances
 * Routes: /land, /land/:id, /land/encumbrances
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderAsOfStamp, renderTableSkeleton } from '../components/shared.js';
import { formatINR, formatArea, formatDate } from '../formatters.js';

let viewMode = 'table'; // 'table' | 'cards'

export async function renderLandView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Records</span>
        <span class="breadcrumb-separator">/</span>
        <span>Land and Title</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Land Holdings & Title Registry</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            164.6 acres across 8 parcels. Tracks revenue extracts, 30-year title chains, encumbrances, and RERA approvals.
          </p>
        </div>
        <div class="page-actions">
          <div class="unit-toggle-group">
            <button class="unit-toggle-btn ${viewMode === 'table' ? 'active' : ''}" onclick="window.setLandViewMode('table')">Table</button>
            <button class="unit-toggle-btn ${viewMode === 'cards' ? 'active' : ''}" onclick="window.setLandViewMode('cards')">Cards</button>
          </div>
          <a href="#/land/encumbrances" class="btn btn-secondary btn-sm">
            Encumbrance Register
          </a>
        </div>
      </div>
    </div>

    <div id="parcels-content">
      ${renderTableSkeleton(6, 7)}
    </div>
  `;

  const parcels = await api.getParcels();
  renderParcelsList(parcels);

  window.setLandViewMode = (mode) => {
    viewMode = mode;
    renderLandView(container);
  };
}

function renderParcelsList(parcels) {
  const target = document.getElementById('parcels-content');
  if (!target) return;

  if (viewMode === 'cards') {
    target.innerHTML = `
      <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap:20px;">
        ${parcels.map(p => `
          <div class="card" style="cursor:pointer; display:flex; flex-direction:column; justify-content:space-between;" onclick="window.location.hash='#/land/${p.id}'">
            <div>
              <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <span style="font-weight:700; color:var(--primary); font-size:14px;">🏞️ ${p.id}</span>
                ${renderStatusBadge(p.status)}
              </div>
              <h3 style="font-size:15px; font-weight:700; margin-bottom:4px;">${p.surveyNumber}</h3>
              <div style="font-size:12px; color:var(--text-muted); margin-bottom:8px;">${p.village}, ${p.district}</div>
              <div style="font-size:13px; font-weight:600; color:var(--text-main); margin-bottom:4px;">
                Area: ${formatArea(p.areaAcres)}
              </div>
              <div style="font-size:12px; color:var(--text-muted);">
                Owner: <strong>${p.ownerCompanyName}</strong>
              </div>
            </div>
            <div style="margin-top:16px; padding-top:12px; border-top:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
              <span class="amount" style="font-weight:700; font-size:13px;">${formatINR(p.estimatedValue)} <span style="font-size:10px; color:var(--text-tertiary); display:block;">Not a valuation</span></span>
              <span style="font-size:12px; color:var(--primary); font-weight:600;">View Title →</span>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    return;
  }

  target.innerHTML = `
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" placeholder="Search survey number, village, or company..." oninput="window.filterParcels(this.value)" />
        <div class="filter-chip-group">
          <span class="filter-chip active" onclick="window.filterParcelStatus('all')">All (${parcels.length})</span>
          <span class="filter-chip" onclick="window.filterParcelStatus('Free')">Free</span>
          <span class="filter-chip" onclick="window.filterParcelStatus('Mortgaged')">Mortgaged</span>
          <span class="filter-chip" onclick="window.filterParcelStatus('Disputed')">Disputed</span>
          <span class="filter-chip" onclick="window.filterParcelStatus('Attached')">Attached</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Parcel ID</th>
            <th>Survey Number</th>
            <th>Location</th>
            <th>Owner Company</th>
            <th>Area</th>
            <th>Estimated Value</th>
            <th>Status</th>
            <th style="text-align:right;">Actions</th>
          </tr>
        </thead>
        <tbody id="parcel-tbody">
          ${parcels.map(p => `
            <tr onclick="window.location.hash='#/land/${p.id}'">
              <td style="font-weight:700; color:var(--primary);">${p.id}</td>
              <td>
                <div style="font-weight:600;">${p.surveyNumber}</div>
                <div style="font-size:11px; color:var(--text-tertiary);">${p.rera?.registered ? 'RERA: ' + p.rera.number : 'Unregistered / Industrial'}</div>
              </td>
              <td>${p.village}, ${p.district}</td>
              <td>${p.ownerCompanyName}</td>
              <td class="tabular-nums" style="font-weight:600;">${formatArea(p.areaAcres)}</td>
              <td class="amount tabular-nums">
                ${formatINR(p.estimatedValue)}
                <div style="font-size:10px; color:var(--text-tertiary);">Not a certified valuation</div>
              </td>
              <td>${renderStatusBadge(p.status)}</td>
              <td style="text-align:right;">
                <a href="#/land/${p.id}" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">View Details →</a>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export async function renderParcelDetailView(container, parcelId) {
  const parcel = await api.getParcelById(parcelId);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/land">Land</a>
        <span class="breadcrumb-separator">/</span>
        <span>${parcel.id}</span>
      </div>
      <div class="page-title-row">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h1 class="page-title">${parcel.surveyNumber} — ${parcel.village}</h1>
            ${renderStatusBadge(parcel.status)}
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Owner: <strong>${parcel.ownerCompanyName}</strong> • Extent: ${formatArea(parcel.areaAcres)} (${parcel.areaSqFt.toLocaleString('en-IN')} sq ft)
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-secondary btn-sm" onclick="window.sendForTitleVerification('${parcel.id}')">
            Needs Verification (Send to Approvals)
          </button>
          ${renderAsOfStamp(parcel.asOfDate)}
        </div>
      </div>
    </div>

    <!-- Parcel View Tabs: Key Facts, Title Chain, Encumbrances, Approvals, Linked, Map -->
    <div class="tabs-nav">
      <button class="tab-btn active" onclick="window.switchParcelTab('facts')">Key Facts</button>
      <button class="tab-btn" onclick="window.switchParcelTab('title')">Title Chain (30 Years)</button>
      <button class="tab-btn" onclick="window.switchParcelTab('encumbrances')">Encumbrances & EC</button>
      <button class="tab-btn" onclick="window.switchParcelTab('approvals')">RERA & Approvals</button>
      <button class="tab-btn" onclick="window.switchParcelTab('map')">Map & Boundary</button>
    </div>

    <div id="parcel-tab-container">
      <div class="card">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Authoritative Land Records</h3>
        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px; font-size:13px;">
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Survey Number</span>
              <span><strong>${parcel.surveyNumber}</strong> ${renderSourceChip(parcel.sources?.[0]?.docId || 'DOC-027', 'Conveyance Deed', 1)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Village & Taluka</span>
              <span>${parcel.village}, ${parcel.taluka}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">District & State</span>
              <span>${parcel.district}</span>
            </div>
          </div>
          <div style="display:flex; flex-direction:column; gap:12px;">
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Total Extent</span>
              <span>${formatArea(parcel.areaAcres)} ${renderSourceChip(parcel.sources?.[1]?.docId || 'DOC-028', 'NA Order', 2)}</span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Estimated Holding Value</span>
              <span class="amount" style="font-weight:700;">${formatINR(parcel.estimatedValue)} <span style="font-size:10px; color:var(--text-tertiary); display:block;">Not a certified valuation</span></span>
            </div>
            <div style="display:flex; justify-content:space-between; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
              <span style="color:var(--text-muted);">Title Status</span>
              <span>${renderStatusBadge(parcel.verificationStatus || 'Verified')}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  `;

  window.sendForTitleVerification = (pId) => {
    window.MeridianApp.showToast(`Title chain for ${pId} routed to Approvals Inbox for review.`, 'info');
  };

  window.switchParcelTab = (tab) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    const target = document.getElementById('parcel-tab-container');
    if (!target) return;

    if (tab === 'title') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Chronological 30-Year Title Chain</h3>
          <div class="audit-timeline">
            ${(parcel.titleChain || []).map(tc => `
              <div class="timeline-item">
                <div class="timeline-node"></div>
                <div class="timeline-header">
                  <span>Year: <strong>${tc.year}</strong></span>
                  <span>${renderSourceChip(tc.sourceDocId, tc.document, 1)}</span>
                </div>
                <div class="timeline-title">${tc.owner}</div>
                <div class="timeline-desc">Instrument: ${tc.document}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else if (tab === 'encumbrances') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Encumbrances & Sub-Registrar Searches</h3>
          <table class="data-table">
            <thead><tr><th>Encumbrance Type</th><th>Party / Institution</th><th>Claim Amount</th><th>Creation Date</th><th>EC Reference</th><th>Status</th></tr></thead>
            <tbody>
              ${(parcel.encumbrances || []).map(e => `
                <tr>
                  <td><strong>${e.type}</strong></td>
                  <td>${e.party}</td>
                  <td class="amount tabular-nums">${e.amount ? formatINR(e.amount) : 'Disputed Claim'}</td>
                  <td>${formatDate(e.date)}</td>
                  <td style="font-family:var(--font-mono); font-size:11px;">${e.ecReference || '—'}</td>
                  <td>${renderStatusBadge(e.status)}</td>
                </tr>
              `).join('') || '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No encumbrances found. Property is clear and marketable.</td></tr>'}
            </tbody>
          </table>
        </div>
      `;
    } else if (tab === 'approvals') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">RERA & Regulatory Approvals</h3>
          <div style="margin-bottom:16px;">
            <strong>RERA Registration:</strong> ${parcel.rera?.registered ? `<span class="status-badge verified">${parcel.rera.number} (Valid till ${parcel.rera.expiryDate})</span>` : `<span class="status-badge attention">${parcel.rera?.status || 'N/A'}</span>`}
          </div>
          <table class="data-table">
            <thead><tr><th>Approval Type</th><th>Issuing Authority</th><th>Sanction Order</th><th>Date</th><th>Status</th></tr></thead>
            <tbody>
              ${(parcel.approvals || []).map(a => `
                <tr>
                  <td>${a.type}</td>
                  <td>${a.authority}</td>
                  <td style="font-family:var(--font-mono); font-size:12px;">${a.number}</td>
                  <td>${formatDate(a.date)}</td>
                  <td>${renderStatusBadge(a.status)}</td>
                </tr>
              `).join('') || '<tr><td colspan="5">No additional statutory sanctions filed.</td></tr>'}
            </tbody>
          </table>
        </div>
      `;
    } else if (tab === 'map') {
      // Map tab rule: "A Map tab appears only if real coordinates exist; otherwise show No boundary data available."
      if (!parcel.coordinates) {
        target.innerHTML = `
          <div class="card" style="text-align:center; padding:40px;">
            <div style="font-size:32px; margin-bottom:8px;">🗺️</div>
            <div style="font-size:16px; font-weight:700; color:var(--text-main);">No boundary data available</div>
            <p style="font-size:13px; color:var(--text-muted); margin-top:4px;">
              GIS boundaries or geo-coordinates have not been recorded for Parcel ${parcel.id} (${parcel.surveyNumber}).
            </p>
          </div>
        `;
      } else {
        target.innerHTML = `
          <div class="card">
            <div style="display:flex; justify-content:space-between; margin-bottom:12px;">
              <h3 style="font-size:15px; font-weight:700;">GIS Boundary Map Preview</h3>
              <span style="font-size:12px; color:var(--text-muted);">Lat: ${parcel.coordinates.lat}, Lng: ${parcel.coordinates.lng}</span>
            </div>
            <div style="height:360px; background:#1E293B; border-radius:8px; display:flex; align-items:center; justify-content:center; color:#94A3B8; position:relative; overflow:hidden;">
              <div style="position:absolute; inset:0; opacity:0.3; background:radial-gradient(#4F46E5 2px, transparent 2px); background-size:30px 30px;"></div>
              <div style="text-align:center; z-index:2;">
                <div style="font-size:36px; margin-bottom:8px;">📍</div>
                <div style="font-size:16px; font-weight:700; color:#fff;">${parcel.surveyNumber} Geo-Fence</div>
                <div style="font-size:12px; color:#CBD5E1; margin-top:4px;">Cadastral Survey Map Layer: Multi-Point Polygon (${parcel.areaAcres} Acres)</div>
              </div>
            </div>
          </div>
        `;
      }
    } else {
      renderParcelDetailView(container, parcelId);
    }
  };
}

export async function renderEncumbranceRegisterView(container) {
  const parcels = await api.getParcels();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/land">Land</a>
        <span class="breadcrumb-separator">/</span>
        <span>Encumbrance Register</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Consolidated Encumbrance Register</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Group-wide register of all mortgages, attachments, disputes, and EC references.
          </p>
        </div>
      </div>
    </div>

    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Parcel</th>
            <th>Owner Company</th>
            <th>Encumbrance Type</th>
            <th>Claimant / Charge Holder</th>
            <th>Amount</th>
            <th>Creation Date</th>
            <th>EC Reference</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${parcels.flatMap(p => (p.encumbrances || []).map(e => `
            <tr>
              <td><a href="#/land/${p.id}" style="font-weight:700;">${p.id} (${p.surveyNumber})</a></td>
              <td>${p.ownerCompanyName}</td>
              <td><strong>${e.type}</strong></td>
              <td>${e.party}</td>
              <td class="amount tabular-nums">${e.amount ? formatINR(e.amount) : 'Suit Claim'}</td>
              <td>${formatDate(e.date)}</td>
              <td style="font-family:var(--font-mono); font-size:11px;">${e.ecReference || '—'}</td>
              <td>${renderStatusBadge(e.status)}</td>
            </tr>
          `)).join('')}
        </tbody>
      </table>
    </div>
  `;
}
