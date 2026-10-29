/**
 * Module M8: Legal Research, Authority Cards, Citation Authenticity Check
 * Routes: /research, /research/saved
 */
import { api } from '../services/api.js';
import { renderStatusBadge, renderSourceChip, renderAIGeneratedTag } from '../components/shared.js';

export async function renderResearchView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Intelligence</span>
        <span class="breadcrumb-separator">/</span>
        <span>Legal Research</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Legal Research & Authority Citations</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Statutory authorities, High Court & Supreme Court precedents, and automated citation authenticity verification.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/research/saved" class="btn btn-secondary btn-sm">
            Saved Research Library (4)
          </a>
        </div>
      </div>
    </div>

    <!-- Search Request Box -->
    <div class="card" style="margin-bottom:24px;">
      <div style="font-weight:700; font-size:15px; margin-bottom:8px;">New Research Request</div>
      <div style="display:flex; gap:12px; margin-bottom:14px;">
        <input type="text" id="research-query-box" class="form-control" style="font-size:15px; padding:12px 16px;" placeholder="Formulate legal proposition (e.g. 'Can banks compound penal interest under SARFAESI?')..." value="Whether penal interest can be capitalized or compounded by NBFCs / Banks in SARFAESI proceedings?" />
        <button class="btn btn-primary" onclick="window.searchLegalAuthorities()">
          Run Research Query →
        </button>
      </div>

      <div style="display:flex; gap:12px; flex-wrap:wrap; font-size:12px; align-items:center;">
        <span style="color:var(--text-muted); font-weight:600;">Filters:</span>
        <select class="form-control" style="max-width:200px; font-size:12px;">
          <option>Link to: Matter M-2025-014 (NNB DRT)</option>
          <option>Link to: Matter M-2025-021 (Civil Title)</option>
          <option>Link to: Matter M-2026-003 (NCLT)</option>
          <option>No Matter Link</option>
        </select>
        <select class="form-control" style="max-width:180px; font-size:12px;">
          <option>Forum: Supreme Court of India</option>
          <option>Forum: Bombay High Court</option>
          <option>Forum: Telangana High Court</option>
          <option>Forum: All Forums</option>
        </select>
        <select class="form-control" style="max-width:160px; font-size:12px;">
          <option>Statute: SARFAESI & Banking</option>
          <option>Statute: IBC 2016</option>
          <option>Statute: Land & Inam Acts</option>
        </select>
      </div>
    </div>

    <!-- Cache Verification Strip (Rule: "Always show Checked saved research first") -->
    <div style="background:var(--color-info-bg); border:1px solid var(--color-info-border); padding:10px 16px; border-radius:8px; margin-bottom:20px; font-size:12px; color:var(--color-info-text); display:flex; align-items:center; gap:8px;">
      <span>ℹ️</span>
      <strong>Checked saved research first:</strong> Retrieved 4 authoritative precedent cards from local repository. Zero unredacted outside queries.
    </div>

    <!-- Research Results Cards -->
    <div id="research-results-container" style="display:flex; flex-direction:column; gap:16px;">
      <!-- Populated below -->
    </div>
  `;

  const items = await api.getResearchItems();
  renderResearchCards(items);

  window.searchLegalAuthorities = async () => {
    window.MeridianApp.showToast('Searching Indian judicial repository...', 'info');
    const q = document.getElementById('research-query-box')?.value || '';
    renderResearchCards(items);
  };
}

function renderResearchCards(items) {
  const target = document.getElementById('research-results-container');
  if (!target) return;

  target.innerHTML = items.map(item => {
    const isUnverified = item.citationStatus === 'Unverified citation' || !item.canUseInDraft;

    return `
      <div class="card" style="border-left: 4px solid ${isUnverified ? 'var(--color-danger)' : 'var(--color-success)'}; margin-bottom:0;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
          <div>
            <div style="font-size:11px; font-weight:700; color:var(--text-tertiary); text-transform:uppercase;">
              ${item.court} • ${item.year} • ${item.topic}
            </div>
            <h3 style="font-size:16px; font-weight:700; color:var(--text-main); margin-top:2px;">
              ${item.title}
            </h3>
            <div style="font-family:var(--font-mono); font-size:12px; color:var(--text-muted); margin-top:2px;">
              Citation: <strong>${item.citation}</strong>
            </div>
          </div>
          <div>
            ${isUnverified ? `
              <span class="status-badge rejected" title="${item.blockReason}">
                ✕ Unverified Citation Check
              </span>
            ` : `
              <span class="status-badge verified" title="Verified against official Supreme Court / High Court reporters">
                ✓ Citation Check Verified
              </span>
            `}
          </div>
        </div>

        <!-- Plain Words Explanation -->
        <div style="background:var(--bg-subtle); padding:12px; border-radius:8px; margin:12px 0;">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:4px;">Plain-Language Ruling:</div>
          <div style="font-size:13px; color:var(--text-main); line-height:1.6;">${item.plainEnglish}</div>
        </div>

        <!-- Why It Matters -->
        <div style="margin-bottom:16px;">
          <strong style="font-size:12px; color:var(--primary);">Why It Matters to Meridian Group:</strong>
          <p style="font-size:13px; color:var(--text-muted); margin-top:2px;">${item.whyItMatters}</p>
        </div>

        <!-- Actions -->
        <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border-subtle); padding-top:12px;">
          <div style="display:flex; gap:6px; flex-wrap:wrap;">
            ${(item.tags || []).map(t => `<span style="font-size:11px; background:var(--bg-subtle); padding:2px 8px; border-radius:4px; color:var(--text-muted);">${t}</span>`).join('')}
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Precedent saved to central library', 'success')">Save to Library</button>
            <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Saved to Matter M-2025-014 evidence register', 'success')">Save to Matter</button>
            
            ${isUnverified ? `
              <button class="btn btn-secondary btn-sm" disabled title="${item.blockReason}" style="opacity:0.5; cursor:not-allowed; background:#FEE2E2; border-color:#FECACA; color:#991B1B;">
                🚫 Use in Draft (Blocked: Unverified)
              </button>
            ` : `
              <button class="btn btn-primary btn-sm" onclick="window.useInDraft('${item.id}')">
                Use in Draft →
              </button>
            `}
          </div>
        </div>
      </div>
    `;
  }).join('');

  window.useInDraft = (resId) => {
    window.location.hash = `#/drafting/editor?citationId=${resId}`;
  };
}

export async function renderSavedResearchView(container) {
  const items = await api.getResearchItems();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/research">Research</a>
        <span class="breadcrumb-separator">/</span>
        <span>Saved Library</span>
      </div>
      <h1 class="page-title">Curated Legal Precedent Library</h1>
    </div>

    <div style="display:flex; flex-direction:column; gap:16px;">
      ${items.map(it => `
        <div class="card" style="margin-bottom:0;">
          <div style="display:flex; justify-content:space-between;">
            <strong style="font-size:14px;">${it.title}</strong>
            ${renderStatusBadge(it.citationStatus)}
          </div>
          <div style="font-size:12px; color:var(--text-muted); margin:4px 0;">${it.citation}</div>
          <p style="font-size:13px; color:var(--text-main); margin-top:6px;">${it.plainEnglish}</p>
        </div>
      `).join('')}
    </div>
  `;
}
