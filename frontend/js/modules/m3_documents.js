/**
 * Module M3: Document Management, Upload, Viewer, Verification Queue, Duplicates
 * Routes: /documents, /documents/queue, /documents/duplicates
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderConfidenceBar, renderConfidentialityTag, renderTableSkeleton } from '../components/shared.js';
import { formatDate } from '../formatters.js';

export async function renderDocumentsView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Records</span>
        <span class="breadcrumb-separator">/</span>
        <span>Documents</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Document Management</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Central repository of 40 title deeds, sanction letters, filings, court pleadings, and tax notices.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/documents/duplicates" class="btn btn-secondary btn-sm">
            Duplicate Pairs (1)
          </a>
          <a href="#/documents/queue" class="btn btn-secondary btn-sm">
            Verification Queue (3)
          </a>
          <button type="button" class="btn btn-primary btn-sm" onclick="window.openUploadModal()">
            + Upload Document
          </button>
        </div>
      </div>
    </div>

    <!-- Upload Dropzone & Sync Banner -->
    <div id="upload-modal-container" style="display:none; margin-bottom: 24px;">
      <div class="card" style="border: 2px dashed var(--primary); background: var(--bg-surface); padding: 28px; text-align: center;">
        <div style="font-size:32px; margin-bottom:8px;">📤</div>
        <h3 style="font-size:16px; font-weight:700; margin-bottom:4px;">Drag & drop document files here</h3>
        <p style="font-size:12px; color:var(--text-muted); margin-bottom:16px;">Supports PDF, scanned TIFF, JPG, and DOCX (up to 50MB per file)</p>
        
        <div style="display:flex; justify-content:center; gap:12px; margin-bottom:16px; flex-wrap:wrap;">
          <input type="file" id="file-picker" style="display:none;" onchange="window.handleFileSelect(event)" />
          <button type="button" class="btn btn-primary btn-sm" onclick="document.getElementById('file-picker').click()">
            Select Local Files
          </button>
          <button type="button" class="btn btn-secondary btn-sm" onclick="window.syncSharedFolder()">
            Sync Shared Folder (SMB / OneDrive)
          </button>
        </div>

        <div style="display:flex; gap:12px; justify-content:center; max-width:600px; margin:0 auto; font-size:12px;">
          <select id="upload-confidentiality" class="form-control" style="font-size:12px;">
            <option value="Internal">Confidentiality: Internal</option>
            <option value="Confidential">Confidentiality: Confidential</option>
            <option value="Restricted">Confidentiality: Restricted</option>
            <option value="Public">Confidentiality: Public</option>
          </select>
          <select id="upload-link-type" class="form-control" style="font-size:12px;">
            <option value="COMP-001">Link: Meridian Holdings (Parent)</option>
            <option value="LN-001">Link: Facility LN-001 (NNB Loan)</option>
            <option value="P-001">Link: Parcel P-001 (Hinjewadi)</option>
            <option value="M-2025-014">Link: Matter M-2025-014 (DRT)</option>
          </select>
        </div>

        <!-- Processing Timeline Simulator -->
        <div id="upload-progress-timeline" style="display:none; margin-top:20px; padding-top:16px; border-top:1px solid var(--border-subtle);">
          <div style="font-size:12px; font-weight:600; margin-bottom:8px;">Document Intake Pipeline:</div>
          <div style="display:flex; justify-content:space-between; max-width:520px; margin:0 auto; font-size:11px;">
            <span id="pipe-1" style="color:var(--color-success); font-weight:bold;">1. Uploaded ✓</span>
            <span id="pipe-2" style="color:var(--text-tertiary);">2. OCR Engine</span>
            <span id="pipe-3" style="color:var(--text-tertiary);">3. Classified</span>
            <span id="pipe-4" style="color:var(--text-tertiary);">4. Fields Extracted</span>
            <span id="pipe-5" style="color:var(--text-tertiary);">5. Routed</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Document List Table Container -->
    <div id="docs-list-content">
      ${renderTableSkeleton(8, 7)}
    </div>
  `;

  const docs = await api.getDocuments();
  renderDocsTable(docs);

  window.openUploadModal = () => {
    const el = document.getElementById('upload-modal-container');
    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
  };

  window.handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const timeline = document.getElementById('upload-progress-timeline');
    if (timeline) timeline.style.display = 'block';

    const p2 = document.getElementById('pipe-2');
    const p3 = document.getElementById('pipe-3');
    const p4 = document.getElementById('pipe-4');
    const p5 = document.getElementById('pipe-5');

    setTimeout(() => { if (p2) { p2.style.color = 'var(--color-success)'; p2.textContent = '2. OCR Engine ✓'; } }, 600);
    setTimeout(() => { if (p3) { p3.style.color = 'var(--color-success)'; p3.textContent = '3. Classified ✓'; } }, 1200);
    setTimeout(() => { if (p4) { p4.style.color = 'var(--color-success)'; p4.textContent = '4. Fields Extracted ✓'; } }, 1800);
    setTimeout(async () => {
      if (p5) { p5.style.color = 'var(--color-success)'; p5.textContent = '5. Routed ✓'; }
      const newDoc = await api.uploadDocument({
        name: file.name,
        confidentiality: document.getElementById('upload-confidentiality').value,
        companyId: document.getElementById('upload-link-type').value
      });
      window.MeridianApp.showToast(`Document ${newDoc.name} ingested & routed to verification.`, 'success');
      const updatedDocs = await api.getDocuments();
      renderDocsTable(updatedDocs);
      setTimeout(() => {
        document.getElementById('upload-modal-container').style.display = 'none';
      }, 1000);
    }, 2400);
  };

  window.syncSharedFolder = () => {
    window.MeridianApp.showToast('Synchronizing SMB network drive "\\\\meridian-nas\\legal_vault"... 4 new instruments indexed.', 'info');
  };
}

function renderDocsTable(docs) {
  const target = document.getElementById('docs-list-content');
  if (!target) return;

  target.innerHTML = `
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" id="doc-search-box" placeholder="Filter by title, type, or entity..." oninput="window.filterDocs(this.value)" />
        <div class="filter-chip-group">
          <span class="filter-chip active" onclick="window.filterDocsByType('all')">All Documents (40)</span>
          <span class="filter-chip" onclick="window.filterDocsByType('Title Deed')">Title Deeds</span>
          <span class="filter-chip" onclick="window.filterDocsByType('Sanction Letter')">Sanctions</span>
          <span class="filter-chip" onclick="window.filterDocsByType('Court')">Court Filings</span>
          <span class="filter-chip" onclick="window.filterDocsByType('Unreviewed')">Unreviewed</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Document Name</th>
            <th>Type</th>
            <th>Linked Entity</th>
            <th>Confidentiality</th>
            <th>Confidence</th>
            <th>Status</th>
            <th>Date</th>
          </tr>
        </thead>
        <tbody id="docs-tbody">
          ${docs.map(d => `
            <tr onclick="window.MeridianApp.openDocViewer('${d.id}', 1)" title="Click to view original document">
              <td style="font-weight:600; color:var(--primary);">${d.id}</td>
              <td>
                <div style="font-weight:600; color:var(--text-main);">${d.name}</div>
                <div style="font-size:11px; color:var(--text-tertiary);">${d.fileSize} • ${d.pageCount} pages • Uploaded by ${d.uploadedBy}</div>
              </td>
              <td><span style="font-size:12px;">${d.type}</span></td>
              <td><span style="font-weight:500;">${d.linkedEntity || d.companyId}</span></td>
              <td>${renderConfidentialityTag(d.confidentiality)}</td>
              <td>${renderConfidenceBar(d.confidence)}</td>
              <td>${renderStatusBadge(d.status)}</td>
              <td style="font-size:12px; color:var(--text-muted);">${formatDate(d.uploadDate)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  window.filterDocs = (term) => {
    const q = term.toLowerCase();
    const filtered = docs.filter(d => d.name.toLowerCase().includes(q) || d.type.toLowerCase().includes(q) || d.id.toLowerCase().includes(q));
    const tbody = document.getElementById('docs-tbody');
    if (tbody) {
      tbody.innerHTML = filtered.map(d => `
        <tr onclick="window.MeridianApp.openDocViewer('${d.id}', 1)">
          <td style="font-weight:600; color:var(--primary);">${d.id}</td>
          <td>
            <div style="font-weight:600; color:var(--text-main);">${d.name}</div>
            <div style="font-size:11px; color:var(--text-tertiary);">${d.fileSize} • ${d.pageCount} pages</div>
          </td>
          <td>${d.type}</td>
          <td>${d.linkedEntity || d.companyId}</td>
          <td>${renderConfidentialityTag(d.confidentiality)}</td>
          <td>${renderConfidenceBar(d.confidence)}</td>
          <td>${renderStatusBadge(d.status)}</td>
          <td>${formatDate(d.uploadDate)}</td>
        </tr>
      `).join('');
    }
  };
}

export async function renderVerificationQueueView(container) {
  const docs = await api.getDocuments();
  const targetDoc = docs.find(d => d.id === 'DOC-016') || docs[0];

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/documents">Documents</a>
        <span class="breadcrumb-separator">/</span>
        <span>Verification Queue</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Side-by-Side Field Verification Queue</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Critical fields (money, dates, legal IDs) flagged by OCR Agent require mandatory human verification before indexing.
          </p>
        </div>
        <div class="page-actions" style="font-size:12px; color:var(--text-muted); display:flex; align-items:center; gap:8px;">
          <span>Shortcuts:</span>
          <span class="kbd-shortcut">V</span> Verify
          <span class="kbd-shortcut">C</span> Correct
          <span class="kbd-shortcut">R</span> Reject
          <span class="kbd-shortcut">N</span> Next Item
        </div>
      </div>
    </div>

    <!-- SideBySideReview Split View Layout -->
    <div class="split-view-container">
      <!-- Left: Original Source Document -->
      <div class="card" style="display:flex; flex-direction:column; padding:0; overflow:hidden;">
        <div style="padding:12px 16px; background:var(--bg-subtle); border-bottom:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
          <div style="font-weight:600; font-size:13px; display:flex; align-items:center; gap:6px;">
            <span>📄 ${targetDoc.name}</span>
            ${renderConfidentialityTag(targetDoc.confidentiality)}
          </div>
          <span style="font-size:11px; color:var(--text-muted); background:var(--bg-surface); padding:2px 8px; border-radius:4px; border:1px solid var(--border-subtle);">
            🔒 Original unchanged (Read-Only)
          </span>
        </div>
        <div class="doc-viewer-canvas" style="flex:1;">
          <div class="mock-pdf-page">
            <div style="border-bottom:2px solid #E5E7EB; padding-bottom:12px; margin-bottom:16px;">
              <h3 style="font-size:16px; font-weight:bold;">COASTAL FINANCE LTD — STATEMENT OF ACCOUNT</h3>
              <div style="font-size:12px; color:#6B7280;">Facility Account: CFL-TL-2020-41 • As on: 30 Sep 2026</div>
            </div>
            <p style="font-size:13px; margin-bottom:14px;">Borrower: Meridian Estates Pvt Ltd</p>
            <div class="pdf-highlight" style="margin:20px 0; font-size:16px; font-weight:700;">
              Total Outstanding Claim Balance: ₹ 42,10,00,000.00
              <br>
              <small style="font-size:11px; font-weight:normal; color:#4B5563;">[Principal: ₹35,00,00,000 | Normal Interest: ₹3,60,00,000 | Penal Compounding: ₹3,50,00,000]</small>
            </div>
            <p style="font-size:12px; color:#4B5563; line-height:1.6;">
              Please note that demand has been served upon the Corporate Guarantor Meridian Infra Holdings Ltd. Failure to remit balance within 15 days will precipitate enforcement of equitable mortgage over Gachibowli Mixed Use Land (Parcel P-003).
            </p>
          </div>
        </div>
      </div>

      <!-- Right: AI Extracted Fields with Verification Controls -->
      <div class="card" style="display:flex; flex-direction:column; overflow:hidden;">
        <div style="padding-bottom:12px; border-bottom:1px solid var(--border-subtle); margin-bottom:16px;">
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="font-size:15px; font-weight:700;">Extracted Fields</h3>
            <span class="status-badge attention">1 Discrepancy Flagged</span>
          </div>
          <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
            Document OCR Confidence: ${renderConfidenceBar(targetDoc.confidence)}
          </div>
        </div>

        <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:16px;">
          <!-- Field 1: Critical Money Mismatch Edge Case -->
          <div style="border:1px solid var(--color-danger-border); background:var(--color-danger-bg); border-radius:8px; padding:16px;">
            <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:6px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span style="color:var(--color-danger); font-size:14px;">🚩</span>
                <strong style="font-size:13px; color:var(--color-danger-text);">Outstanding Claim Balance (Critical Field)</strong>
              </div>
              ${renderConfidenceBar(76)}
            </div>
            <div style="margin:10px 0;">
              <input type="text" id="field-val-1" class="form-control" value="₹ 42,10,00,000" style="font-weight:700; font-size:16px;" />
            </div>
            <div style="font-size:12px; color:var(--color-danger-text); margin-bottom:12px;">
              ⚠️ <strong>Audit Warning:</strong> Company internal ledger records ₹ 38,60,00,000. Discrepancy of ₹ 3,50,00,000 represents disputed penal interest charged contrary to RBI circular DOR.MCS.REC.28/01.01.001/2023-24.
            </div>
            <div style="display:flex; gap:8px;">
              <button class="btn btn-secondary btn-sm" onclick="window.verifyFieldAction('DOC-016', 'F-023', 'Verified')">
                ✓ Verify As Extracted (V)
              </button>
              <button class="btn btn-secondary btn-sm" style="color:var(--color-info-text); border-color:var(--color-info-border);" onclick="window.correctFieldAction('DOC-016', 'F-023')">
                ✎ Correct to Ledger ₹ 38.60 Cr (C)
              </button>
              <button class="btn btn-danger btn-sm" onclick="window.verifyFieldAction('DOC-016', 'F-023', 'Rejected')">
                ✕ Reject (R)
              </button>
            </div>
          </div>

          <!-- Field 2: Borrower Name -->
          <div style="border:1px solid var(--border-subtle); background:var(--bg-subtle); border-radius:8px; padding:16px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
              <strong style="font-size:13px;">Borrower Entity</strong>
              ${renderConfidenceBar(99)}
            </div>
            <div style="font-size:14px; font-weight:600; margin-bottom:10px;">Meridian Estates Pvt Ltd</div>
            <div style="display:flex; gap:8px;">
              <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Borrower entity verified.', 'success')">✓ Verify</button>
            </div>
          </div>
        </div>

        <div style="padding-top:16px; border-top:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
          <span style="font-size:12px; color:var(--text-muted);">Queue progress: 1 of 3 items</span>
          <button class="btn btn-primary btn-sm" onclick="window.nextQueueItem()">
            Next Document (N) →
          </button>
        </div>
      </div>
    </div>
  `;

  window.verifyFieldAction = async (docId, fieldId, status) => {
    await api.verifyField(docId, fieldId, status);
    window.MeridianApp.showToast(`Field ${fieldId} marked as ${status}. Written to Audit Log.`, 'success');
  };

  window.correctFieldAction = async (docId, fieldId) => {
    await api.verifyField(docId, fieldId, 'Corrected', '₹ 38,60,00,000 (Adjusted for disputed penal compounding)');
    window.MeridianApp.showToast(`Field corrected to ₹ 38.60 Cr. Discrepancy logged for DRT legal brief.`, 'info');
  };

  window.nextQueueItem = () => {
    window.MeridianApp.showToast('Advancing to next queued document...', 'info');
  };
}

export async function renderDuplicatesView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/documents">Documents</a>
        <span class="breadcrumb-separator">/</span>
        <span>Duplicate Resolution</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Duplicate Document Pairs</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            AI duplicate detector identifies identical or near-identical uploads. Per rule: <strong>Nothing is ever deleted</strong>; records are kept side by side or marked.
          </p>
        </div>
      </div>
    </div>

    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; padding-bottom:12px; border-bottom:1px solid var(--border-subtle);">
        <div>
          <div style="font-size:15px; font-weight:700;">Mortgage Deed Hinjewadi Parcel P-001</div>
          <div style="font-size:12px; color:var(--text-muted);">Similarity Score: <strong style="color:var(--color-danger-text);">98.4% Match</strong> (OCR text and layout collision)</div>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Both copies retained with unique audit stamps.', 'info')">
            Keep Both
          </button>
          <button class="btn btn-primary btn-sm" onclick="window.MeridianApp.showToast('DOC-020 marked as Duplicate copy of DOC-019. Audit log updated.', 'success')">
            Mark as Duplicate (Keep Record)
          </button>
        </div>
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
        <div style="padding:16px; background:var(--bg-subtle); border-radius:8px; border:1px solid var(--border-subtle);">
          <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
            <strong style="color:var(--primary);">DOC-019 (Original Upload)</strong>
            <span class="status-badge verified">Primary Record</span>
          </div>
          <div style="font-size:13px; font-weight:600; margin-bottom:4px;">Registered Deed of Mortgage - Hinjewadi Parcel P-001 (Original).pdf</div>
          <div style="font-size:11px; color:var(--text-muted); line-height:1.6;">
            Uploaded by: Rohan Joshi • 20 Oct 2019<br>
            File size: 5.6 MB • 28 Pages • SHA-256: 4a9f...10b2
          </div>
        </div>

        <div style="padding:16px; background:var(--color-warning-bg); border-radius:8px; border:1px solid var(--color-warning-border);">
          <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
            <strong style="color:var(--color-warning-text);">DOC-020 (Candidate Duplicate)</strong>
            <span class="status-badge attention">Duplicate Detected</span>
          </div>
          <div style="font-size:13px; font-weight:600; margin-bottom:4px;">Duplicate Copy - Registered Deed of Mortgage Hinjewadi P-001.pdf</div>
          <div style="font-size:11px; color:var(--text-muted); line-height:1.6;">
            Uploaded by: Rohan Joshi • 25 Oct 2026<br>
            File size: 5.6 MB • 28 Pages • Exact content replica
          </div>
        </div>
      </div>
    </div>
  `;
}
