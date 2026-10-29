/**
 * Module M7: Case and Matter Management, Fact Sheet, Timeline, Conflicts, Hearing Diary
 * Routes: /matters, /matters/:id, /matters/create, /matters/diary
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderAIGeneratedTag, renderStepper, renderTableSkeleton } from '../components/shared.js';
import { formatDate } from '../formatters.js';

export async function renderMattersView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Records</span>
        <span class="breadcrumb-separator">/</span>
        <span>Cases and Matters</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Litigation & Dispute Matters</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Central management of DRT, NCLT, High Court, and Civil Court proceedings.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/matters/diary" class="btn btn-secondary btn-sm">
            📅 Hearing Diary
          </a>
          <a href="#/matters/create" class="btn btn-primary btn-sm">
            + Create New Matter (Stepper)
          </a>
        </div>
      </div>
    </div>

    <div id="matters-list-content">
      ${renderTableSkeleton(6, 7)}
    </div>
  `;

  let matters = await api.getMatters();

  // If role is External counsel, filter only assigned matters (Section 4 Least Access rule)
  if (state.currentRole === 'External counsel') {
    const assignedIds = state.currentUser?.assignedMatters || ['M-2025-014', 'M-2026-003'];
    matters = matters.filter(m => assignedIds.includes(m.id));
  }

  renderMattersTable(matters);
}

function renderMattersTable(matters) {
  const target = document.getElementById('matters-list-content');
  if (!target) return;

  target.innerHTML = `
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" placeholder="Search case title, forum, number..." oninput="window.filterMatters(this.value)" />
        <div class="filter-chip-group">
          <span class="filter-chip active">All Matters (${matters.length})</span>
          <span class="filter-chip">DRT Recovery</span>
          <span class="filter-chip">Civil Title</span>
          <span class="filter-chip">NCLT / IBC</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Matter ID</th>
            <th>Title / Cause Title</th>
            <th>Forum / Court</th>
            <th>Case Number</th>
            <th>Company</th>
            <th>Next Hearing</th>
            <th>Assigned Counsel</th>
            <th>Status</th>
            <th style="text-align:right;">Matter File</th>
          </tr>
        </thead>
        <tbody id="matter-tbody">
          ${matters.map(m => `
            <tr onclick="window.location.hash='#/matters/${m.id}'">
              <td style="font-weight:700; color:var(--primary);">${m.id}</td>
              <td>
                <div style="font-weight:600; color:var(--text-main);">${m.title}</div>
                <div style="font-size:11px; color:var(--text-tertiary);">Internal Lead: ${m.internalCounsel}</div>
              </td>
              <td>${m.forum}</td>
              <td style="font-family:var(--font-mono); font-size:12px;">${m.caseNumber}</td>
              <td>${m.companyName}</td>
              <td><span style="font-weight:600; color:var(--primary);">${formatDate(m.nextHearing)}</span></td>
              <td>${m.assignedLawyer}</td>
              <td>${renderStatusBadge(m.status)}</td>
              <td style="text-align:right;">
                <a href="#/matters/${m.id}" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">Open File →</a>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export async function renderMatterDetailView(container, matterId) {
  const matter = await api.getMatterById(matterId);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/matters">Matters</a>
        <span class="breadcrumb-separator">/</span>
        <span>${matter.id}</span>
      </div>
      <div class="page-title-row">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h1 class="page-title">${matter.title}</h1>
            ${renderStatusBadge(matter.status)}
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            ${matter.forum} • Case No: <strong>${matter.caseNumber}</strong> • Company: ${matter.companyName}
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-secondary btn-sm" onclick="window.addDocumentModal('${matter.id}')">
            + Add Document
          </button>
        </div>
      </div>
    </div>

    <!-- Mandatory Review Banner (Section 7: AI never shows a final legal opinion) -->
    <div style="background:var(--color-warning-bg); border:1px solid var(--color-warning-border); padding:12px 16px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="font-size:16px;">⚖️</span>
        <div>
          <strong style="color:var(--color-warning-text); font-size:13px;">${matter.reviewStatus}</strong>
          <span style="font-size:12px; color:var(--color-warning-text); margin-left:8px;">AI-synthesized matter brief. Final legal strategy requires internal lawyer sign-off.</span>
        </div>
      </div>
      <button class="btn btn-sm btn-secondary" onclick="window.approveMatterAnalysis('${matter.id}')">
        Lawyer Sign-Off
      </button>
    </div>

    <!-- Matter File Sub-Tabs -->
    <div class="tabs-nav">
      <button class="tab-btn active" onclick="window.switchMatterTab('facts')">Fact Sheet (${matter.facts?.length || 0})</button>
      <button class="tab-btn" onclick="window.switchMatterTab('timeline')">Litigation Timeline (${matter.timeline?.length || 0})</button>
      <button class="tab-btn" onclick="window.switchMatterTab('conflicts')">Conflicts & Opposing Arguments</button>
      <button class="tab-btn" onclick="window.switchMatterTab('strengths')">Strengths & Weaknesses</button>
      <button class="tab-btn" onclick="window.switchMatterTab('missing')">Missing Information (${matter.missingInfo?.length || 0})</button>
      <button class="tab-btn" onclick="window.switchMatterTab('hearings')">Hearing Diary</button>
    </div>

    <div id="matter-tab-container">
      <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
          <h3 style="font-size:15px; font-weight:700;">Authoritative Fact Sheet</h3>
          ${renderAIGeneratedTag('Every Fact Grounded with SourceChip')}
        </div>
        <div style="display:flex; flex-direction:column; gap:12px;">
          ${(matter.facts || []).map(f => `
            <div style="padding:14px; background:var(--bg-subtle); border-radius:8px; border:1px solid var(--border-subtle); display:flex; justify-content:space-between; align-items:center;">
              <div style="font-size:13px; color:var(--text-main); line-height:1.6;">
                • ${f.fact}
                ${renderSourceChip(f.source.docId, f.source.docName, f.source.page)}
              </div>
              ${renderStatusBadge(f.status)}
            </div>
          `).join('')}
        </div>
      </div>
    </div>
  `;

  window.approveMatterAnalysis = async (mId) => {
    await api.approveLegalAnalysis(mId);
    window.MeridianApp.showToast('Legal analysis certified by assigned lawyer.', 'success');
    renderMatterDetailView(container, mId);
  };

  window.addDocumentModal = (mId) => {
    const docName = prompt("Enter document name or filing title to attach to this matter:", "Additional Rejoinder Affidavit.pdf");
    if (docName) {
      api.addDocumentToMatter(mId, {
        id: `DOC-NEW-${Date.now().toString().slice(-3)}`,
        name: docName,
        type: 'Court Pleadings',
        extractedFields: [{ name: 'Filing Evidence', value: 'Receipt & Service proof recorded.' }]
      });
      window.MeridianApp.showToast('Document attached to matter file. Timeline and fact sheet updated.', 'success');
      renderMatterDetailView(container, mId);
    }
  };

  window.switchMatterTab = (tab) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    const target = document.getElementById('matter-tab-container');
    if (!target) return;

    if (tab === 'timeline') {
      target.innerHTML = `
        <div class="card">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <h3 style="font-size:15px; font-weight:700;">Date-wise Dispute Timeline</h3>
            <button class="btn btn-secondary btn-sm" onclick="window.addTimelineEvent('${matter.id}')">+ Add Event</button>
          </div>
          <div class="audit-timeline">
            ${(matter.timeline || []).map(t => `
              <div class="timeline-item">
                <div class="timeline-node"></div>
                <div class="timeline-header">
                  <span>Date: <strong>${formatDate(t.date)}</strong></span>
                  <span>${renderSourceChip(t.docId, t.evidence, 1)}</span>
                </div>
                <div class="timeline-title">${t.title}</div>
                <div class="timeline-desc">Evidence: ${t.evidence}</div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else if (tab === 'conflicts') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">Contradictions & Fact Conflicts</h3>
          <div style="display:flex; flex-direction:column; gap:16px; margin-bottom:24px;">
            ${(matter.conflicts || []).map(c => `
              <div style="border:1px solid var(--border-subtle); border-radius:8px; overflow:hidden;">
                <div style="padding:8px 14px; background:var(--bg-subtle); font-weight:700; font-size:13px;">${c.title}</div>
                <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; padding:14px;">
                  <div style="background:#FEF2F2; padding:12px; border-radius:6px; border:1px solid #FECACA;">
                    <div style="font-size:11px; font-weight:bold; color:#B91C1C; margin-bottom:4px;">OPPOSING CLAIM</div>
                    <div style="font-size:12px; color:#1F2937;">${c.sideA}</div>
                    <div style="margin-top:6px; font-size:11px; color:#6B7280;">Source: ${c.sourceA}</div>
                  </div>
                  <div style="background:#F0FDF4; padding:12px; border-radius:6px; border:1px solid #BBF7D0;">
                    <div style="font-size:11px; font-weight:bold; color:#15803D; margin-bottom:4px;">REBUTTAL EVIDENCE</div>
                    <div style="font-size:12px; color:#1F2937;">${c.sideB}</div>
                    <div style="margin-top:6px; font-size:11px; color:#6B7280;">Source: ${c.sourceB}</div>
                  </div>
                </div>
              </div>
            `).join('') || '<p style="color:var(--text-muted);">No open contradictions identified.</p>'}
          </div>

          <h3 style="font-size:15px; font-weight:700; margin-bottom:12px; display:flex; align-items:center; gap:8px;">
            <span>Other Side's Likely Arguments</span>
            ${renderAIGeneratedTag('Adversarial Forecast')}
          </h3>
          <div style="display:flex; flex-direction:column; gap:8px;">
            ${(matter.otherSideArguments || []).map(arg => `
              <div style="padding:10px 14px; background:var(--bg-subtle); border-radius:6px; font-size:13px; color:var(--text-main);">
                ⚠️ ${arg.point}
              </div>
            `).join('')}
          </div>
        </div>
      `;
    } else if (tab === 'strengths') {
      target.innerHTML = `
        <div class="card">
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:20px;">
            <div>
              <h3 style="font-size:15px; font-weight:700; color:var(--color-success-text); margin-bottom:12px;">Key Strengths</h3>
              ${(matter.strengths || []).map(s => `<div style="padding:10px; background:var(--color-success-bg); border-radius:6px; margin-bottom:8px; font-size:13px; color:var(--color-success-text);">✓ ${s}</div>`).join('')}
            </div>
            <div>
              <h3 style="font-size:15px; font-weight:700; color:var(--color-danger-text); margin-bottom:12px;">Strategic Vulnerabilities</h3>
              ${(matter.weaknesses || []).map(w => `<div style="padding:10px; background:var(--color-danger-bg); border-radius:6px; margin-bottom:8px; font-size:13px; color:var(--color-danger-text);">⚠ ${w}</div>`).join('')}
            </div>
          </div>
        </div>
      `;
    } else if (tab === 'missing') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">Missing Information & Discovery Checklist</h3>
          <div style="display:flex; flex-direction:column; gap:12px;">
            ${(matter.missingInfo || []).map(m => `
              <div style="padding:12px; background:var(--bg-subtle); border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <div style="font-weight:600; font-size:13px;">${m.item}</div>
                  <div style="font-size:11px; color:var(--text-muted);">${m.status}</div>
                </div>
                <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Discovery requisition sent to registry clerk.', 'info')">
                  ${m.requested ? 'Requested' : 'Request Info'}
                </button>
              </div>
            `).join('') || '<p style="color:var(--text-muted);">All essential discovery evidence gathered.</p>'}
          </div>
        </div>
      `;
    } else if (tab === 'hearings') {
      target.innerHTML = `
        <div class="card">
          <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Hearing Diary Entries</h3>
          <table class="data-table">
            <thead><tr><th>Hearing Date</th><th>Bench / Court</th><th>Purpose</th><th>Recorded Outcome</th></tr></thead>
            <tbody>
              ${(matter.hearings || []).map(h => `
                <tr>
                  <td><strong>${formatDate(h.date)}</strong> (${h.time})</td>
                  <td>${h.bench}</td>
                  <td>${h.purpose}</td>
                  <td>${h.outcome || '<span class="status-badge attention">Scheduled</span>'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else {
      renderMatterDetailView(container, matterId);
    }
  };
}

export async function renderCreateMatterView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/matters">Matters</a>
        <span class="breadcrumb-separator">/</span>
        <span>Create New Matter</span>
      </div>
      <h1 class="page-title">Initiate New Matter File (Stepper Flow)</h1>
    </div>

    <div class="card" style="max-width:760px; margin:0 auto; padding:28px;">
      ${renderStepper(['Case Details', 'Parties & Counsel', 'Link Portfolio Records', 'Upload Documents'], 0)}

      <div class="form-group" style="margin-top:24px;">
        <label class="form-label">Matter Title / Cause Title</label>
        <input type="text" class="form-control" placeholder="e.g., Meridian Infra vs Coastal Infrastructure Authority" />
      </div>

      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
        <div class="form-group">
          <label class="form-label">Court / Forum</label>
          <input type="text" class="form-control" placeholder="e.g., Debts Recovery Tribunal-II, Mumbai" />
        </div>
        <div class="form-group">
          <label class="form-label">Case Number</label>
          <input type="text" class="form-control" placeholder="e.g., OA No. 89/2026" />
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">Relevant Group Company</label>
        <select class="form-control">
          <option>Meridian Infra Holdings Ltd</option>
          <option>Meridian Realty Pvt Ltd</option>
          <option>Meridian Estates Pvt Ltd</option>
          <option>Meridian Projects LLP</option>
        </select>
      </div>

      <div style="margin-top:24px; padding-top:16px; border-top:1px solid var(--border-subtle); display:flex; justify-content:flex-end; gap:12px;">
        <a href="#/matters" class="btn btn-secondary">Cancel</a>
        <button class="btn btn-primary" onclick="window.MeridianApp.showToast('Matter created and indexed into litigation docket.', 'success'); window.location.hash='#/matters';">
          Create Matter File →
        </button>
      </div>
    </div>
  `;
}

export async function renderHearingDiaryView(container) {
  const matters = await api.getMatters();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/matters">Matters</a>
        <span class="breadcrumb-separator">/</span>
        <span>Hearing Diary</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Hearing Diary & Court Calendar</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Calendar of judicial listings. Hearing outcomes record next dates that synchronize automatically with Compliance Calendar.
          </p>
        </div>
      </div>
    </div>

    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Matter</th>
            <th>Forum</th>
            <th>Case Number</th>
            <th>Listing Purpose</th>
            <th>Assigned Counsel</th>
            <th style="text-align:right;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${matters.map(m => `
            <tr>
              <td><strong style="color:var(--primary);">${formatDate(m.nextHearing)}</strong></td>
              <td><a href="#/matters/${m.id}" style="font-weight:600;">${m.title}</a></td>
              <td>${m.forum}</td>
              <td style="font-family:var(--font-mono);">${m.caseNumber}</td>
              <td>${m.nextHearingPurpose || 'Arguments / Compliance'}</td>
              <td>${m.assignedLawyer}</td>
              <td style="text-align:right;">
                <button class="btn btn-secondary btn-sm" onclick="window.recordHearingOutcome('${m.id}')">Record Outcome</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  window.recordHearingOutcome = (matterId) => {
    const outcome = prompt("Enter hearing outcome summary:", "Arguments concluded in part. Matter adjourned for cross-examination.");
    const nextDate = prompt("Enter next date of hearing (DD MMM YYYY):", "26 Nov 2026");
    if (outcome && nextDate) {
      window.MeridianApp.showToast(`Hearing outcome recorded. Next date ${nextDate} pushed to Compliance Calendar.`, 'success');
    }
  };
}
