/**
 * Module M12: Notifications, Escalation Ladder, Message Approval & Voice Alerts
 * Routes: /notifications, /notifications/messages, /notifications/calls
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderTableSkeleton } from '../components/shared.js';

export async function renderNotificationsView(container) {
  const notifs = await api.getNotifications();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Work</span>
        <span class="breadcrumb-separator">/</span>
        <span>Notifications</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Notification Centre & Escalation Engine</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Multi-channel statutory alerts with progressive escalation: App → Email → SMS/WhatsApp → Voice Call → Board.
          </p>
        </div>
        <div class="page-actions">
          <a href="#/notifications/calls" class="btn btn-secondary btn-sm">
            📞 Voice Call Log (3)
          </a>
          <a href="#/notifications/messages" class="btn btn-primary btn-sm">
            Voice Message Approval (1 Pending)
          </a>
        </div>
      </div>
    </div>

    <!-- Active Escalation Spotlight: Fast-Forward Demo Simulator (Section 8 Cross-module requirement) -->
    <div class="card" style="border: 2px solid var(--color-danger-border); background: var(--color-danger-bg); padding:20px; margin-bottom:24px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div style="display:flex; align-items:center; gap:8px;">
          <span style="font-size:22px;">⚡</span>
          <div>
            <h3 style="font-size:15px; font-weight:700; color:var(--color-danger-text);">Active Escalation Ladder: NOTIF-001 (DRT Hearing Notice)</h3>
            <div style="font-size:12px; color:var(--color-danger-text);">Unacknowledged for 48 hours. Progressive escalation engine is actively engaged.</div>
          </div>
        </div>
        <button class="btn btn-danger btn-sm" onclick="window.fastForwardEscalation('NOTIF-001')">
          ⚡ Fast-Forward Demo (Advance Step)
        </button>
      </div>

      <!-- Horizontal Step Tracker -->
      <div style="display:flex; justify-content:space-between; align-items:center; position:relative; max-width:800px; margin:20px auto 10px;">
        <div style="position:absolute; top:14px; left:40px; right:40px; height:3px; background:var(--border-strong); z-index:1;"></div>
        
        <div style="display:flex; flex-direction:column; align-items:center; z-index:2;">
          <div style="width:30px; height:30px; border-radius:50%; background:var(--color-success); color:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold;">✓</div>
          <span style="font-size:11px; font-weight:600; margin-top:4px;">1. App Alert</span>
          <span style="font-size:9px; color:var(--text-tertiary);">Delivered</span>
        </div>

        <div style="display:flex; flex-direction:column; align-items:center; z-index:2;">
          <div style="width:30px; height:30px; border-radius:50%; background:var(--color-success); color:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold;">✓</div>
          <span style="font-size:11px; font-weight:600; margin-top:4px;">2. Email</span>
          <span style="font-size:9px; color:var(--text-tertiary);">Opened</span>
        </div>

        <div style="display:flex; flex-direction:column; align-items:center; z-index:2;">
          <div style="width:30px; height:30px; border-radius:50%; background:var(--color-success); color:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold;">✓</div>
          <span style="font-size:11px; font-weight:600; margin-top:4px;">3. SMS / WhatsApp</span>
          <span style="font-size:9px; color:var(--text-tertiary);">Dispatched</span>
        </div>

        <div style="display:flex; flex-direction:column; align-items:center; z-index:2;">
          <div style="width:30px; height:30px; border-radius:50%; background:var(--primary); color:#fff; display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:bold; box-shadow:0 0 0 4px var(--primary-light);">4</div>
          <span style="font-size:11px; font-weight:700; color:var(--primary); margin-top:4px;">4. Voice Call (ACTIVE)</span>
          <span style="font-size:9px; color:var(--primary);">Pending Script Approval</span>
        </div>

        <div style="display:flex; flex-direction:column; align-items:center; z-index:2;">
          <div style="width:30px; height:30px; border-radius:50%; background:var(--bg-subtle); border:2px solid var(--border-strong); color:var(--text-muted); display:flex; align-items:center; justify-content:center; font-size:12px;">5</div>
          <span style="font-size:11px; color:var(--text-muted); margin-top:4px;">5. Board Escalation</span>
          <span style="font-size:9px; color:var(--text-tertiary);">Queued</span>
        </div>
      </div>
    </div>

    <!-- Notification Inbox -->
    <div class="table-container">
      <div class="table-toolbar">
        <div style="font-weight:700; font-size:13px;">Recent Alerts & Broadcasts</div>
        <div class="filter-chip-group">
          <span class="filter-chip active">All Alerts</span>
          <span class="filter-chip">Unacknowledged (2)</span>
          <span class="filter-chip">Escalated</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>Priority</th>
            <th>Type</th>
            <th>Message Summary</th>
            <th>Origin Module</th>
            <th>Timestamp</th>
            <th>Status</th>
            <th style="text-align:right;">Action</th>
          </tr>
        </thead>
        <tbody>
          ${notifs.map(n => `
            <tr>
              <td>
                <span class="status-badge ${n.priority === 'Urgent' ? 'rejected' : 'needs-approval'}">
                  ${n.priority}
                </span>
              </td>
              <td><strong>${n.type}</strong></td>
              <td>
                <div style="font-weight:600; color:var(--text-main);">${n.title}</div>
                <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">${n.message}</div>
              </td>
              <td>${n.module}</td>
              <td style="font-size:12px; color:var(--text-tertiary);">${n.timestamp}</td>
              <td>${renderStatusBadge(n.status)}</td>
              <td style="text-align:right;">
                <button class="btn btn-secondary btn-sm" onclick="window.ackNotif('${n.id}')">
                  ${n.acknowledged ? '✓ Ack' : 'Acknowledge'}
                </button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  window.ackNotif = async (nId) => {
    await api.acknowledgeNotification(nId);
    window.MeridianApp.showToast(`Alert ${nId} acknowledged. Escalation sequence halted.`, 'success');
    renderNotificationsView(container);
  };

  window.fastForwardEscalation = async (nId) => {
    await api.fastForwardNotification(nId);
    window.MeridianApp.showToast(`Fast-forwarded escalation step for ${nId}. Script queued in Message Approval.`, 'info');
    renderNotificationsView(container);
  };
}

export async function renderMessageApprovalView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/notifications">Notifications</a>
        <span class="breadcrumb-separator">/</span>
        <span>Voice Message Approval</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Automated Voice Message Script Approval</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Strict safety rule: <strong>Nothing is spoken without human approval.</strong> Review synthesized speech text prior to telephone dispatch.
          </p>
        </div>
      </div>
    </div>

    <div class="card" style="max-width:760px; margin:0 auto; padding:28px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <span class="status-badge attention">Awaiting Administrator Approval</span>
        <span style="font-size:12px; color:var(--text-muted);">Voice Notification Agent • Synthesized Speech</span>
      </div>

      <div class="form-group">
        <label class="form-label">Intended Recipient</label>
        <input type="text" class="form-control" value="Vikramaditya Singhania (Managing Director) • +91 98200 99887" readonly />
      </div>

      <div class="form-group">
        <label class="form-label">Speech Synthesis Language & Voice Model</label>
        <select class="form-control">
          <option>English (India) — Natural Enterprise Male (Aditya)</option>
          <option>Hindi (Standard) — Natural Enterprise Female (Pooja)</option>
        </select>
      </div>

      <div class="form-group">
        <label class="form-label">Exact Spoken Message Script (Editable)</label>
        <textarea id="voice-script-text" class="form-control" rows="5" style="font-size:13px; line-height:1.6;">Hello Mr. Vikramaditya Singhania. This is an urgent compliance notification from Meridian Infra Group. A high-priority hearing in Matter M-2025-014, Northern National Bank DRT Recovery, is scheduled for 12 November 2026. Prior digital alerts have not been acknowledged. Please open your compliance portal or press 1 on your keypad to acknowledge receipt.</textarea>
      </div>

      <div style="margin-top:24px; padding-top:16px; border-top:1px solid var(--border-subtle); display:flex; justify-content:flex-end; gap:12px;">
        <button class="btn btn-secondary" onclick="window.MeridianApp.showToast('Voice call cancelled.', 'warning'); window.location.hash='#/notifications';">
          Cancel Call
        </button>
        <button class="btn btn-primary" onclick="window.approveVoiceMessage()">
          ✓ Approve & Place Automated Call
        </button>
      </div>
    </div>
  `;

  window.approveVoiceMessage = () => {
    window.MeridianApp.showToast('Voice message approved and queued for telephony dispatch. Logged in Call Log.', 'success');
    window.location.hash = '#/notifications/calls';
  };
}

export async function renderCallLogView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/notifications">Notifications</a>
        <span class="breadcrumb-separator">/</span>
        <span>Call Log</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">Automated Telephony Call Log</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Audit record of voice attempts, call durations, receiver responses, and replay of message text.
          </p>
        </div>
      </div>
    </div>

    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Call Timestamp</th>
            <th>Recipient</th>
            <th>Attempt #</th>
            <th>Result</th>
            <th>Duration</th>
            <th>Message Replay Text</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>28 Oct 2026, 08:35 AM</td>
            <td>Vikramaditya Singhania</td>
            <td>Attempt 1</td>
            <td><span class="status-badge attention">Missed / Unanswered</span></td>
            <td>24 seconds</td>
            <td style="font-size:12px; color:var(--text-muted);">"High-priority DRT hearing notice..."</td>
          </tr>
          <tr>
            <td>27 Oct 2026, 02:15 PM</td>
            <td>Priya Nambiar</td>
            <td>Attempt 1</td>
            <td><span class="status-badge verified">Acknowledged (Keypad 1)</span></td>
            <td>45 seconds</td>
            <td style="font-size:12px; color:var(--text-muted);">"Statutory Form 8 filing overdue reminder..."</td>
          </tr>
          <tr>
            <td>24 Oct 2026, 11:20 AM</td>
            <td>Amit Verma</td>
            <td>Attempt 1</td>
            <td><span class="status-badge verified">Heard & Confirmed</span></td>
            <td>50 seconds</td>
            <td style="font-size:12px; color:var(--text-muted);">"Sanction renewal deadline notification..."</td>
          </tr>
        </tbody>
      </table>
    </div>
  `;
}
