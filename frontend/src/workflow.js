// Real-time collaboration workflow: WebSocket client + per-portal live panel.
//
// The panel is injected into each workspace. It subscribes to the server's
// /ws/workflow stream; on every event it re-fetches the lightweight
// /api/workflow list and re-renders ONLY the workflow container (so the rest
// of the workspace — and any text the user is typing — is preserved).
import { api, getToken } from './api.js'
import { showToast } from './app.js'

let ws = null
let wsReady = false
let reconnectTimer = null
let activeHandlers = []

// ---------------------------------------------------------------------------
// WebSocket lifecycle
// ---------------------------------------------------------------------------
export function connectWorkflow(onEvent) {
  const token = getToken()
  if (!token) return
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const url = `${proto}://${window.location.host}/ws/workflow?token=${encodeURIComponent(token)}`
  try {
    ws = new WebSocket(url)
  } catch {
    return
  }
  ws.onopen = () => { wsReady = true }
  ws.onmessage = (e) => {
    let ev
    try { ev = JSON.parse(e.data) } catch { return }
    if (onEvent) onEvent(ev)
  }
  ws.onclose = () => {
    wsReady = false
    // Auto-reconnect with backoff (local server may be restarting).
    clearTimeout(reconnectTimer)
    reconnectTimer = setTimeout(() => connectWorkflow(onEvent), 2500)
  }
  ws.onerror = () => { try { ws.close() } catch {} }
}

export function disconnectWorkflow() {
  clearTimeout(reconnectTimer)
  if (ws) { try { ws.close() } catch {} ws = null }
}

export function wsConnected() { return wsReady }

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))

function fmtTime(iso) {
  if (!iso) return ''
  try {
    const d = new Date(iso)
    return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  } catch { return iso }
}

const STATUS_META = {
  pending_approval: { label: 'Awaiting approval', cls: 'badge-warning' },
  assigned:         { label: 'Assigned', cls: 'badge-info' },
  in_progress:      { label: 'In progress', cls: 'badge-info' },
  waiting_input:    { label: 'Waiting for input', cls: 'badge-warning' },
  review_pending:   { label: 'Under management review', cls: 'badge-warning' },
  rework:           { label: 'Sent back for rework', cls: 'badge-error' },
  completed:        { label: 'Completed', cls: 'badge-success' },
  rejected:         { label: 'Rejected', cls: 'badge-error' },
}

function statusBadge(status) {
  const m = STATUS_META[status] || { label: status, cls: 'badge-info' }
  return `<span class="badge ${m.cls}"><span class="dot"></span>${esc(m.label)}</span>`
}

// ---------------------------------------------------------------------------
// per-portal panel
// ---------------------------------------------------------------------------
export function renderWorkflowPanel(portal, wfData) {
  const wfs = (wfData && wfData.workflows) || []
  const inputs = (wfData && wfData.pending_inputs) || []
  if (!wfData || !wfData.available) return ''

  let body = ''
  if (portal === 'management' || portal === 'admin') {
    body = renderManagementPanel(wfs)
  } else if (portal === 'employee') {
    body = renderEmployeePanel(wfs)
  } else if (portal === 'client' || portal === 'tenant') {
    body = renderRequesterPanel(portal, wfs, inputs)
  } else if (portal === 'counsel' || portal === 'auditor') {
    body = renderStakeholderPanel(portal, wfs, inputs)
  } else {
    body = renderManagementPanel(wfs)
  }

  return `
    <div class="glass-card card-pad-lg wf-panel" id="wf-panel" data-portal="${portal}">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:18px; flex-wrap:wrap; gap:10px;">
        <div>
          <span class="eyebrow">LIVE COLLABORATION</span>
          <h3 style="margin-top:4px;">Request Workflow</h3>
        </div>
        <span class="badge ${wsConnected() ? 'badge-success' : 'badge-info'}">
          <span class="dot"></span>${wsConnected() ? 'Real-time connected' : 'Connecting…'}
        </span>
      </div>
      ${body || renderEmpty('No workflows yet', 'Submit a request to start a live collaboration.')}
    </div>
  `
}

