/**
 * Module M2: Home and Ask Box
 * Routes: /home, /ask
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderAsOfStamp, renderAIGeneratedTag, renderNotFoundState } from '../components/shared.js';
import { formatDate } from '../formatters.js';

export async function renderHomeView(container) {
  const user = state.currentUser || { name: 'Rajesh Sharma', role: state.currentRole };

  // Fetch KPI & list data via Service Layer
  const [approvals, tasks, notifications, docs] = await Promise.all([
    api.getApprovals(),
    api.getCalendarTasks(),
    api.getNotifications(),
    api.getDocuments()
  ]);

  const urgentTasks = tasks.filter(t => t.daysLeft <= 9);
  const pendingApprovals = approvals.filter(a => a.status === 'Pending');
  const unreviewedDocs = docs.filter(d => d.status === 'Unreviewed');
  const unackAlerts = notifications.filter(n => !n.acknowledged);

  container.innerHTML = `
    <div class="home-container">
      <!-- 1. Greeting, Role & AsOfStamp -->
      <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom: 24px; flex-wrap: wrap; gap: 8px;">
        <div>
          <h1 style="font-size: var(--font-size-2xl); font-weight: 700; color: var(--text-main); letter-spacing:-0.02em;">
            Good afternoon, ${user.name}
          </h1>
          <div style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Active Role: <strong style="color:var(--primary);">${state.currentRole}</strong> • Session security level: Enterprise High
          </div>
        </div>
        <div>
          ${renderAsOfStamp('28 Oct 2026, 14:30 IST')}
        </div>
      </div>

      <!-- 2. Large Ask Box with Example Chips -->
      <div class="card" style="background: linear-gradient(180deg, var(--bg-surface) 0%, var(--bg-subtle) 100%); border: 1px solid var(--border-subtle); padding: 24px; margin-bottom: 24px;">
        <div style="font-size: var(--font-size-sm); font-weight: 600; color: var(--text-main); margin-bottom: 8px; display:flex; align-items:center; gap:8px;">
          <span>✨ Private Enterprise Knowledge Assistant</span>
          ${renderAIGeneratedTag('Verified Sources Only')}
        </div>
        <div style="position:relative;">
          <input type="text" id="home-ask-input" class="form-control" style="padding: 14px 18px; font-size: 15px; border-radius: var(--radius-lg); background: var(--bg-surface);" placeholder="Ask anything about your companies, loans, land parcels, court cases or tax notices..." />
          <button type="button" class="btn btn-primary" style="position:absolute; right:6px; top:6px; bottom:6px;" onclick="window.submitHomeAsk()">
            Ask Intelligence →
          </button>
        </div>
        <div style="display:flex; align-items:center; gap:8px; margin-top:12px; flex-wrap:wrap;">
          <span style="font-size:11px; font-weight:600; color:var(--text-tertiary);">SUGGESTIONS:</span>
          <button type="button" class="filter-chip" onclick="window.fillAsk('Which land parcels are currently mortgaged?')">Which parcels are mortgaged?</button>
          <button type="button" class="filter-chip" onclick="window.fillAsk('What are the upcoming statutory deadlines due in 7 days?')">What is due this week?</button>
          <button type="button" class="filter-chip" onclick="window.fillAsk('Summarize the DRT proceeding claim by Northern National Bank')">DRT Northern National Bank claim?</button>
          <button type="button" class="filter-chip" onclick="window.fillAsk('What is the GST demand status for Meridian Realty?')">Meridian Realty GST demand</button>
        </div>
      </div>

      <!-- 3. Four KPI Cards (All Clickable) -->
      <div class="kpi-grid">
        <div class="kpi-card" onclick="window.location.hash='#/calendar'">
          <div class="kpi-label">
            <span>Deadlines in 7 Days</span>
            <span>📅</span>
          </div>
          <div class="kpi-value amount" style="color:var(--color-danger);">${urgentTasks.length}</div>
          <div class="kpi-sub">Upcoming statutory hearings & filings</div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/approvals'">
          <div class="kpi-label">
            <span>Pending Approvals</span>
            <span>✍️</span>
          </div>
          <div class="kpi-value amount" style="color:var(--color-warning);">${pendingApprovals.length}</div>
          <div class="kpi-sub">Settlements, drafts, and extracted fields</div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/documents/queue'">
          <div class="kpi-label">
            <span>New Documents to Verify</span>
            <span>📄</span>
          </div>
          <div class="kpi-value amount">${unreviewedDocs.length}</div>
          <div class="kpi-sub">OCR fields waiting human verification</div>
        </div>

        <div class="kpi-card" onclick="window.location.hash='#/notifications'">
          <div class="kpi-label">
            <span>Unacknowledged Alerts</span>
            <span>🔔</span>
          </div>
          <div class="kpi-value amount" style="color:var(--color-danger);">${unackAlerts.length}</div>
          <div class="kpi-sub">Active in voice & SMS escalation ladder</div>
        </div>
      </div>

      <!-- 4. Two Columns: Today's Deadlines & Pending Approvals -->
      <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px; margin-bottom:24px;">
        <!-- Left: Today's / Urgent Deadlines -->
        <div class="card" style="margin-bottom:0;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <h3 style="font-size:15px; font-weight:700;">Critical Deadlines</h3>
            <a href="#/calendar" style="font-size:12px; font-weight:600;">View Calendar →</a>
          </div>
          <div style="display:flex; flex-direction:column; gap:12px;">
            ${urgentTasks.slice(0, 4).map(t => `
              <div style="padding:12px; border:1px solid var(--border-subtle); border-radius:var(--radius-md); background:var(--bg-subtle); display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <div style="font-weight:600; font-size:13px; color:var(--text-main);">${t.title}</div>
                  <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
                    ${t.companyName} • Due: <strong>${formatDate(t.dueDate)}</strong>
                    ${renderSourceChip(t.sourceDocId, t.sourceDocName, t.sourcePage)}
                  </div>
                </div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <span class="status-badge ${t.daysLeft <= 7 ? 'rejected' : 'needs-approval'}">${t.daysLeft <= 0 ? 'Overdue' : t.daysLeft + ' days left'}</span>
                  <button class="btn btn-secondary btn-sm" onclick="window.acknowledgeTask('${t.id}')">
                    ${t.acknowledged ? '✓ Ack' : 'Acknowledge'}
                  </button>
                </div>
              </div>
            `).join('')}
          </div>
        </div>

        <!-- Right: Pending Approvals -->
        <div class="card" style="margin-bottom:0;">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
            <h3 style="font-size:15px; font-weight:700;">Pending Approvals</h3>
            <a href="#/approvals" style="font-size:12px; font-weight:600;">Open Inbox (${pendingApprovals.length}) →</a>
          </div>
          <div style="display:flex; flex-direction:column; gap:12px;">
            ${pendingApprovals.slice(0, 4).map(a => `
              <div style="padding:12px; border:1px solid var(--border-subtle); border-radius:var(--radius-md); background:var(--bg-subtle); display:flex; justify-content:space-between; align-items:center;">
                <div>
                  <div style="display:flex; align-items:center; gap:6px;">
                    <span class="status-badge calculated">${a.type}</span>
                    <strong style="font-size:13px; color:var(--text-main);">${a.title}</strong>
                  </div>
                  <div style="font-size:11px; color:var(--text-muted); margin-top:4px;">
                    Requested by <strong>${a.requestedBy}</strong> • Age: ${a.age}
                    ${renderSourceChip(a.sourceDocId, a.sourceDocName, a.sourcePage)}
                  </div>
                </div>
                <a href="#/approvals/${a.id}" class="btn btn-primary btn-sm">Review</a>
              </div>
            `).join('')}
          </div>
        </div>
      </div>

      <!-- 5. Daily Summary Card in Plain Language with AIGeneratedTag & Sources -->
      <div class="card" style="border-left: 4px solid var(--primary);">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:16px;">📋</span>
            <h3 style="font-size:15px; font-weight:700;">Executive Daily Briefing</h3>
            ${renderAIGeneratedTag('Synthesized from 40 Enterprise Records')}
          </div>
          <span style="font-size:11px; color:var(--text-tertiary);">Generated today at 08:00 AM IST</span>
        </div>
        <p style="font-size:13px; line-height:1.7; color:var(--text-muted); margin-bottom:12px;">
          The group holds <strong>8 parcels spanning 164.6 acres</strong> across Maharashtra and Karnataka, of which 4 parcels remain encumbered by project finance charges. Northern National Bank's DRT claim of <strong>₹ 112.40 Cr</strong> ${renderSourceChip('DOC-013', 'NNB Demand Notice', 3)} requires priority attention prior to the cross-examination hearing on 12 Nov 2026. Separately, Coastal Finance Ltd exhibits an unreconciled discrepancy of <strong>₹ 3.50 Cr</strong> in penal compounding ${renderSourceChip('DOC-016', 'CFL Statement', 1)} which is legally contestable under recent RBI norms. In tax, GST Show Cause Notice DRC-01 demand of <strong>₹ 1.84 Cr</strong> for Meridian Realty is due for reply in 9 days ${renderSourceChip('DOC-005', 'DRC-01 SCN', 2)}.
        </p>
        <div style="display:flex; align-items:center; gap:8px; font-size:11px; color:var(--text-tertiary);">
          <span>Grounding Sources:</span>
          ${renderSourceChip('DOC-013', 'NNB Claim Notice', 3)}
          ${renderSourceChip('DOC-016', 'CFL Facility Statement', 1)}
          ${renderSourceChip('DOC-005', 'GST SCN FY22', 2)}
          ${renderSourceChip('DOC-027', 'Hinjewadi Conveyance Deed', 1)}
        </div>
      </div>
    </div>
  `;

  window.fillAsk = (q) => {
    const input = document.getElementById('home-ask-input');
    if (input) input.value = q;
  };

  window.submitHomeAsk = () => {
    const input = document.getElementById('home-ask-input');
    const query = input ? input.value.trim() : '';
    if (query) {
      sessionStorage.setItem('pending_ask_query', query);
      window.location.hash = '#/ask';
    }
  };

  window.acknowledgeTask = async (taskId) => {
    await api.acknowledgeTask(taskId);
    window.MeridianApp.showToast('Deadline acknowledged.', 'success');
    renderHomeView(container);
  };
}

export async function renderAskView(container) {
  const initialQuery = sessionStorage.getItem('pending_ask_query') || '';
  sessionStorage.removeItem('pending_ask_query');

  container.innerHTML = `
    <div style="display:grid; grid-template-columns: 280px 1fr; gap:24px; height: calc(100vh - 120px);">
      <!-- Left Rail: Question History & Saved Answers -->
      <div class="card" style="display:flex; flex-direction:column; overflow:hidden; padding:16px;">
        <div style="font-weight:700; font-size:14px; margin-bottom:12px; display:flex; justify-content:space-between; align-items:center;">
          <span>Inquiry History</span>
          <button type="button" class="btn btn-secondary btn-sm" onclick="window.newChatSession()">+ New</button>
        </div>
        <div style="flex:1; overflow-y:auto; display:flex; flex-direction:column; gap:8px;">
          <div class="filter-chip active" style="text-align:left; border-radius:6px; padding:8px 10px;" onclick="window.loadSavedAsk(1)">
            <div style="font-weight:600; font-size:12px;">Which parcels are mortgaged?</div>
            <div style="font-size:10px; color:var(--text-tertiary);">Saved • 28 Oct 2026</div>
          </div>
          <div class="filter-chip" style="text-align:left; border-radius:6px; padding:8px 10px;" onclick="window.loadSavedAsk(2)">
            <div style="font-weight:600; font-size:12px;">Northern National Bank DRT claim</div>
            <div style="font-size:10px; color:var(--text-tertiary);">Saved • 27 Oct 2026</div>
          </div>
          <div class="filter-chip" style="text-align:left; border-radius:6px; padding:8px 10px;" onclick="window.loadSavedAsk(3)">
            <div style="font-weight:600; font-size:12px;">Coastal Finance penal compounding</div>
            <div style="font-size:10px; color:var(--text-tertiary);">Saved • 26 Oct 2026</div>
          </div>
        </div>

        <div style="padding-top:12px; border-top:1px solid var(--border-subtle); font-size:11px; color:var(--text-tertiary);">
          🔒 Stored enterprise answers are reused from Knowledge Hub. Zero unredacted outside queries.
        </div>
      </div>

      <!-- Right Main Chat Area -->
      <div class="card" style="display:flex; flex-direction:column; overflow:hidden; padding:20px;">
        <!-- Chat Message Log -->
        <div id="ask-chat-log" style="flex:1; overflow-y:auto; padding-right:8px; display:flex; flex-direction:column; gap:20px;">
          <!-- Welcome Prompt -->
          <div style="background:var(--bg-subtle); padding:16px; border-radius:12px; border:1px solid var(--border-subtle);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
              <span style="font-size:18px;">✨</span>
              <strong style="font-size:14px;">Meridian Grounded Intelligence</strong>
              ${renderAIGeneratedTag('Strict No Source, No Fact Policy')}
            </div>
            <p style="font-size:13px; color:var(--text-muted); line-height:1.6;">
              I can answer specific inquiries regarding group companies, loans, mortgages, title chains, court cases, and tax matters. Every fact and number includes a clickable <strong>SourceChip</strong> that opens the exact page in the Document Viewer. Guessed or unverified data is never displayed.
            </p>
          </div>
        </div>

        <!-- Chat Input Bar -->
        <div style="padding-top:16px; border-top:1px solid var(--border-subtle);">
          <div style="display:flex; gap:8px;">
            <input type="text" id="ask-input-box" class="form-control" placeholder="Type your inquiry here (e.g., 'What is the sanctioned interest rate on LN-001?')..." value="${initialQuery}" onkeydown="if(event.key==='Enter') window.executeAskQuery()" />
            <button type="button" class="btn btn-primary" onclick="window.executeAskQuery()">
              Send →
            </button>
          </div>
        </div>
      </div>
    </div>
  `;

  window.executeAskQuery = async () => {
    const input = document.getElementById('ask-input-box');
    const q = input?.value.trim();
    if (!q) return;

    input.value = '';
    const log = document.getElementById('ask-chat-log');

    // Append user message bubble
    const userMsg = document.createElement('div');
    userMsg.style.cssText = 'align-self: flex-end; background: var(--primary); color: #fff; padding: 10px 16px; border-radius: 12px 12px 2px 12px; max-width: 80%; font-size: 14px;';
    userMsg.textContent = q;
    log.appendChild(userMsg);
    log.scrollTop = log.scrollHeight;

    // Show typing indicator
    const typingEl = document.createElement('div');
    typingEl.id = 'typing-indicator';
    typingEl.style.cssText = 'align-self: flex-start; background: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 12px 18px; border-radius: 12px 12px 12px 2px; font-size: 13px; color: var(--text-muted); display:flex; align-items:center; gap:8px;';
    typingEl.innerHTML = '<span style="animation:pulse 1.2s infinite;">⏳</span> Routing through agents — thinking…';
    log.appendChild(typingEl);
    log.scrollTop = log.scrollHeight;

    try {
      const result = await api.askAI(q);
      typingEl.remove();
      await renderAIAnswer(log, q, result);
    } catch (err) {
      typingEl.remove();
      const errEl = document.createElement('div');
      errEl.style.cssText = 'align-self: flex-start; background: var(--bg-surface); border: 1px solid var(--color-danger); padding: 14px 18px; border-radius: 12px; font-size: 13px; color: var(--color-danger); max-width:90%;';
      errEl.innerHTML = `⚠️ <strong>Agent Error:</strong> ${err.message || 'Could not reach the backend. Make sure the server is running.'}`;
      log.appendChild(errEl);
      log.scrollTop = log.scrollHeight;
    }
  };

  if (initialQuery) {
    window.executeAskQuery();
  }

  window.loadSavedAsk = (idx) => {
    const input = document.getElementById('ask-input-box');
    const queries = [
      'Which land parcels are currently mortgaged?',
      'Summarize Northern National Bank DRT claim',
      'Explain Coastal Finance penal interest calculation'
    ];
    if (input && queries[idx - 1]) {
      input.value = queries[idx - 1];
      window.executeAskQuery();
    }
  };

  window.newChatSession = () => {
    renderAskView(container);
  };
}

async function renderAIAnswer(log, query, result) {
  const answerContainer = document.createElement('div');
  answerContainer.style.cssText = 'align-self: flex-start; background: var(--bg-surface); border: 1px solid var(--border-subtle); padding: 18px; border-radius: 12px 12px 12px 2px; max-width: 90%; box-shadow: var(--shadow-sm);';

  const answer = result?.answer || '';
  const status = result?.status || 'ok';
  const sources = result?.sources || [];
  const latency = result?.latency_ms ? `${(result.latency_ms / 1000).toFixed(1)}s` : '';

  // No answer fallback
  if (!answer || answer.trim() === '' || answer.includes('No specialist agent produced an answer')) {
    answerContainer.innerHTML = renderNotFoundState(
      'No Verified Record Found',
      `The knowledge base does not contain verified citations for "${query}". Try asking about parcels, loans, matters, tax notices, or company records.`
    );
    log.appendChild(answerContainer);
    log.scrollTop = log.scrollHeight;
    return;
  }

  const needsApproval = status === 'needs_approval';
  const sourcesHtml = sources.length > 0
    ? `<div style="background:var(--bg-subtle); padding:10px 14px; border-radius:8px; border:1px solid var(--border-subtle); margin-bottom:14px;">
        <div style="font-size:11px; font-weight:700; color:var(--text-muted); text-transform:uppercase; margin-bottom:6px;">Sources (${sources.length})</div>
        <div style="display:flex; flex-wrap:wrap; gap:6px;">
          ${sources.map(s => renderSourceChip(s, s, 1)).join('')}
        </div>
       </div>`
    : '';

  answerContainer.innerHTML = `
    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
      <div style="display:flex; align-items:center; gap:8px;">
        <span style="font-size:16px;">${needsApproval ? '⏳' : '✨'}</span>
        <strong style="font-size:13px; color:var(--text-main);">${needsApproval ? 'Pending Approval' : 'Agent Response'}</strong>
        ${renderAIGeneratedTag(latency ? `via llama3 · ${latency}` : 'Local LLM')}
      </div>
      <button class="btn btn-secondary btn-sm" onclick="navigator.clipboard.writeText(this.closest('div').nextElementSibling?.textContent || ''); window.MeridianApp?.showToast('Copied', 'info');">Copy</button>
    </div>
    <div style="font-size:13px; line-height:1.7; color:var(--text-main); white-space:pre-wrap; margin-bottom:14px;">${answer}</div>
    ${sourcesHtml}
    ${needsApproval ? `<div style="background:#FEF3C7; border:1px solid #FCD34D; padding:10px 14px; border-radius:8px; font-size:12px; color:#92400E;">⏳ This response requires human approval before it can be used.</div>` : ''}
  `;

  log.appendChild(answerContainer);
  log.scrollTop = log.scrollHeight;
}
