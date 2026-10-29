/**
 * Module M15: Knowledge Hub, Stored Enterprise Facts, Outside Lookup Privacy Log, Review Dates
 * Routes: /knowledge, /knowledge/lookups
 */
import { api } from '../services/api.js';
import { renderStatusBadge, renderSourceChip, renderTableSkeleton } from '../components/shared.js';
import { formatDate } from '../formatters.js';

let activeKnowledgeTab = 'browser'; // 'browser' | 'lookups' | 'review'

export async function renderKnowledgeView(container) {
  const [facts, lookups] = await Promise.all([
    api.getKnowledgeFacts(),
    api.getOutsideLookups()
  ]);

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Intelligence</span>
        <span class="breadcrumb-separator">/</span>
        <span>Knowledge Hub</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Enterprise Knowledge Hub & Privacy Vault</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Repository of indexed facts, verified legal rules, and external lookup redaction audits.
          </p>
        </div>
      </div>
    </div>

    <!-- Info Banner (Section 15 Specification) -->
    <div style="background:var(--color-info-bg); border:1px solid var(--color-info-border); padding:12px 18px; border-radius:8px; margin-bottom:20px; font-size:13px; color:var(--color-info-text); display:flex; align-items:center; gap:10px;">
      <span style="font-size:18px;">💡</span>
      <div>
        <strong>Privacy & Cost Optimization Architecture:</strong> Stored enterprise answers are cached and reused across sessions. Outside legal and court API lookups are rare, sanitized, and cost significantly less.
      </div>
    </div>

    <!-- Sub-Tabs: Knowledge Browser, Outside Lookup Log, Review Dates -->
    <div class="tabs-nav">
      <button class="tab-btn ${activeKnowledgeTab === 'browser' ? 'active' : ''}" onclick="window.setKbTab('browser')">Stored Knowledge Browser (${facts.length})</button>
      <button class="tab-btn ${activeKnowledgeTab === 'lookups' ? 'active' : ''}" onclick="window.setKbTab('lookups')">Outside Lookup Redaction Log (${lookups.length})</button>
      <button class="tab-btn ${activeKnowledgeTab === 'review' ? 'active' : ''}" onclick="window.setKbTab('review')">Facts Nearing Expiry (2)</button>
    </div>

    <div id="knowledge-tab-content">
      ${renderKnowledgeBrowser(facts)}
    </div>
  `;

  window.setKbTab = (tab) => {
    activeKnowledgeTab = tab;
    const target = document.getElementById('knowledge-tab-content');
    if (!target) return;

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    if (tab === 'browser') {
      target.innerHTML = renderKnowledgeBrowser(facts);
    } else if (tab === 'lookups') {
      target.innerHTML = renderOutsideLookupsView(target, lookups);
    } else if (tab === 'review') {
      target.innerHTML = renderReviewDatesTab(facts);
    }
  };
}

function renderKnowledgeBrowser(facts) {
  return `
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" placeholder="Search stored legal facts..." />
        <div class="filter-chip-group">
          <span class="filter-chip active">All Topics</span>
          <span class="filter-chip">Banking Law</span>
          <span class="filter-chip">Land Regulations</span>
          <span class="filter-chip">Tax Rules</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Topic & Category</th>
            <th>Stored Enterprise Fact</th>
            <th>Primary Source</th>
            <th>Times Reused</th>
            <th>Review Date</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${facts.map(f => `
            <tr>
              <td>
                <div style="font-weight:700; color:var(--text-main);">${f.topic}</div>
                <div style="font-size:11px; color:var(--text-tertiary);">${f.category}</div>
              </td>
              <td style="font-size:13px; max-width:440px; line-height:1.6;">${f.storedFact}</td>
              <td><span style="font-size:12px;">${f.source}</span></td>
              <td class="tabular-nums" style="font-weight:600; color:var(--primary);">${f.usageCount} times</td>
              <td>${formatDate(f.reviewDate)}</td>
              <td>${renderStatusBadge(f.status)}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export function renderOutsideLookupsView(target, lookups) {
  return `
    <div class="card">
      <div style="margin-bottom:16px;">
        <h3 style="font-size:15px; font-weight:700;">Outside API Query Sanitization Audit</h3>
        <p style="font-size:12px; color:var(--text-muted); margin-top:2px;">
          Verification log ensuring that no confidential company names, loan amounts, PANs, or case numbers were ever dispatched to external search engines or public AI models.
        </p>
      </div>
      <div style="display:flex; flex-direction:column; gap:16px;">
        ${lookups.map(l => `
          <div style="border:1px solid var(--border-subtle); border-radius:8px; padding:16px; background:var(--bg-subtle);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span class="status-badge verified">✓ Private Details Redacted</span>
                <strong style="font-size:13px;">${l.externalSourceUsed}</strong>
              </div>
              <span style="font-size:11px; color:var(--text-tertiary);">${l.timestamp}</span>
            </div>

            <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px; margin:10px 0;">
              <div style="background:#FFFFFF; border:1px solid var(--border-subtle); padding:10px; border-radius:6px;">
                <div style="font-size:10px; font-weight:700; color:var(--text-tertiary); text-transform:uppercase;">Originating Query (Internal Context)</div>
                <div style="font-size:12px; color:var(--text-main); margin-top:4px;">${l.rawQueryOrigin}</div>
              </div>
              <div style="background:#F0FDF4; border:1px solid #BBF7D0; padding:10px; border-radius:6px;">
                <div style="font-size:10px; font-weight:700; color:#15803D; text-transform:uppercase;">Sanitized External Query Sent Out</div>
                <div style="font-size:12px; color:#166534; font-weight:500; margin-top:4px;">${l.cleanedQuerySent}</div>
              </div>
            </div>

            <div style="font-size:11px; color:var(--text-muted); line-height:1.5;">
              🔒 <strong>Redaction Certificate:</strong> ${l.privateDetailsRemovedNote}
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

function renderReviewDatesTab(facts) {
  const expiring = facts.filter(f => f.status === 'Review Due Soon');

  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">Facts Nearing Statutory Expiry</h3>
      <p style="font-size:12px; color:var(--text-muted); margin-bottom:16px;">
        To prevent reliance on stale case law or superseded circulars, stored knowledge triggers mandatory periodic human reviews.
      </p>
      <div style="display:flex; flex-direction:column; gap:12px;">
        ${expiring.map(e => `
          <div style="padding:16px; border:1px solid var(--color-warning-border); background:var(--color-warning-bg); border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
            <div>
              <strong style="color:var(--color-warning-text); font-size:14px;">${e.topic}</strong>
              <div style="font-size:12px; color:var(--text-main); margin:4px 0;">${e.storedFact}</div>
              <div style="font-size:11px; color:var(--text-muted);">Scheduled Review Date: <strong>${formatDate(e.reviewDate)}</strong></div>
            </div>
            <div style="display:flex; gap:8px;">
              <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Fact kept as-is for 6 more months.', 'info')">Keep As Is</button>
              <button class="btn btn-primary btn-sm" onclick="window.MeridianApp.showToast('Fact re-verified against latest official gazette.', 'success')">Refresh Fact</button>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}