function renderEmpty(title, sub) {
  return `<div style="text-align:center; padding:28px 12px;">
    <div style="font-weight:600; margin-bottom:6px;">${esc(title)}</div>
    <div class="caption">${esc(sub)}</div>
  </div>`
}

// ---- management / admin: incoming requests + approve/assign + final review
function renderManagementPanel(wfs) {
  const pending = wfs.filter((w) => w.status === 'pending_approval')
  const inReview = wfs.filter((w) => w.status === 'review_pending')
  const active = wfs.filter((w) => !['pending_approval', 'review_pending', 'completed', 'rejected'].includes(w.status))
  const done = wfs.filter((w) => ['completed', 'rejected'].includes(w.status))
  return `
    <div style="margin-bottom:22px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <h4 style="margin:0;">Incoming Requests <span class="badge badge-warning">${pending.length}</span></h4>
      </div>
      ${pending.length === 0
        ? renderEmpty('Queue clear', 'No requests are waiting for your approval.')
        : pending.map((w) => `
          <div class="wf-row" data-wf="${w.id}">
            <div style="display:flex; justify-content:space-between; gap:12px; align-items:flex-start;">
              <div style="min-width:0;">
                <b>${esc(w.subject)}</b>
                <div class="caption" style="margin-top:2px;">
                  from ${esc(w.created_by)} (${esc(w.created_by_portal)}) · ${fmtTime(w.created_at)}
                  ${w.matter ? ' · matter ' + esc(w.matter) : ''}
                </div>
                <p class="text-small" style="margin:8px 0 0; white-space:pre-wrap;">${esc(w.message)}</p>
              </div>
              <div style="display:flex; gap:8px; flex-shrink:0;">
                <button class="btn btn-primary btn-sm wf-approve-btn" data-wf="${w.id}">Approve &amp; assign</button>
                <button class="btn btn-ghost btn-sm wf-reject-btn" data-wf="${w.id}" style="color:var(--status-error-fg);">Reject</button>
              </div>
            </div>
          </div>`).join('')}
    </div>
    <div style="margin-bottom:22px;">
      <h4 style="margin-bottom:12px;">Final Review — employee work awaiting your sign-off <span class="badge badge-warning">${inReview.length}</span></h4>
      ${inReview.length === 0
        ? renderEmpty('Nothing to review', 'When an employee submits their work, it appears here for your final approval.')
        : inReview.map((w) => {
            const lastReview = [...(w.activity || [])].reverse().find((a) => a.kind === 'review_submitted')
            return `
          <div class="wf-row" data-wf="${w.id}" data-final-response="${esc(w.final_response || '')}" style="margin-bottom:14px;">
            <div style="min-width:0; width:100%;">
              <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:12px;">
                <div>
                  <b>${esc(w.subject)}</b>
                  <div class="caption" style="margin-top:2px;">
                    from ${esc(w.created_by)} (${esc(w.created_by_portal)}) · done by ${esc(w.assigned_to)}
                    ${w.review_submitted_at ? ' · submitted ' + fmtTime(w.review_submitted_at) : ''}
                  </div>
                </div>
                <div style="display:flex; gap:8px; flex-shrink:0;">
                  <button class="btn btn-primary btn-sm wf-final-approve-btn" data-wf="${w.id}">✅ Final Approve</button>
                  <button class="btn btn-ghost btn-sm wf-sendback-btn" data-wf="${w.id}" style="color:var(--status-error-fg);">Send back</button>
                </div>
              </div>
              ${w.final_response ? `
              <div style="margin-top:10px; padding:12px; border-radius:var(--r-12); background:rgba(34,197,94,.06); border:1px solid rgba(34,197,94,.25); max-height:200px; overflow-y:auto;">
                <div style="font-size:11px; font-weight:700; color:#16a34a; margin-bottom:6px;">📄 AI-PREPARED DOCUMENT (AI Advocate + AI Auditor approved)</div>
                <div class="text-small" style="white-space:pre-wrap;">${esc(w.final_response.slice(0, 600))}${w.final_response.length > 600 ? '…' : ''}</div>
              </div>` : lastReview ? `<p class="text-small" style="margin:8px 0 0; white-space:pre-wrap;">${esc(lastReview.text)}</p>` : ''}
            </div>
          </div>`}).join('')}
    </div>
    ${active.length ? `<div style="margin-bottom:22px;">
      <h4 style="margin-bottom:12px;">Active Workflows <span class="badge badge-info">${active.length}</span></h4>
      ${active.map(wfRow).join('')}
    </div>` : ''}
    ${done.length ? `<div>
      <h4 style="margin-bottom:12px;">Recently Closed</h4>
      ${done.slice(0, 5).map(wfRow).join('')}
    </div>` : ''}
  `
}

