/**
 * Global RecordDrawer, DocumentViewer, Modal, Toast & CommandPalette Controller
 */
import { api } from '../services/api.js';
import { renderStatusBadge, renderConfidenceBar, renderSourceChip, renderConfidentialityTag } from './shared.js';
import { formatINR, formatDate } from '../formatters.js';

export class DrawerController {
  constructor() {
    this.drawerEl = null;
    this.backdropEl = null;
    this.activeTab = 'overview';
    this.currentRecord = null;
    this.currentRecordType = null;
  }

  init() {
    this.drawerEl = document.getElementById('global-drawer');
    this.backdropEl = document.getElementById('global-drawer-backdrop');

    if (this.backdropEl) {
      this.backdropEl.addEventListener('click', () => this.close());
    }

    const closeBtn = document.getElementById('drawer-close-btn');
    if (closeBtn) {
      closeBtn.addEventListener('click', () => this.close());
    }

    // Setup tab listeners
    const tabs = document.querySelectorAll('.drawer-tab');
    tabs.forEach(tab => {
      tab.addEventListener('click', (e) => {
        tabs.forEach(t => t.classList.remove('active'));
        e.target.classList.add('active');
        this.activeTab = e.target.dataset.tab;
        this.renderBody();
      });
    });
  }

  open(recordType, record) {
    this.currentRecordType = recordType;
    this.currentRecord = record;
    this.activeTab = 'overview';

    // Reset tabs
    document.querySelectorAll('.drawer-tab').forEach(t => {
      t.classList.toggle('active', t.dataset.tab === 'overview');
    });

    const titleEl = document.getElementById('drawer-title');
    const subEl = document.getElementById('drawer-subtitle');

    if (titleEl) titleEl.textContent = record.name || record.title || record.id;
    if (subEl) subEl.textContent = `${recordType.toUpperCase()} • ID: ${record.id}`;

    this.renderBody();

    this.drawerEl?.classList.add('open');
    this.backdropEl?.classList.add('open');
  }

  close() {
    this.drawerEl?.classList.remove('open');
    this.backdropEl?.classList.remove('open');
    this.currentRecord = null;
  }

  renderBody() {
    const body = document.getElementById('drawer-body');
    if (!body || !this.currentRecord) return;

    const r = this.currentRecord;
    const type = this.currentRecordType;

    if (this.activeTab === 'overview') {
      body.innerHTML = this.renderOverviewTab(type, r);
    } else if (this.activeTab === 'documents') {
      body.innerHTML = this.renderDocumentsTab(type, r);
    } else if (this.activeTab === 'linked') {
      body.innerHTML = this.renderLinkedTab(type, r);
    } else if (this.activeTab === 'history') {
      body.innerHTML = this.renderHistoryTab(type, r);
    }
  }

  renderOverviewTab(type, r) {
    let fieldsHtml = '';

    if (type === 'loan') {
      fieldsHtml = `
        <div style="display:flex; flex-direction:column; gap:16px;">
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Status</span>
            <span>${renderStatusBadge(r.status)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Lender</span>
            <span style="font-weight:600;">${r.lenderName}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Borrower</span>
            <span>${r.borrowerName}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Sanction Amount</span>
            <span class="amount" style="font-weight:700;">${formatINR(r.sanctionAmount)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Outstanding Claim</span>
            <span class="amount" style="font-weight:700; color:var(--color-danger);">${formatINR(r.outstandingClaim)} ${renderSourceChip('DOC-013', 'NNB Claim Notice', 2)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Settlement Stage</span>
            <span>${renderStatusBadge(r.settlementStage || 'Negotiation')}</span>
          </div>
        </div>
      `;
    } else if (type === 'parcel') {
      fieldsHtml = `
        <div style="display:flex; flex-direction:column; gap:16px;">
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Status</span>
            <span>${renderStatusBadge(r.status)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Survey Number</span>
            <span style="font-weight:600;">${r.surveyNumber} ${renderSourceChip(r.sources?.[0]?.docId || 'DOC-027', 'Title Deed', 1)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Owner Company</span>
            <span>${r.ownerCompanyName}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Area</span>
            <span style="font-weight:600;">${r.areaAcres} acres (${r.areaSqFt.toLocaleString('en-IN')} sq ft)</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Estimated Value</span>
            <span class="amount" style="font-weight:700;">${formatINR(r.estimatedValue)} <small style="font-size:10px; color:var(--text-tertiary); display:block;">Not a certified valuation</small></span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Verification Status</span>
            <span>${renderStatusBadge(r.verificationStatus || 'Verified')}</span>
          </div>
        </div>
      `;
    } else if (type === 'matter') {
      fieldsHtml = `
        <div style="display:flex; flex-direction:column; gap:16px;">
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Status</span>
            <span>${renderStatusBadge(r.status)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Forum</span>
            <span style="font-weight:600;">${r.forum}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Case Number</span>
            <span>${r.caseNumber}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Next Hearing</span>
            <span style="font-weight:700; color:var(--primary);">${formatDate(r.nextHearing)}</span>
          </div>
          <div style="display:flex; justify-content:space-between; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
            <span style="color:var(--text-muted);">Assigned Counsel</span>
            <span>${r.assignedLawyer}</span>
          </div>
        </div>
      `;
    } else {
      fieldsHtml = `
        <pre style="font-size:12px; background:var(--bg-subtle); padding:12px; border-radius:8px; overflow:auto;">${JSON.stringify(r, null, 2)}</pre>
      `;
    }

    return `
      <div style="padding:4px 0;">
        ${fieldsHtml}
        <div style="margin-top:24px;">
          <a href="#/${type === 'parcel' ? 'land' : type + 's'}/${r.id}" class="btn btn-primary" style="width:100%; text-decoration:none;" onclick="window.MeridianApp.drawer.close()">
            Open Full Record Screen
          </a>
        </div>
      </div>
    `;
  }

