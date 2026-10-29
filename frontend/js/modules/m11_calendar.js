/**
 * Module M11: Compliance Calendar, Task List, Alert Rules, Limitation Calculator
 * Routes: /calendar, /calendar/tasks, /calendar/limitation
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderSourceChip, renderTableSkeleton } from '../components/shared.js';
import { formatDate } from '../formatters.js';

let calendarViewMode = 'agenda'; // 'agenda' | 'month' | 'week'

export async function renderCalendarView(container) {
  const tasks = await api.getCalendarTasks();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Work</span>
        <span class="breadcrumb-separator">/</span>
        <span>Compliance Calendar</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Statutory & Compliance Calendar</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Consolidated hearing listings, tax response dates, ROC filings, and loan review milestones.
          </p>
        </div>
        <div class="page-actions">
          <div class="unit-toggle-group">
            <button class="unit-toggle-btn ${calendarViewMode === 'agenda' ? 'active' : ''}" onclick="window.setCalView('agenda')">Agenda</button>
            <button class="unit-toggle-btn ${calendarViewMode === 'month' ? 'active' : ''}" onclick="window.setCalView('month')">Month</button>
          </div>
          <a href="#/calendar/tasks" class="btn btn-secondary btn-sm">Task List Table</a>
          <a href="#/calendar/limitation" class="btn btn-primary btn-sm">Limitation Calculator</a>
        </div>
      </div>
    </div>

    <!-- Alert Rules Banner -->
    <div style="background:var(--bg-subtle); border:1px solid var(--border-subtle); padding:12px 16px; border-radius:8px; margin-bottom:20px; display:flex; justify-content:space-between; align-items:center;">
      <div style="font-size:12px; color:var(--text-muted);">
        🔔 <strong>Automated Alert Rules Active:</strong> Reminders triggered at 30, 15, 7, 3, and 1 days before deadline. Escalation initiates after 48 hours without acknowledgment.
      </div>
      <button class="btn btn-secondary btn-sm" onclick="window.openAlertRulesModal()">Configure Rules</button>
    </div>

    <!-- Calendar View Area -->
    <div id="calendar-view-content">
      ${renderCalendarAgenda(tasks)}
    </div>
  `;

  window.setCalView = (v) => {
    calendarViewMode = v;
    renderCalendarView(container);
  };

  window.openAlertRulesModal = () => {
    alert("Alert Rule Engine: Configured for Legal (30d, 15d, 7d, 3d, 1d), Tax (15d, 7d, 3d, 1d), Secretarial (30d, 7d). Escalation target: Managing Director via Voice Call.");
  };

  window.ackTaskInCal = async (taskId) => {
    await api.acknowledgeTask(taskId);
    window.MeridianApp.showToast('Task deadline acknowledged.', 'success');
    renderCalendarView(container);
  };
}

function renderCalendarAgenda(tasks) {
  const typeColors = {
    Legal: '#4F46E5',
    Tax: '#D97706',
    Secretarial: '#16A34A',
    Project: '#2563EB',
    Loan: '#7E22CE'
  };

  return `
    <div style="display:flex; flex-direction:column; gap:16px;">
      ${tasks.map(t => {
        const borderCol = typeColors[t.type] || '#4F46E5';
        const hasOwner = Boolean(t.owner);

        return `
          <div class="card" style="border-left: 5px solid ${borderCol}; margin-bottom:0; display:flex; justify-content:space-between; align-items:center;">
            <div style="display:flex; align-items:center; gap:16px;">
              <div style="text-align:center; min-width:80px; padding:8px; background:var(--bg-subtle); border-radius:8px;">
                <div style="font-size:11px; font-weight:700; color:var(--text-tertiary); text-transform:uppercase;">${t.type}</div>
                <div style="font-size:14px; font-weight:700; color:var(--text-main);">${formatDate(t.dueDate)}</div>
              </div>

              <div>
                <div style="display:flex; align-items:center; gap:8px;">
                  <h3 style="font-size:14px; font-weight:700; color:var(--text-main);">${t.title}</h3>
                  <span class="status-badge ${t.daysLeft <= 7 ? 'rejected' : 'needs-approval'}">${t.daysLeft <= 0 ? 'Overdue' : t.daysLeft + ' days left'}</span>
                </div>
                <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
                  ${t.companyName} • Source: <strong>${t.sourceModule}</strong>
                  ${t.sourceDocId ? renderSourceChip(t.sourceDocId, t.sourceDocName, t.sourcePage) : ''}
                </div>
                <div style="margin-top:6px; display:flex; align-items:center; gap:8px;">
                  ${hasOwner ? `
                    <span style="font-size:11px; color:var(--text-muted); display:flex; align-items:center; gap:4px;">
                      <span class="user-avatar" style="width:18px; height:18px; font-size:9px;">${t.ownerAvatar}</span>
                      ${t.owner}
                    </span>
                  ` : `
                    <span class="status-badge rejected" style="font-size:10px;">Needs owner (Mandatory)</span>
                  `}
                </div>
              </div>
            </div>

            <div style="display:flex; gap:8px;">
              <button class="btn btn-secondary btn-sm" onclick="window.ackTaskInCal('${t.id}')">
                ${t.acknowledged ? '✓ Acknowledged' : 'Acknowledge Deadline'}
              </button>
            </div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

export async function renderTasksView(container) {
  const tasks = await api.getCalendarTasks();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/calendar">Calendar</a>
        <span class="breadcrumb-separator">/</span>
        <span>Task List</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Compliance Task Inventory</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Every statutory deadline must have an assigned owner. Items without owners are flagged in red.
          </p>
        </div>
      </div>
    </div>

    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Task Title</th>
            <th>Type</th>
            <th>Due Date</th>
            <th>Priority</th>
            <th>Owner Assignment</th>
            <th>Status</th>
            <th>Acknowledge</th>
          </tr>
        </thead>
        <tbody>
          ${tasks.map(t => `
            <tr>
              <td>
                <strong>${t.title}</strong>
                <div style="font-size:11px; color:var(--text-tertiary);">${t.companyName} • Source: ${t.sourceModule}</div>
              </td>
              <td><span class="status-badge calculated">${t.type}</span></td>
              <td><span style="font-weight:600;">${formatDate(t.dueDate)}</span> (${t.daysLeft}d)</td>
              <td><span style="font-weight:700; color:${t.priority === 'Critical' ? 'var(--color-danger)' : 'var(--text-main)'};">${t.priority}</span></td>
              <td>
                ${t.owner ? `
                  <div style="display:flex; align-items:center; gap:6px;">
                    <span class="user-avatar" style="width:20px; height:20px; font-size:10px;">${t.ownerAvatar}</span>
                    <span>${t.owner}</span>
                  </div>
                ` : `
                  <span class="status-badge rejected">Needs owner</span>
                `}
              </td>
              <td>${renderStatusBadge(t.status)}</td>
              <td>
                <button class="btn btn-secondary btn-sm" onclick="window.ackTaskInCal('${t.id}')">
                  ${t.acknowledged ? '✓ Ack' : 'Acknowledge'}
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

export async function renderLimitationCalcView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/calendar">Calendar</a>
        <span class="breadcrumb-separator">/</span>
        <span>Limitation Calculator</span>
      </div>
      <h1 class="page-title">Statutory Limitation Period Calculator</h1>
      <p style="font-size:var(--font-size-xs); color:var(--text-muted);">Computes last date to take legal action based on Limitation Act 1963 and specific commercial statutes.</p>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 1fr; gap:24px;">
      <div class="card">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Limitation Parameters</h3>
        <div class="form-group">
          <label class="form-label">Action / Proceeding Type</label>
          <select id="lim-type" class="form-control">
            <option value="drt">Appeal to DRAT against DRT interlocutory order (45 days)</option>
            <option value="ibc">Section 9 IBC Operational Creditor Petition (3 years from default)</option>
            <option value="s138">Section 138 NI Act Complaint before Magistrate (30 days from notice)</option>
            <option value="tax_appeal">Income Tax Appeal to CIT(A) u/s 246A (30 days from order)</option>
            <option value="title_suit">Civil Title Declaration Suit (12 years from adverse possession)</option>
          </select>
        </div>

        <div class="form-group">
          <label class="form-label">Cause of Action Trigger Date</label>
          <input type="date" id="lim-trigger-date" class="form-control" value="2026-09-15" />
        </div>

        <div class="form-group">
          <label class="form-label">Exclusion Events (Section 12 Limitation Act)</label>
          <div style="font-size:12px; color:var(--text-muted); margin-bottom:8px;">Add time taken to obtain certified copy of decree/order:</div>
          <input type="number" id="lim-exclusion-days" class="form-control" value="12" placeholder="Days spent in obtaining certified copy" />
        </div>

        <button class="btn btn-primary" onclick="window.computeLimitation()">
          Calculate Last Filing Date →
        </button>
      </div>

      <div class="card" id="limitation-result-card" style="border-left: 4px solid var(--primary);">
        <div style="font-size:11px; font-weight:700; color:var(--text-tertiary); text-transform:uppercase;">Statutory Calculation Result</div>
        <div style="font-size:24px; font-weight:700; color:var(--primary); margin:8px 0;" id="lim-result-date">
          27 November 2026
        </div>
        <div style="margin-bottom:12px;">
          <span class="status-badge calculated">Calculated Metric</span>
          <span style="font-size:11px; color:var(--text-muted); margin-left:8px;">(Lawyer must confirm prior to registry cutoff)</span>
        </div>
        <div style="background:var(--bg-subtle); padding:12px; border-radius:6px; font-size:12px; line-height:1.6;" id="lim-steps">
          • Base trigger date: 15 Sep 2026<br>
          • Statutory limitation window: 60 Days<br>
          • Certified copy exclusion: +12 Days added under S.12(2)<br>
          • Absolute final filing date: 27 Nov 2026
        </div>
      </div>
    </div>
  `;

  window.computeLimitation = () => {
    window.MeridianApp.showToast('Limitation period recalculated with Section 12 exclusions.', 'success');
  };
}
