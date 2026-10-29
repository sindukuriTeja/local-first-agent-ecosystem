/**
 * Module M9: Drafting and Templates, Draft Editor, Version History, Approval Lock
 * Routes: /drafting, /drafting/editor, /drafting/editor/:id
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderAIGeneratedTag } from '../components/shared.js';

export async function renderDraftingView(container) {
  const templates = await api.getTemplates();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Intelligence</span>
        <span class="breadcrumb-separator">/</span>
        <span>Drafting & Templates</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Drafting Templates & Pleadings</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Standardized legal notices, replies, petitions, and settlement agreements grounded in verified facts.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/drafting/editor" class="btn btn-primary btn-sm">
            + Open Blank Draft Editor
          </a>
        </div>
      </div>
    </div>

    <!-- Template Library Grid Grouped by Type -->
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:20px;">
      ${templates.map(tpl => `
        <div class="card" style="display:flex; flex-direction:column; justify-content:space-between;">
          <div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <span class="status-badge calculated">${tpl.category}</span>
              <span style="font-size:11px; color:var(--text-tertiary);">Updated: ${tpl.lastUpdated}</span>
            </div>
            <h3 style="font-size:15px; font-weight:700; margin-bottom:6px; color:var(--text-main);">${tpl.name}</h3>
            <p style="font-size:12px; color:var(--text-muted); line-height:1.5; margin-bottom:12px;">${tpl.description}</p>
            
            <div style="font-size:11px; color:var(--text-muted); margin-bottom:4px;">
              <strong>Default Fact Sources:</strong>
              ${tpl.defaultFacts?.map(f => `<span style="margin-left:4px;">${renderSourceChip(f.source, f.label, 1)}</span>`).join('') || 'None'}
            </div>
          </div>

          <div style="margin-top:16px; padding-top:12px; border-top:1px solid var(--border-subtle); display:flex; justify-content:flex-end;">
            <a href="#/drafting/editor?templateId=${tpl.id}" class="btn btn-secondary btn-sm">
              Use Template →
            </a>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

export async function renderDraftEditorView(container, draftId) {
  const templates = await api.getTemplates();
  const urlParams = new URLSearchParams(window.location.hash.split('?')[1]);
  const templateId = urlParams.get('templateId') || 'TPL-001';
  const tpl = templates.find(t => t.id === templateId) || templates[0];

  container.innerHTML = `
    <!-- Top Mandatory Banner: Always shows Draft - Needs Approval until approved -->
    <div style="background:var(--color-warning-bg); border:1px solid var(--color-warning-border); padding:10px 18px; border-radius:8px; margin-bottom:16px; display:flex; justify-content:space-between; align-items:center;">
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="font-size:16px;">✍️</span>
        <strong style="color:var(--color-warning-text); font-size:13px;">DRAFT – NEEDS APPROVAL</strong>
        <span style="font-size:12px; color:var(--color-warning-text);">This draft is unapproved. External release is strictly prohibited until lawyer sign-off.</span>
      </div>
      <div style="display:flex; gap:8px;">
        <button class="btn btn-secondary btn-sm" onclick="window.compareVersionsModal()">
          Compare Versions (v1.2 vs v1.0)
        </button>
        <button class="btn btn-primary btn-sm" onclick="window.submitDraftForApproval()">
          Send for Approval →
        </button>
      </div>
    </div>

    <!-- 3-Column Layout: Left Facts, Center Editor, Right Citations/Blanks -->
    <div style="display:grid; grid-template-columns: 260px 1fr 300px; gap:16px; height: calc(100vh - 180px);">
      <!-- Left Panel: Facts Used with SourceChips -->
      <div class="card" style="display:flex; flex-direction:column; overflow:hidden; padding:16px;">
        <div style="font-weight:700; font-size:13px; margin-bottom:12px; display:flex; align-items:center; justify-content:space-between;">
          <span>Facts Grounded</span>
          <span class="status-badge verified">Verified</span>
        </div>
        <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:10px; font-size:12px;">
          <div style="background:var(--bg-subtle); padding:10px; border-radius:6px; border:1px solid var(--border-subtle);">
            <div>• Registered Office: Level 14, Lower Parel, Mumbai</div>
            <div style="margin-top:4px;">${renderSourceChip('DOC-002', 'Form INC-22', 2)}</div>
          </div>
          <div style="background:var(--bg-subtle); padding:10px; border-radius:6px; border:1px solid var(--border-subtle);">
            <div>• Security Cheque Endorsement Memo dated Jan 2023</div>
            <div style="margin-top:4px;">${renderSourceChip('DOC-002', 'Cheque Endorsement', 1)}</div>
          </div>
          <div style="background:var(--bg-subtle); padding:10px; border-radius:6px; border:1px solid var(--border-subtle);">
            <div>• Freight credit note adjustment claim of ₹ 10 Lakhs</div>
            <div style="margin-top:4px;">${renderSourceChip('DOC-005', 'Reconciliation Statement', 4)}</div>
          </div>
        </div>
      </div>

      <!-- Center Panel: Rich-Text Editor -->
      <div class="card" style="display:flex; flex-direction:column; overflow:hidden; padding:20px;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px; padding-bottom:8px; border-bottom:1px solid var(--border-subtle);">
          <input type="text" id="draft-title-input" class="form-control" value="${tpl.name} — Matter M-2026-031" style="font-weight:700; font-size:15px; border:none; background:transparent; padding:0;" />
          <div style="display:flex; gap:8px;">
            <button class="btn btn-secondary btn-sm" onclick="window.exportDraft('pdf')">Export PDF (Watermarked)</button>
            <button class="btn btn-secondary btn-sm" onclick="window.exportDraft('docx')">Export Word</button>
          </div>
        </div>

        <textarea id="draft-content-area" class="form-control" style="flex:1; font-family:var(--font-mono); font-size:13px; line-height:1.7; padding:16px; border-radius:6px; resize:none;">${tpl.defaultContent}</textarea>
        
        <div style="margin-top:12px; display:flex; justify-content:space-between; align-items:center; font-size:11px; color:var(--text-tertiary);">
          <span>Auto-saved to local memory 1 minute ago.</span>
          <span>Draft Version: 1.2 (Unreleased)</span>
        </div>
      </div>

      <!-- Right Panel: Citations, Blanks & Comments -->
      <div class="card" style="display:flex; flex-direction:column; overflow:hidden; padding:16px;">
        <div class="tabs-nav" style="margin-bottom:12px;">
          <button class="tab-btn active" onclick="window.switchEditorTab('citations')">Citations</button>
          <button class="tab-btn" onclick="window.switchEditorTab('blanks')">Blanks (1)</button>
          <button class="tab-btn" onclick="window.switchEditorTab('comments')">Comments</button>
        </div>

        <div id="editor-right-tab" style="flex:1; overflow-y:auto; font-size:12px;">
          <!-- Citations Tab Default -->
          <div style="font-weight:700; margin-bottom:8px;">Verified Authorities In Pleading:</div>
          <div style="background:var(--bg-subtle); padding:10px; border-radius:6px; margin-bottom:8px; border:1px solid var(--border-subtle);">
            <div style="font-weight:600; color:var(--primary);">Central Bank of India v. Ravindra</div>
            <div style="font-size:11px; color:var(--text-muted);">(2002) 1 SCC 367 — Prohibition on penal interest compounding</div>
            <span class="status-badge verified" style="margin-top:4px;">Verified Citation</span>
          </div>
        </div>
      </div>
    </div>
  `;

  window.switchEditorTab = (tab) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    const target = document.getElementById('editor-right-tab');
    if (!target) return;

    if (tab === 'blanks') {
      target.innerHTML = `
        <div style="font-weight:700; margin-bottom:8px; color:var(--color-warning-text);">Unsupported Statements (Blanks):</div>
        <p style="font-size:11px; color:var(--text-muted); margin-bottom:10px;">Statements lacking document citation are kept blank and highlighted yellow to prevent ungrounded claims.</p>
        <div style="background:#FEF3C7; border:1px solid #FDE68A; padding:10px; border-radius:6px; color:#92400E; margin-bottom:8px;">
          <strong>[BLANK_STATEMENT_1]:</strong>
          <br>"Insert certified details of supply defect or credit note acknowledgment."
          <div style="margin-top:6px;"><button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Select evidence file from document drawer', 'info')">Link Evidence</button></div>
        </div>
      `;
    } else if (tab === 'comments') {
      target.innerHTML = `
        <div style="font-weight:700; margin-bottom:8px;">Counsel Comments:</div>
        <div style="padding:10px; background:var(--bg-subtle); border-radius:6px; margin-bottom:8px;">
          <div style="font-weight:600;">Ananya Deshmukh (Lawyer)</div>
          <div style="color:var(--text-muted); margin-top:2px;">Ensure we cite paragraph 3 of the invoice receipt showing freight damage.</div>
        </div>
      `;
    } else {
      renderDraftEditorView(container, draftId);
    }
  };

  window.submitDraftForApproval = () => {
    window.MeridianApp.showToast('Draft submitted to Approvals Inbox for Lawyer verification.', 'success');
  };

  window.exportDraft = (format) => {
    window.MeridianApp.showToast(`Exporting ${format.toUpperCase()} with mandatory "DRAFT - NOT FOR CIRCULATION" watermark.`, 'info');
  };

  window.compareVersionsModal = () => {
    alert("Version Comparison: v1.2 incorporates RBI 2023 circular citation and corrects cheque date from 14 May to 12 May 2026.");
  };
}