  renderDocumentsTab(type, r) {
    const docs = (r.sources || []).map(s => `
      <div style="padding:12px; border:1px solid var(--border-subtle); border-radius:8px; margin-bottom:10px; display:flex; justify-content:space-between; align-items:center;">
        <div>
          <div style="font-weight:600; font-size:13px;">${s.docName || s.field}</div>
          <div style="font-size:11px; color:var(--text-tertiary);">Source ID: ${s.docId} • Page ${s.page}</div>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.openDocViewer('${s.docId}', ${s.page})">
          View Doc
        </button>
      </div>
    `).join('');

    return docs || `<p style="color:var(--text-muted); font-size:13px;">No linked source documents registered for this quick preview.</p>`;
  }

  renderLinkedTab(type, r) {
    return `
      <div style="display:flex; flex-direction:column; gap:12px;">
        <div style="font-size:12px; font-weight:600; color:var(--text-muted); text-transform:uppercase;">Connected Enterprise Entities</div>
        ${(r.linkedLoans || []).map(l => `<div style="padding:8px 12px; background:var(--bg-subtle); border-radius:6px; font-size:13px;">💳 Loan: <a href="#/loans/${l}">${l}</a></div>`).join('')}
        ${(r.linkedParcels || []).map(p => `<div style="padding:8px 12px; background:var(--bg-subtle); border-radius:6px; font-size:13px;">🏞️ Parcel: <a href="#/land/${p}">${p}</a></div>`).join('')}
        ${(r.linkedMatters || []).map(m => `<div style="padding:8px 12px; background:var(--bg-subtle); border-radius:6px; font-size:13px;">⚖️ Case Matter: <a href="#/matters/${m}">${m}</a></div>`).join('')}
      </div>
    `;
  }

  renderHistoryTab(type, r) {
    return `
      <div class="audit-timeline">
        <div class="timeline-item">
          <div class="timeline-node"></div>
          <div class="timeline-header">
            <span>28 Oct 2026, 10:15 AM</span>
            <span>Rajesh Sharma</span>
          </div>
          <div class="timeline-title">Audit Log Check Passed</div>
          <div class="timeline-desc">Automated consistency check verified across linked registries.</div>
        </div>
        <div class="timeline-item">
          <div class="timeline-node"></div>
          <div class="timeline-header">
            <span>20 Oct 2026, 03:40 PM</span>
            <span>AI Entity Agent</span>
          </div>
          <div class="timeline-title">Record Synchronized</div>
          <div class="timeline-desc">Extracted latest field values from authoritative source documents.</div>
        </div>
      </div>
    `;
  }
}

// Document Viewer Controller
export class DocumentViewerModal {
  constructor() {
    this.modalEl = null;
  }

  open(docId, page = 1) {
    api.getDocumentById(docId).then(doc => {
      this.render(doc, page);
    }).catch(err => {
      // Fallback display if mock doc id
      this.render({
        id: docId,
        name: `Document ${docId}.pdf`,
        type: 'Statutory Record',
        confidentiality: 'Confidential',
        pageCount: 6,
        confidence: 96,
        extractedFields: [
          { name: 'Document Identifier', value: docId, confidence: 99, status: 'Verified' }
        ]
      }, page);
    });
  }