function wfRow(w) {
  const assignee = w.assigned_to || '—'
  return `
    <div class="wf-row">
      <div style="display:flex; justify-content:space-between; gap:12px; align-items:center;">
        <div style="min-width:0;">
          <b>${esc(w.subject)}</b>
          <div class="caption" style="margin-top:2px;">
            ${esc(assignee)} · ${fmtTime(w.updated_at)}
          </div>
        </div>
        ${statusBadge(w.status)}
      </div>
    </div>`
}

// ---- employee: my assigned work -----------------------------------------
function renderEmployeePanel(wfs) {
  const open = wfs.filter((w) => ['assigned','in_progress','waiting_input','review_pending','rework'].includes(w.status))
  const closed = wfs.filter((w) => ['completed','rejected'].includes(w.status))
  if (open.length === 0) {
    return renderEmpty('No assigned work yet',
      'When management approves a request and assigns it to you, it appears here in real time.')
  }
  return open.map((w) => {
    const lastRework = w.status === 'rework'
      ? [...(w.activity || [])].reverse().find((a) => a.kind === 'rework_requested')
      : null
    const lastReview = w.status === 'review_pending'
      ? [...(w.activity || [])].reverse().find((a) => a.kind === 'review_submitted')
      : null
    return `
    <div class="wf-work-card" data-wf="${w.id}">
      <div style="display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:8px;">
        <div>
          <b style="font-size:16px;">${esc(w.subject)}</b>
          <div class="caption" style="margin-top:2px;">
            from ${esc(w.created_by)} (${esc(w.created_by_portal)})
            ${w.matter ? ' · matter ' + esc(w.matter) : ''}
          </div>
        </div>
        ${statusBadge(w.status)}
      </div>
      <p class="text-small" style="white-space:pre-wrap; margin-bottom:12px;">${esc(w.message)}</p>
      ${lastRework ? `<div style="margin:0 0 12px; padding:10px 12px; border-radius:var(--r-12); background:rgba(239,68,68,.08); border:1px solid rgba(239,68,68,.35);">
        <div class="caption" style="margin-bottom:4px; color:var(--status-error-fg);">Management sent this back for rework</div>
        <div class="text-small">${esc(lastRework.text)}</div>
      </div>` : ''}
      ${lastReview ? `<div style="margin:0 0 12px; padding:10px 12px; border-radius:var(--r-12); background:var(--gl);">
        <div class="caption" style="margin-bottom:4px;">Submitted for management review — awaiting final approval</div>
        <div class="text-small">${esc(lastReview.text)}</div>
      </div>` : ''}
      ${renderInputs(w)}
      ${renderActivity(w)}
      <div class="wf-actions" style="display:flex; flex-wrap:wrap; gap:8px; margin-top:12px;">
        ${w.status === 'assigned'
          ? `<button class="btn btn-primary btn-sm wf-start-btn" data-wf="${w.id}">Start work</button>` : ''}
        ${w.status !== 'review_pending' ? `
        <button class="btn btn-ghost btn-sm wf-ai-btn" data-wf="${w.id}">Run AI task</button>
        <button class="btn btn-ghost btn-sm wf-input-btn" data-wf="${w.id}">Request input</button>` : ''}
        <button class="btn btn-ghost btn-sm wf-note-btn" data-wf="${w.id}">Add note</button>
        ${w.status !== 'review_pending'
          ? `<button class="btn btn-primary btn-sm wf-complete-btn" data-wf="${w.id}">Submit for review</button>`
          : `<span class="caption">Waiting for management's final approval — the client will be notified once it is good.</span>`}
      </div>
    </div>`}).join('')
    + (closed.length ? `<div style="margin-top:18px;">
        <h4 style="margin-bottom:10px;">Recently closed</h4>
        ${closed.slice(0,4).map(wfRow).join('')}
      </div>` : '')
}

function renderInputs(w) {
  if (!w.inputs || w.inputs.length === 0) return ''
  return `<div style="margin:10px 0; padding:10px 12px; border-radius:var(--r-12); background:var(--gl);">
    <div class="caption" style="margin-bottom:8px;">Input requests</div>
    ${w.inputs.map((i) => `
      <div style="display:flex; gap:10px; align-items:flex-start; padding:6px 0; border-top:1px solid var(--bd);">
        <span class="badge ${i.status === 'pending' ? 'badge-warning' : 'badge-success'}" style="flex-shrink:0;">
          ${i.status === 'pending' ? 'pending' : 'answered'}
        </span>
        <div style="min-width:0;">
          <div class="text-small"><b>${esc(i.to_user)}</b> (${esc(i.to_portal)}): ${esc(i.question)}</div>
          ${i.status === 'answered' ? `<div class="text-small" style="margin-top:4px; color:var(--a1);">↳ ${esc(i.answer)}</div>` : ''}
        </div>
      </div>`).join('')}
  </div>`
}

function renderActivity(w) {
  const acts = (w.activity || []).filter((a) => a.kind !== 'created').slice(-6).reverse()
  if (acts.length === 0) return ''
  return `<div style="margin:8px 0; display:flex; flex-direction:column; gap:6px;">
    ${acts.map((a) => `
      <div class="text-small" style="display:flex; gap:8px;">
        <span class="badge badge-info" style="flex-shrink:0;">${esc(a.kind)}</span>
        <span style="min-width:0;">${esc(a.text)} ${a.data && a.data.answer ? `<div style="color:var(--mu); margin-top:2px;">${esc(String(a.data.answer).slice(0, 220))}</div>` : ''}</span>
      </div>`).join('')}
  </div>`
}

// ---- client / tenant: my requests + answer inputs -----------------------
function renderRequesterPanel(portal, wfs, inputs) {
  // Only show workflows created by this portal (not all visible ones)
  const mine = wfs.filter(w => w.created_by_portal === portal || inputs.some(i => i.workflow_id === w.id))
  const parts = []
  if (inputs.length > 0) {
    parts.push(`
      <div style="margin-bottom:20px; padding:16px; border-radius:var(--r-12); background:rgba(99,102,241,.08); border:2px solid rgba(99,102,241,.4);">
        <h4 style="margin-bottom:12px; color:var(--role); display:flex; align-items:center; gap:8px;">
          <span>🔔</span> Action needed — please respond
        </h4>
        ${inputs.map((i) => `
          <div class="wf-row" style="margin-bottom:12px; background:var(--bg,#1e1e2e); padding:14px; border-radius:var(--r-12);">
            <b style="font-size:14px;">${esc(i.question)}</b>
            <div class="caption" style="margin:6px 0 10px;">
              from ${esc(i.from_user)} · re: ${esc(i.subject)}
            </div>
            <div style="display:flex; gap:8px;">
              <input class="form-input wf-answer-input" data-input="${i.input_id}" placeholder="Type your answer here…" style="flex:1;" />
              <button class="btn btn-primary wf-answer-btn" data-input="${i.input_id}" style="white-space:nowrap;">Send →</button>
            </div>
          </div>`).join('')}
      </div>`)
  }
  if (mine.length === 0 && inputs.length === 0) {
    parts.push(renderEmpty('No requests yet', 'Use the form below to submit a request — management will be notified in real time.'))
  } else if (mine.length > 0) {
    parts.push(`
      <div>
        <h4 style="margin-bottom:12px;">My Requests</h4>
        ${mine.slice(0, 5).map((w) => `
          <div class="wf-row" style="margin-bottom:14px;">
            <div style="display:flex; justify-content:space-between; gap:12px;">
              <b>${esc(w.subject)}</b>
              ${statusBadge(w.status)}
            </div>
            <div class="caption" style="margin-top:4px;">${fmtTime(w.updated_at)}
              ${w.assigned_to ? ' · assigned to ' + esc(w.assigned_to) : ''}
            </div>
            ${w.status === 'completed' && w.final_response ? `
              <div style="margin-top:10px; padding:12px; border-radius:var(--r-12); background:var(--gl);">
                <div class="caption" style="margin-bottom:6px;">Final response</div>
                <div class="text-small" style="white-space:pre-wrap;">${esc(w.final_response)}</div>
              </div>` : ''}
            ${w.status === 'review_pending' && w.final_response ? `
              <div style="margin-top:10px; padding:14px; border-radius:var(--r-12); background:rgba(34,197,94,.08); border:1px solid rgba(34,197,94,.3);">
                <div style="font-weight:700; font-size:13px; color:#16a34a; margin-bottom:8px;">📄 Your Sale & Purchase Agreement is ready</div>
                <div class="text-small" style="white-space:pre-wrap; max-height:300px; overflow-y:auto;">${esc(w.final_response)}</div>
                <div style="margin-top:10px; font-size:11px; color:var(--mu);">✅ Approved by Legal Advocate & Auditor — contact us to arrange signing.</div>
              </div>` : ''}
            ${renderActivity(w)}
          </div>`).join('')}
      </div>`)
  }
  return parts.join('')
}

// ---- counsel / auditor: inputs addressed to me --------------------------
function renderStakeholderPanel(portal, wfs, inputs) {
  const parts = []
  if (inputs.length > 0) {
    parts.push(`
      <div style="margin-bottom:20px;">
        <h4 style="margin-bottom:10px;">Input requested from you</h4>
        ${inputs.map((i) => `
          <div class="wf-row" style="margin-bottom:10px;">
            <b>${esc(i.question)}</b>
            <div class="caption" style="margin:4px 0 8px;">
              from ${esc(i.from_user)} · ${esc(i.subject)}
            </div>
            <div style="display:flex; gap:8px;">
              <input class="form-input wf-answer-input" data-input="${i.input_id}" placeholder="Your answer…" />
              <button class="btn btn-primary btn-sm wf-answer-btn" data-input="${i.input_id}">Send</button>
            </div>
          </div>`).join('')}
      </div>`)
  }
  if (wfs.length > 0) {
    parts.push(`<div><h4 style="margin-bottom:12px;">Workflows you're involved in</h4>${wfs.map(wfRow).join('')}</div>`)
  }
  if (parts.length === 0) {
    parts.push(renderEmpty('No pending input', 'When an employee requests your input, it appears here in real time.'))
  }
  return parts.join('')
}

// ---------------------------------------------------------------------------
// live re-render (called on WS events)
// ---------------------------------------------------------------------------
export async function refreshWorkflowPanel() {
  const panel = document.getElementById('wf-panel')
  if (!panel) return

  // Don't refresh if user is actively typing inside the panel
  const active = document.activeElement
  if (active && active.closest && active.closest('#wf-panel')) return

  const portal = panel.dataset.portal
  try {
    const data = await api.portal()
    const wfData = data.workflow
    if (!wfData || !wfData.available) return

    const html = renderWorkflowPanel(portal, wfData)
    if (!html) return

    // Preserve any open modal + input focus.
    const modalRoot = document.getElementById('wf-modal-root')
    const modalHtml = modalRoot ? modalRoot.innerHTML : ''
    const focused = document.activeElement
    const fid = focused && focused.id ? focused.id : null
    const fval = focused && focused.value ? focused.value : null

    // Replace the outer panel element entirely so wf-panel doesn't nest
    const tmp = document.createElement('div')
    tmp.innerHTML = html
    const newPanel = tmp.firstElementChild
    const currentPanel = document.getElementById('wf-panel')
    if (newPanel && currentPanel && currentPanel.parentNode) {
      currentPanel.parentNode.replaceChild(newPanel, currentPanel)
    } else if (newPanel) {
      // Panel was removed from DOM — re-inject at top of content area
      const contentArea = document.getElementById('workspace-content')
      if (contentArea) contentArea.insertBefore(newPanel, contentArea.firstChild)
    }

    // Clear bound flag so event listeners are re-attached after re-render
    const updatedPanel = document.getElementById('wf-panel')
    if (updatedPanel) updatedPanel._wfBound = false

    // Re-attach modal + focus.
    const newModal = document.getElementById('wf-modal-root')
    if (newModal) newModal.innerHTML = modalHtml
    if (fid) {
      const el = document.getElementById(fid)
      if (el) { el.focus(); if (fval) el.value = fval }
    }
    bindWorkflowEvents(portal)
  } catch {
    /* keep existing panel on transient errors */
  }
}

// ---------------------------------------------------------------------------
// event binding (delegated so re-renders keep working)
// ---------------------------------------------------------------------------
export function bindWorkflowEvents(portal) {
  const panel = document.getElementById('wf-panel')
  if (!panel || panel._wfBound) return
  panel._wfBound = true

  // Management: approve / reject
  panel.addEventListener('click', async (e) => {
    const t = e.target.closest('button')
    if (!t) return
    // Management-only actions — block for other portals
    const isMgmt = portal === 'management' || portal === 'admin'
    if (t.classList.contains('wf-approve-btn')) { if (isMgmt) openAssignModal(t.dataset.wf); return }
    if (t.classList.contains('wf-reject-btn')) { if (isMgmt) openRejectModal(t.dataset.wf); return }
    if (t.classList.contains('wf-final-approve-btn')) { if (isMgmt) openFinalApproveModal(t.dataset.wf); return }
    if (t.classList.contains('wf-sendback-btn')) { if (isMgmt) openSendBackModal(t.dataset.wf); return }
    // Worker actions
    if (t.classList.contains('wf-start-btn')) await act('start', { workflow_id: t.dataset.wf })
    if (t.classList.contains('wf-ai-btn')) openAiModal(t.dataset.wf)
    if (t.classList.contains('wf-input-btn')) openInputModal(t.dataset.wf)
    if (t.classList.contains('wf-note-btn')) openNoteModal(t.dataset.wf)
    if (t.classList.contains('wf-complete-btn')) openCompleteModal(t.dataset.wf)
    if (t.classList.contains('wf-answer-btn')) {
      const input = panel.querySelector(`.wf-answer-input[data-input="${t.dataset.input}"]`)
      if (input && input.value.trim()) {
        const answer = input.value.trim()
        t.disabled = true
        t.textContent = 'Sending…'
        try {
          await act('input/answer', { input_id: t.dataset.input, answer })
        } catch (err) {
          t.disabled = false
          t.textContent = 'Send'
          showToast && showToast({ title: 'Error', message: err.message || 'Failed to send answer', type: 'error' })
          console.error('wf-answer-btn error:', err)
        }
      }
    }
  })

  // NOTE: modal form submits are delegated on the body-level #wf-modal-root
  // (see getModalRoot / handleModalSubmit), because the modal is portaled
  // out of the panel so its position:fixed overlay is not trapped by the
  // panel's backdrop-filter.
}

async function act(endpoint, body) {
  const map = {
    approve: () => api.wfApprove(body),
    reject: () => api.wfReject(body),
    start: () => api.wfStart(body),
    ai: () => api.wfAi(body),
    input: () => api.wfInput(body),
    activity: () => api.wfActivity(body),
    'input/answer': () => api.wfAnswerInput(body),
    complete: () => api.wfComplete(body),
    'final-approve': () => api.wfFinalApprove(body),
    'send-back': () => api.wfSendBack(body),
  }
  const result = await map[endpoint]()
  await refreshWorkflowPanel()
  return result
}

// ---- lightweight modal (rendered into a body-level #wf-modal-root) -------
// The modal root is attached to <body>, NOT inside the workflow panel. The
// panel has `backdrop-filter: blur(...)` (via .glass-card), which makes it a
// containing block for `position:fixed` descendants — so a fixed overlay
// rendered inside it is trapped to the panel's small box and its buttons
// become unreachable. Portaling to <body> keeps the overlay full-viewport.
function getModalRoot() {
  let root = document.getElementById('wf-modal-root')
  if (!root) {
    root = document.createElement('div')
    root.id = 'wf-modal-root'
    document.body.appendChild(root)
    // Modal forms live here (in <body>, outside the panel), so the submit
    // handler is delegated on the root — not on the panel.
    root.addEventListener('submit', handleModalSubmit)
  }
  return root
}

async function handleModalSubmit(e) {
  e.preventDefault()
  const form = e.target
  const kind = form.dataset.wfKind
  if (!kind) return
  const val = (id) => (form.querySelector(id) ? form.querySelector(id).value.trim() : '')
  try {
    if (kind === 'assign') await act('approve', { workflow_id: form.dataset.wf, employee_username: val('#wf-assign-user'), note: val('#wf-assign-note') })
    if (kind === 'reject') await act('reject', { workflow_id: form.dataset.wf, note: val('#wf-reject-note') })
    if (kind === 'ai') await act('ai', { workflow_id: form.dataset.wf, prompt: val('#wf-ai-prompt') })
    if (kind === 'input') await act('input', { workflow_id: form.dataset.wf, to_user: val('#wf-input-user'), to_portal: val('#wf-input-portal'), question: val('#wf-input-q') })
    if (kind === 'note') await act('activity', { workflow_id: form.dataset.wf, kind: 'note', text: val('#wf-note-text') })
    if (kind === 'complete') await act('complete', { workflow_id: form.dataset.wf, final_response: val('#wf-complete-text') })
    if (kind === 'final-approve') await act('final-approve', { workflow_id: form.dataset.wf, final_response: val('#wf-final-response'), note: val('#wf-final-note') })
    if (kind === 'send-back') await act('send-back', { workflow_id: form.dataset.wf, note: val('#wf-sendback-note') })
    closeModal()
  } catch (err) {
    showToast({ title: 'Workflow error', message: err.message, type: 'error' })
  }
}
function closeModal() {
  const root = document.getElementById('wf-modal-root')
  if (root) root.innerHTML = ''
}
function openModal(title, bodyHtml, formId) {
  const root = getModalRoot()
  root.innerHTML = `
    <div class="wf-modal-overlay" id="wf-modal-overlay">
      <div class="wf-modal">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
          <h3 style="margin:0;">${esc(title)}</h3>
          <button type="button" class="btn btn-ghost btn-sm" id="wf-modal-close">✕</button>
        </div>
        <form id="${formId}" data-wf-kind="${formId}">
          ${bodyHtml}
          <div style="display:flex; gap:10px; justify-content:flex-end; margin-top:18px;">
            <button type="button" class="btn btn-ghost" id="wf-modal-cancel">Cancel</button>
            <button type="submit" class="btn btn-primary">Confirm</button>
          </div>
        </form>
      </div>
    </div>`
  const close = () => closeModal()
  document.getElementById('wf-modal-close').onclick = close
  document.getElementById('wf-modal-cancel').onclick = close
  document.getElementById('wf-modal-overlay').onclick = (e) => { if (e.target.id === 'wf-modal-overlay') close() }
}

function openAssignModal(wfId) {
  openModal('Approve & assign', `
    <div class="form-group">
      <label class="form-label">Assign to employee</label>
      <input id="wf-assign-user" class="form-input" placeholder="e.g. employee1" required />
    </div>
    <div class="form-group">
      <label class="form-label">Note (optional)</label>
      <input id="wf-assign-note" class="form-input" placeholder="Instructions for the assignee" />
    </div>`, 'assign')
  const form = document.getElementById('assign')
  if (form) form.dataset.wf = wfId
}
function openRejectModal(wfId) {
  openModal('Reject request', `
    <div class="form-group">
      <label class="form-label">Reason</label>
      <textarea id="wf-reject-note" class="form-textarea" rows="2" placeholder="Why is this being rejected?"></textarea>
    </div>`, 'reject')
  document.getElementById('reject').dataset.wf = wfId
}
function openAiModal(wfId) {
  openModal('Run AI task on this request', `
    <div class="form-group">
      <label class="form-label">Prompt</label>
      <textarea id="wf-ai-prompt" class="form-textarea" rows="3" required
        placeholder="e.g. Summarize the applicable statute and deadlines for this matter."></textarea>
    </div>
    <p class="caption">Runs through the governed 16-agent orchestrator on local hardware.</p>`, 'ai')
  document.getElementById('ai').dataset.wf = wfId
}
function openInputModal(wfId) {
  openModal('Request input from a stakeholder', `
    <div class="form-group">
      <label class="form-label">From (portal)</label>
      <select id="wf-input-portal" class="form-input">
        <option value="client">client</option>
        <option value="tenant">tenant</option>
        <option value="counsel">counsel</option>
        <option value="auditor">auditor</option>
        <option value="employee">employee</option>
      </select>
    </div>
    <div class="form-group">
      <label class="form-label">To (username)</label>
      <input id="wf-input-user" class="form-input" placeholder="e.g. client1" required />
    </div>
    <div class="form-group">
      <label class="form-label">Question</label>
      <textarea id="wf-input-q" class="form-textarea" rows="2" required placeholder="What do you need from them?"></textarea>
    </div>`, 'input')
  document.getElementById('input').dataset.wf = wfId
}
function openNoteModal(wfId) {
  openModal('Add a work note', `
    <div class="form-group">
      <label class="form-label">Note</label>
      <textarea id="wf-note-text" class="form-textarea" rows="3" required placeholder="Progress update for the record…"></textarea>
    </div>`, 'note')
  document.getElementById('note').dataset.wf = wfId
}
function openCompleteModal(wfId) {
  openModal('Submit for management review', `
    <div class="form-group">
      <label class="form-label">Summary of your work</label>
      <textarea id="wf-complete-text" class="form-textarea" rows="5" required placeholder="Summarize what you did, the outcome, next steps, and any documents produced…"></textarea>
    </div>
    <p class="caption">Management will review this. If it is good, they will approve it and the client is notified; otherwise it is sent back to you with feedback.</p>`, 'complete')
  document.getElementById('complete').dataset.wf = wfId
}
function openFinalApproveModal(wfId) {
  // Pre-populate with the AI-prepared final response if available
  const wfCard = document.querySelector(`[data-wf="${wfId}"][data-final-response]`)
  const preText = wfCard ? (wfCard.dataset.finalResponse || '') : ''
  openModal("Final approval — review & send to client", `
    <div style="margin-bottom:12px; padding:10px 14px; border-radius:8px; background:rgba(34,197,94,.08); border:1px solid rgba(34,197,94,.3); font-size:13px;">
      ✅ <strong>AI Legal Advocate</strong> and <strong>AI Auditor</strong> have both approved this document. Review below and click Confirm to deliver to the client.
    </div>
    <div class="form-group">
      <label class="form-label">Final response to the client</label>
      <textarea id="wf-final-response" class="form-textarea" rows="8" required placeholder="The message the client will receive once you approve…">${esc(preText)}</textarea>
    </div>
    <div class="form-group">
      <label class="form-label">Internal note (optional)</label>
      <input id="wf-final-note" class="form-input" placeholder="For the record" />
    </div>
    <p class="caption">Approving delivers the final response to the client and closes the workflow.</p>`, 'final-approve')
  document.getElementById('final-approve').dataset.wf = wfId
}
function openSendBackModal(wfId) {
  openModal('Send back for rework', `
    <div class="form-group">
      <label class="form-label">Feedback for the employee</label>
      <textarea id="wf-sendback-note" class="form-textarea" rows="3" required placeholder="What needs to be fixed before you approve?"></textarea>
    </div>`, 'send-back')
  document.getElementById('send-back').dataset.wf = wfId
}