  render(doc, activePage = 1) {
    let container = document.getElementById('doc-viewer-modal');
    if (!container) {
      container = document.createElement('div');
      container.id = 'doc-viewer-modal';
      document.body.appendChild(container);
    }

    container.innerHTML = `
      <div style="position:fixed; inset:0; background:rgba(15,23,42,0.8); backdrop-filter:blur(4px); z-index:250; display:flex; flex-direction:column; animation:fadeIn 150ms ease;">
        <!-- Top Toolbar -->
        <div style="height:56px; background:#0F172A; border-bottom:1px solid #1E293B; display:flex; align-items:center; justify-content:space-between; padding:0 24px; color:#F8FAFC;">
          <div style="display:flex; align-items:center; gap:16px;">
            <span style="font-weight:700; font-size:15px; display:flex; align-items:center; gap:8px;">
              📄 ${doc.name}
            </span>
            ${renderConfidentialityTag(doc.confidentiality)}
            <span style="font-size:12px; color:#94A3B8; background:rgba(255,255,255,0.1); padding:2px 8px; border-radius:4px;">
              🔒 Original unchanged (Read-Only)
            </span>
          </div>
          <div style="display:flex; align-items:center; gap:16px;">
            <span style="font-size:13px; color:#94A3B8;">Page ${activePage} of ${doc.pageCount || 4}</span>
            <button class="btn btn-sm btn-secondary" onclick="document.getElementById('doc-viewer-modal').remove()">
              ✕ Close
            </button>
          </div>
        </div>

        <!-- Main Body: Thumbnails + Document Page Canvas + Extracted Fields -->
        <div style="flex:1; display:flex; overflow:hidden;">
          <!-- Left Thumbnails -->
          <div style="width:160px; background:#111827; border-right:1px solid #1E293B; overflow-y:auto; padding:16px 12px; display:flex; flex-direction:column; gap:12px;">
            <div style="font-size:11px; font-weight:700; color:#64748B; text-transform:uppercase;">Pages (${doc.pageCount || 4})</div>
            ${Array.from({ length: doc.pageCount || 4 }).map((_, idx) => `
              <div style="border:2px solid ${idx + 1 === Number(activePage) ? '#4F46E5' : '#374151'}; border-radius:4px; padding:12px 8px; background:#1F2937; text-align:center; color:#E5E7EB; font-size:11px; cursor:pointer;" onclick="window.MeridianApp.openDocViewer('${doc.id}', ${idx + 1})">
                <div style="height:50px; background:#374151; border-radius:2px; margin-bottom:6px; display:flex; align-items:center; justify-content:center; font-size:10px; color:#9CA3AF;">Preview</div>
                Page ${idx + 1}
              </div>
            `).join('')}
          </div>

          <!-- Center Canvas -->
          <div class="doc-viewer-canvas" style="flex:1;">
            <div class="mock-pdf-page">
              <div style="display:flex; justify-content:space-between; border-bottom:2px solid #E5E7EB; padding-bottom:12px; margin-bottom:20px;">
                <div style="font-size:18px; font-weight:bold; letter-spacing:-0.02em;">OFFICIAL RECORD / INSTRUMENT</div>
                <div style="font-size:12px; color:#6B7280;">DOC ID: ${doc.id} • Page ${activePage}</div>
              </div>
              <p style="margin-bottom:16px; font-size:14px; color:#374151;">
                THIS DEED / SANCTION NOTICE is made on this authoritative recording date between the Parties referenced herein.
              </p>
              <div class="pdf-highlight" style="margin:20px 0; font-size:15px; font-weight:600; line-height:1.8;">
                [EXTRACTED FIELD HIGHLIGHT: Active Page Citation]
                <br>
                Certified value, survey parcel identification number, or covenant extracted by OCR Agent.
                <br>
                Confirmed: ${doc.extractedFields?.[0]?.value || 'Authoritative data string verified.'}
              </div>
              <p style="margin-bottom:16px; font-size:13px; color:#4B5563;">
                All covenants, representations, warranties, and security charges created under this instrument remain binding and registered with the competent Sub-Registrar / DRT / National Company Law Tribunal.
              </p>
              <div style="margin-top:60px; display:flex; justify-content:space-between; font-size:12px; color:#9CA3AF;">
                <div>Digitally Sealed & Stamped</div>
                <div>Page ${activePage} of ${doc.pageCount || 4}</div>
              </div>
            </div>
          </div>

          <!-- Right Field Inspector -->
          <div style="width:340px; background:#0F172A; border-left:1px solid #1E293B; overflow-y:auto; padding:20px; color:#F8FAFC;">
            <div style="font-size:13px; font-weight:700; margin-bottom:16px; display:flex; align-items:center; justify-content:space-between;">
              <span>Extracted Fields</span>
              ${renderConfidenceBar(doc.confidence || 94)}
            </div>
            ${(doc.extractedFields || []).map(f => `
              <div style="background:#1E293B; border:1px solid #334155; border-radius:8px; padding:12px; margin-bottom:12px;">
                <div style="font-size:11px; color:#94A3B8; text-transform:uppercase; margin-bottom:4px;">${f.name}</div>
                <div style="font-size:14px; font-weight:600; color:#F8FAFC; margin-bottom:8px;">${f.value}</div>
                <div style="display:flex; justify-content:space-between; align-items:center;">
                  ${renderStatusBadge(f.status || 'Verified')}
                  ${renderConfidenceBar(f.confidence || 95)}
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }
}
