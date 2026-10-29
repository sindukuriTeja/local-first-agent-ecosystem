// Nushift Workspaces Controller (All 7 Roles)
// Complete Data Binding, Modals, AI Runner, Tables, Charts, Sensitivity Badges
import {
  initCommonUI,
  icons,
  ROLE_CONFIGS,
  openModal,
  closeModal,
  showToast,
  animateCountUp,
} from './app.js'
import { api, getToken, getUser, clearSession } from './api.js'
import {
  connectWorkflow, disconnectWorkflow, renderWorkflowPanel,
  refreshWorkflowPanel, bindWorkflowEvents,
} from './workflow.js'

let currentUser = null
let portalData = null
let activeRoleKey = 'employee'
let runningAiTask = false
let aiAbortController = null

export async function initWorkspace() {
  initCommonUI()

  // 1. Check authentication
  const token = getToken()
  if (!token) {
    window.location.replace('roles.html')
    return
  }

  try {
    const meRes = await api.me()
    currentUser = meRes.user
  } catch {
    currentUser = getUser()
    if (!currentUser) {
      clearSession()
      window.location.replace('roles.html')
      return
    }
  }

  // Determine role: URL query ?role= or user.portal
  const params = new URLSearchParams(window.location.search)
  const roleQuery = params.get('role')
  activeRoleKey = (roleQuery && ROLE_CONFIGS[roleQuery.toLowerCase()])
    ? roleQuery.toLowerCase()
    : (currentUser.portal || 'employee')

  // Set role styling
  document.body.className = 'workspace-body'
  document.body.setAttribute('data-role', activeRoleKey)
  const roleCfg = ROLE_CONFIGS[activeRoleKey] || ROLE_CONFIGS.employee
  document.title = `${roleCfg.title} Portal | Nushift`

  // Setup sidebar and shell headers
  renderShellHeader(roleCfg)
  setupShellInteractions()

  // Fetch portal data
  await loadPortalData()
}

function renderShellHeader(roleCfg) {
  // Topbar greeting
  const firstName = (currentUser.display_name || currentUser.username || 'Practitioner').split(' ')[0]
  const greetingEl = document.getElementById('shell-greeting')
  if (greetingEl) {
    greetingEl.textContent = `Good morning, ${firstName}`
  }

  const roleEyebrow = document.getElementById('shell-role-eyebrow')
  if (roleEyebrow) {
    roleEyebrow.textContent = roleCfg.title.toUpperCase() + ' WORKSPACE'
  }

  const breadcrumb = document.getElementById('shell-breadcrumb')
  if (breadcrumb) {
    breadcrumb.innerHTML = `
      <span>Nushift</span>
      <span>/</span>
      <span style="color: var(--role); font-weight: 500;">${roleCfg.title}</span>
      <span>/</span>
      <span>Overview</span>
    `
  }

  // Sidebar user block
  const avatarEl = document.getElementById('shell-avatar')
  if (avatarEl) {
    const name = currentUser.display_name || currentUser.username || 'User'
    const parts = name.trim().split(/\s+/)
    const initials = ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || 'U'
    avatarEl.textContent = initials
  }

  const userNameEl = document.getElementById('shell-user-name')
  if (userNameEl) {
    userNameEl.textContent = currentUser.display_name || currentUser.username
  }

  const userRoleEl = document.getElementById('shell-user-role')
  if (userRoleEl) {
    userRoleEl.textContent = roleCfg.title
  }

  // Sidebar navigation links
  renderSidebarNav(activeRoleKey)
}

function renderSidebarNav(roleKey) {
  const navList = document.getElementById('sidebar-nav-list')
  if (!navList) return

  const commonNav = [
    { label: 'Overview', icon: icons.barChart, active: true, id: 'sec-overview' },
    { label: 'Documents', icon: icons.fileText, active: false, id: 'sec-documents' },
    { label: 'Matters & Cases', icon: icons.briefcase, active: false, id: 'sec-cases' },
  ]

  if (roleKey === 'auditor') {
    commonNav[2] = { label: 'Audit Trail', icon: icons.activity, active: false, id: 'sec-audit' }
  } else if (roleKey === 'admin') {
    commonNav.push({ label: 'User Directory', icon: icons.users, active: false, id: 'sec-users' })
  }

  navList.innerHTML = commonNav
    .map(
      (n) => `
    <li>
      <a href="#${n.id}" class="sidebar-nav-item ${n.active ? 'active' : ''}">
        ${n.icon}
        <span>${n.label}</span>
      </a>
    </li>
  `
    )
    .join('')
}

function setupShellInteractions() {
  // Mobile drawer
  const menuBtn = document.getElementById('sidebar-menu-btn')
  const sidebar = document.getElementById('workspace-sidebar')
  if (menuBtn && sidebar) {
    const backdrop = document.createElement('div')
    backdrop.id = 'workspace-drawer-backdrop'
    backdrop.style.cssText = 'position:fixed; inset:0; background:rgba(7,11,20,0.55); z-index:85; display:none;'
    document.body.appendChild(backdrop)
    const closeDrawer = () => {
      sidebar.classList.remove('drawer-open')
      backdrop.style.display = 'none'
    }
    menuBtn.addEventListener('click', () => {
      const open = sidebar.classList.toggle('drawer-open')
      backdrop.style.display = open ? 'block' : 'none'
    })
    backdrop.addEventListener('click', closeDrawer)
  }

  // Sign out modal trigger
  const signoutBtn = document.getElementById('shell-signout-btn')
  if (signoutBtn) {
    signoutBtn.addEventListener('click', () => {
      openModal('signout-modal')
    })
  }

  const confirmSignoutBtn = document.getElementById('confirm-signout-btn')
  if (confirmSignoutBtn) {
    confirmSignoutBtn.addEventListener('click', async () => {
      try {
        await api.logout()
      } catch {
        /* ignore */
      }
      disconnectWorkflow()
      clearSession()
      window.location.href = 'roles.html'
    })
  }

  const cancelSignoutBtn = document.getElementById('cancel-signout-btn')
  if (cancelSignoutBtn) {
    cancelSignoutBtn.addEventListener('click', () => {
      closeModal('signout-modal')
    })
  }

  // Notifications button
  const notifBtn = document.getElementById('shell-notif-btn')
  if (notifBtn) {
    notifBtn.addEventListener('click', () => {
      showToast({
        title: 'System Notifications',
        message: 'All 16 governance agents operational on local hardware.',
        type: 'info',
      })
    })
  }
}

async function loadPortalData() {
  const contentArea = document.getElementById('workspace-content')
  if (!contentArea) return

  // Loading skeleton
  contentArea.innerHTML = `
    <div style="display: flex; flex-direction: column; gap: 24px;">
      <div class="skeleton-line" style="height: 180px; border-radius: var(--r-20);"></div>
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px;">
        <div class="skeleton-line" style="height: 110px; border-radius: var(--r-20);"></div>
        <div class="skeleton-line" style="height: 110px; border-radius: var(--r-20);"></div>
        <div class="skeleton-line" style="height: 110px; border-radius: var(--r-20);"></div>
        <div class="skeleton-line" style="height: 110px; border-radius: var(--r-20);"></div>
      </div>
      <div class="skeleton-line" style="height: 240px; border-radius: var(--r-20);"></div>
    </div>
  `

  try {
    portalData = await api.portal()
    renderActiveWorkspace(contentArea)
    // Inject the real-time collaboration workflow panel (all roles).
    injectWorkflowPanel()
    // Subscribe to the live event stream; re-render the panel on each event.
    connectWorkflow(() => refreshWorkflowPanel())
  } catch (err) {
    contentArea.innerHTML = `
      <div class="glass-card card-pad-lg" style="border-color: var(--status-error-fg); text-align: center;">
        <div class="icon-tile icon-tile-56" style="margin: 0 auto 16px; --role: var(--status-error-fg);">
          ${icons.alertTriangle}
        </div>
        <h3 style="color: var(--status-error-fg); margin-bottom: 8px;">Failed to load workspace data</h3>
        <p class="text-small" style="margin-bottom: 24px;">${err.message || 'Please check server connection.'}</p>
        <button type="button" class="btn btn-primary" onclick="window.location.reload()">
          <span>Try again</span>
        </button>
      </div>
    `
  }
}

// Inject the live workflow panel at the top of the workspace content.
function injectWorkflowPanel() {
  const contentArea = document.getElementById('workspace-content')
  if (!contentArea || !portalData) return
  const wfData = portalData.workflow || { available: false }
  if (!wfData.available) return
  const holder = document.createElement('div')
  holder.innerHTML = renderWorkflowPanel(activeRoleKey, wfData)
  // Prepend so it's the first thing each role sees.
  contentArea.insertBefore(holder.firstElementChild, contentArea.firstChild)
  bindWorkflowEvents(activeRoleKey)
}

// Route to role-specific workspace layout
function renderActiveWorkspace(container) {
  switch (activeRoleKey) {
    case 'employee':
      renderEmployeeWorkspace(container)
      break
    case 'management':
      renderManagementWorkspace(container)
      break
    case 'advocate':
    case 'counsel':
      renderAdvocateWorkspace(container)
      break
    case 'client':
      renderClientWorkspace(container)
      break
    case 'tenant':
      renderTenantWorkspace(container)
      break
    case 'auditor':
      renderAuditorWorkspace(container)
      break
    case 'admin':
      renderAdminWorkspace(container)
      break
    default:
      renderEmployeeWorkspace(container)
  }
}

/* =============================================================
   8.1 Internal Employee (Blue Accent)
   Hero: AI task box
   Below: 4 stat cards with tickers
   Two columns: "My cases" and "Drafts in my queue"
   Legal work tabbed card (Statutes, Judgments)
   All documents in scope table
   ============================================================= */
function renderEmployeeWorkspace(container) {
  const c = portalData.counts || {}
  const cases = portalData.cases || []
  const drafts = portalData.drafts || []
  const legalWork = portalData.legal_work || []
  const statutes = legalWork.filter((d) => d.doc_type === 'statute')
  const judgments = legalWork.filter((d) => d.doc_type !== 'statute')
  const allDocs = portalData.documents || []

  container.innerHTML = `
    <!-- Hero: Gradient-border AI Task Box -->
    ${renderAiTaskBox(portalData.ai_tasks || [])}

    <!-- 4 Stat Cards with Tickers -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px;">
      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Assigned cases</span>
          <span class="icon-tile icon-tile-44">${icons.briefcase}</span>
        </div>
        <div class="stat-number" data-ticker="${c.cases || cases.length}">0</div>
      </div>

      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Tax matters</span>
          <span class="icon-tile icon-tile-44">${icons.percent}</span>
        </div>
        <div class="stat-number" data-ticker="${c.tax || (portalData.tax_matters || []).length}">0</div>
      </div>

      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Legal work</span>
          <span class="icon-tile icon-tile-44">${icons.bookOpen}</span>
        </div>
        <div class="stat-number" data-ticker="${legalWork.length}">0</div>
      </div>

      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Drafts waiting</span>
          <span class="icon-tile icon-tile-44">${icons.fileText}</span>
        </div>
        <div class="stat-number" data-ticker="${c.drafts || drafts.length}">0</div>
      </div>
    </div>

    <!-- Two columns: My cases cards and Drafts in queue -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 24px;">
      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">My cases</h3>
        ${renderDocCardsOrEmpty(cases, 'No active cases assigned to your account.')}
      </div>

      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">Drafts in my queue</h3>
        ${renderDocCardsOrEmpty(drafts, 'No drafts currently awaiting review.')}
      </div>
    </div>

    <!-- Tabbed Card: Legal Work (Statutes, Judgments) -->
    <div class="glass-card card-pad-lg" id="sec-cases">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
        <h3>Legal Work Library</h3>
        <div style="display: flex; gap: 8px;">
          <button type="button" class="btn btn-ghost btn-sm active" id="tab-statutes-btn" style="border-bottom: 2px solid var(--role);">
            Statutes (${statutes.length})
          </button>
          <button type="button" class="btn btn-ghost btn-sm" id="tab-judgments-btn">
            Judgments (${judgments.length})
          </button>
        </div>
      </div>
      <div id="legal-work-tab-content">
        ${renderTable(statutes.length > 0 ? statutes : judgments, ['title', 'doc_type', 'sensitivity', 'updated_at'])}
      </div>
    </div>

    <!-- All documents in scope -->
    <div class="glass-card card-pad-lg" id="sec-documents">
      <h3 style="margin-bottom: 16px;">All documents in scope</h3>
      ${renderTable(allDocs, ['title', 'doc_type', 'sensitivity', 'updated_at'])}
    </div>
  `

  bindAiTaskEvents()
  bindLegalTabs(statutes, judgments)
  initTickersInContainer(container)
}

/* =============================================================
   8.2 Management or Executive (Amber Accent)
   Hero: KPI strip (4 stats) + inline SVG bar chart of matters by area
   Below: Pending approvals list with Approve/Reject modal
   Compliance snapshot card & Workload table
   ============================================================= */
function renderManagementWorkspace(container) {
  const kpi = portalData.kpi || {}
  const approvals = portalData.approvals || []
  const workload = portalData.workload || []
  const compliance = portalData.compliance_snapshot || []

  container.innerHTML = `
    <!-- Hero: Firm-wide KPI Strip + Inline SVG Bar Chart -->
    <div class="glass-card card-pad-lg" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 32px; align-items: center;">
      <!-- KPI stats -->
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
        <div>
          <div class="caption">Total Documents</div>
          <div class="stat-number" data-ticker="${kpi.documents || 0}">0</div>
        </div>
        <div>
          <div class="caption">Open Matters</div>
          <div class="stat-number" data-ticker="${kpi.open_cases || 0}">0</div>
        </div>
        <div>
          <div class="caption">Pending Approvals</div>
          <div class="stat-number" data-ticker="${kpi.pending_approvals || approvals.length}">0</div>
        </div>
        <div>
          <div class="caption">Tax Filings</div>
          <div class="stat-number" data-ticker="${kpi.tax_matters || 0}">0</div>
        </div>
      </div>

      <!-- Simple inline SVG bar chart of matters by area -->
      <div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 12px;">
          <span style="font-size: 14px; font-weight: 600;">Matters Distribution by Area</span>
          <span class="caption">Active caseload</span>
        </div>
        ${renderSvgBarChart(workload)}
      </div>
    </div>

    <!-- Pending approvals with Approve and Reject buttons (confirm modal) -->
    <div class="glass-card card-pad-lg" id="sec-overview">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
        <div>
          <h3>Pending Approvals Queue</h3>
          <p class="caption">Executive sign-off required before draft release.</p>
        </div>
        <span class="badge badge-warning"><span class="dot"></span>${approvals.length} Awaiting</span>
      </div>

      ${
        approvals.length === 0
          ? renderEmptyState('No pending approvals', 'All candidate filings and requests have been decided.')
          : `
        <div class="table-container">
          <table class="data-table">
            <thead>
              <tr>
                <th>Title / Action</th>
                <th>Requested By</th>
                <th>Type</th>
                <th>Date</th>
                <th style="text-align: right;">Decide</th>
              </tr>
            </thead>
            <tbody>
              ${approvals
                .map(
                  (ap) => `
                <tr>
                  <td><b>${ap.title || ap.action || 'Filing Draft'}</b></td>
                  <td>${ap.requested_by || ap.user || 'counsel'}</td>
                  <td><span class="badge badge-info">${ap.type || 'draft'}</span></td>
                  <td class="caption">${fmtDate(ap.created_at)}</td>
                  <td style="text-align: right;">
                    <button type="button" class="btn btn-primary btn-sm approve-action-btn" data-id="${ap.id}" data-action="approved" style="margin-right: 6px;">
                      Approve
                    </button>
                    <button type="button" class="btn btn-ghost btn-sm approve-action-btn" data-id="${ap.id}" data-action="rejected" style="color: var(--status-error-fg);">
                      Reject
                    </button>
                  </td>
                </tr>
              `
                )
                .join('')}
            </tbody>
          </table>
        </div>
      `
      }
    </div>

    <!-- Grid 2: Workload by matter and Compliance Snapshot -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 24px;">
      <div class="glass-card card-pad-lg" id="sec-cases">
        <h3 style="margin-bottom: 16px;">Active Matter Proceedings</h3>
        ${
          workload.length === 0
            ? renderEmptyState('No workload data', 'All current cases are concluded.')
            : `
          <div class="table-container">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Matter</th>
                  <th>Client</th>
                  <th>Deadline</th>
                  <th style="text-align: right;">Items</th>
                </tr>
              </thead>
              <tbody>
                ${workload
                  .map(
                    (w) => `
                  <tr>
                    <td><b>${w.matter}</b></td>
                    <td>${w.client || '—'}</td>
                    <td class="caption">${w.deadline || '—'}</td>
                    <td style="text-align: right;"><b>${w.items || 1}</b></td>
                  </tr>
                `
                  )
                  .join('')}
              </tbody>
            </table>
          </div>
        `
        }
      </div>

      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">Compliance &amp; Risk Snapshot</h3>
        ${renderDocCardsOrEmpty(compliance, 'No risk flags or upcoming compliance alerts recorded.')}
      </div>
    </div>
  `

  bindApprovalEvents()
  initTickersInContainer(container)
}

/* =============================================================
   8.3 Advocate or External Counsel (Pink Accent)
   Hero: "Matters" as a card list with status badge & next-hearing line
   Right column: "Drafts to review" panel
   Below: Shared documents table & legal research
   AI assistant task box
   ============================================================= */
function renderAdvocateWorkspace(container) {
  const cases = portalData.cases || []
  const draftsToReview = portalData.drafts_to_review || portalData.drafts || []
  const sharedDocs = portalData.documents || []
  const research = portalData.research || []

  container.innerHTML = `
    <!-- Top Row: Matters card list (hero) + Drafts to review panel -->
    <div style="display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 24px;" id="sec-cases">
      <!-- Matters Hero Card List -->
      <div class="glass-card card-pad-lg">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
          <h3>Assigned Court Matters</h3>
          <span class="badge badge-role">${cases.length} Active</span>
        </div>
        ${
          cases.length === 0
            ? renderEmptyState('No matters assigned', 'All briefed proceedings have been resolved.')
            : `
          <div style="display: flex; flex-direction: column; gap: 14px;">
            ${cases
              .map(
                (c) => `
              <div class="glass-card card-pad-sm" style="display: flex; flex-direction: column; gap: 8px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 600; font-size: 16px;">${c.title}</span>
                  ${renderSensBadge(c.sensitivity)}
                </div>
                <div style="display: flex; align-items: center; gap: 16px; font-size: 13px; color: var(--mu);">
                  <span>Matter ID: <b style="color: var(--fg);">${c.matter || c.id}</b></span>
                  <span>Next Hearing: <b style="color: var(--role);">${c.deadline || '2026-11-15'}</b></span>
                </div>
              </div>
            `
              )
              .join('')}
          </div>
        `
        }
      </div>

      <!-- Drafts to Review Panel -->
      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">Drafts to Review</h3>
        ${renderDocCardsOrEmpty(draftsToReview, 'No pending briefs or draft motions in your queue.')}
      </div>
    </div>

    <!-- AI Assistant Task Box -->
    ${renderAiTaskBox(portalData.ai_tasks || [])}

    <!-- Below: Shared Documents & Research -->
    <div class="glass-card card-pad-lg" id="sec-documents">
      <h3 style="margin-bottom: 16px;">Shared Counsel Documents</h3>
      ${renderTable(sharedDocs, ['title', 'doc_type', 'sensitivity', 'updated_at'])}
    </div>

    <div class="glass-card card-pad-lg">
      <h3 style="margin-bottom: 16px;">Legal Precedent Research</h3>
      ${renderDocCardsOrEmpty(research, 'No shared statutory research notes.')}
    </div>
  `

  bindAiTaskEvents()
}

/* =============================================================
   8.4 Client (Green Accent)
   Hero: 5-step progress tracker (Intake, Review, Drafting, Approval, Filed)
   with current step highlighted and labelled "(now)", status pill ("On track")
   Below: "Shared documents" & "Next step" card with one action button
   Request & Upload forms, and request history
   ============================================================= */
function renderClientWorkspace(container) {
  const cases = portalData.cases || []
  const reports = portalData.reports || []
  const requests = portalData.my_requests || []

  container.innerHTML = `
    <!-- Hero: 5-Step Progress Tracker -->
    <div class="glass-card card-pad-lg">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; flex-wrap: wrap; gap: 12px;">
        <div>
          <span class="eyebrow">MATTER MILESTONE TRACKER</span>
          <h2 style="font-size: 26px; margin-top: 4px;">Commercial Dispute Settlement</h2>
        </div>
        <span class="badge badge-success" style="font-size: 13px; padding: 6px 14px;">
          <span class="dot"></span>On track
        </span>
      </div>

      <div class="progress-stepper" aria-label="Matter progression steps">
        <div class="progress-stepper-track">
          <div class="progress-stepper-fill" style="width: 50%;"></div>
        </div>

        <div class="progress-step-item">
          <div class="step-circle complete">${icons.check}</div>
          <span style="font-size: 13px; font-weight: 500;">Intake</span>
        </div>

        <div class="progress-step-item">
          <div class="step-circle complete">${icons.check}</div>
          <span style="font-size: 13px; font-weight: 500;">Review</span>
        </div>

        <div class="progress-step-item">
          <div class="step-circle active">3</div>
          <span style="font-size: 13px; font-weight: 600; color: var(--role);">Drafting (now)</span>
        </div>

        <div class="progress-step-item">
          <div class="step-circle">4</div>
          <span style="font-size: 13px; color: var(--mu);">Approval</span>
        </div>

        <div class="progress-step-item">
          <div class="step-circle">5</div>
          <span style="font-size: 13px; color: var(--mu);">Filed</span>
        </div>
      </div>
    </div>

    <!-- Grid 2: Shared Documents & Next Step Card -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 24px;">
      <!-- Shared documents -->
      <div class="glass-card card-pad-lg" id="sec-documents">
        <h3 style="margin-bottom: 16px;">Reviewed Legal Reports</h3>
        ${renderDocCardsOrEmpty(reports, 'Your counsel has not released any reports yet.')}
      </div>

      <!-- Next Step Card with one action button -->
      <div class="glass-card card-spotlight card-pad-lg" style="display: flex; flex-direction: column; justify-content: space-between;">
        <div>
          <span class="eyebrow" style="margin-bottom: 8px; display: inline-block;">ACTION REQUIRED</span>
          <h3 style="margin-bottom: 12px;">Confirm Representation Terms</h3>
          <p class="text-small" style="font-size: 15px; margin-bottom: 24px;">
            Please review the updated representation scope document and confirm client authorization.
          </p>
        </div>
        <button type="button" class="btn btn-primary btn-lg" id="client-next-step-btn" style="width: 100%;">
          <span>Authorize and proceed</span>
          ${icons.arrowRight}
        </button>
      </div>
    </div>

    <!-- Interactive Request & Upload Forms -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 24px;">
      <!-- Request form -->
      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">Submit an Inquiry</h3>
        <form id="client-request-form">
          <div class="form-group">
            <label class="form-label" for="req-subject">Subject</label>
            <input id="req-subject" class="form-input" placeholder="e.g. Question on deadline" required />
          </div>
          <div class="form-group">
            <label class="form-label" for="req-message">Message</label>
            <textarea id="req-message" class="form-textarea" placeholder="Provide context for your assigned legal counsel..." required></textarea>
          </div>
          <button type="submit" class="btn btn-primary" style="width: 100%;">
            <span>Send message</span>
            ${icons.send}
          </button>
        </form>
      </div>

      <!-- Upload form -->
      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">Upload Supporting Evidence</h3>
        <form id="client-upload-form">
          <div class="form-group">
            <label class="form-label" for="upload-file">Select File</label>
            <input id="upload-file" type="file" class="form-input" style="padding-top: 10px;" required />
          </div>
          <div class="form-group">
            <label class="form-label" for="upload-sens">Sensitivity</label>
            <select id="upload-sens" class="form-input">
              <option value="internal">Internal (Firm Only)</option>
              <option value="confidential" selected>Confidential (Privileged)</option>
              <option value="public">Public</option>
            </select>
          </div>
          <button type="submit" class="btn btn-ghost" style="width: 100%;">
            <span>Upload file</span>
            ${icons.upload}
          </button>
        </form>
      </div>
    </div>

    <!-- My Request History -->
    <div class="glass-card card-pad-lg">
      <h3 style="margin-bottom: 16px;">My Request History</h3>
      ${renderRequestTable(requests)}
    </div>
  `

  bindClientFormEvents()
}

/* =============================================================
   8.5 Tenant or Buyer or Vendor (Orange Accent)
   Hero: Task checklist with due dates and checkboxes + property card
   Below: Documents/parcels table, updates list, request & upload
   ============================================================= */
function renderTenantWorkspace(container) {
  const parcels = portalData.parcels || []
  const updates = portalData.updates || []
  const requests = portalData.my_requests || []

  container.innerHTML = `
    <!-- Hero: Task Checklist + Property Card -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px;" id="sec-cases">
      <!-- Task checklist with due dates and checkboxes -->
      <div class="glass-card card-pad-lg">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <h3>Required Property Tasks</h3>
          <span class="badge badge-role">2 Remaining</span>
        </div>
        <div style="display: flex; flex-direction: column; gap: 14px;">
          <label style="display: flex; align-items: center; gap: 12px; cursor: pointer; padding: 8px; border-radius: var(--r-12); background: var(--gl);">
            <input type="checkbox" checked style="width: 18px; height: 18px; accent-color: var(--role);" />
            <div style="flex: 1;">
              <span style="text-decoration: line-through; color: var(--mu);">Submit Title Registration KYC</span>
              <div class="caption">Completed 2026-10-20</div>
            </div>
          </label>

          <label style="display: flex; align-items: center; gap: 12px; cursor: pointer; padding: 8px; border-radius: var(--r-12); background: var(--gl);">
            <input type="checkbox" style="width: 18px; height: 18px; accent-color: var(--role);" />
            <div style="flex: 1;">
              <b>Upload Encumbrance Certificate</b>
              <div class="caption" style="color: var(--role);">Due by 2026-11-05</div>
            </div>
          </label>

          <label style="display: flex; align-items: center; gap: 12px; cursor: pointer; padding: 8px; border-radius: var(--r-12); background: var(--gl);">
            <input type="checkbox" style="width: 18px; height: 18px; accent-color: var(--role);" />
            <div style="flex: 1;">
              <b>Verify Boundary Demarcation Survey</b>
              <div class="caption">Due by 2026-11-12</div>
            </div>
          </label>
        </div>
      </div>

      <!-- Property or Contract Card with Key Facts -->
      <div class="glass-card card-pad-lg">
        <span class="eyebrow" style="margin-bottom: 8px; display: inline-block;">PARCEL DOSSIER</span>
        <h3 style="margin-bottom: 16px;">Registered Land Parcel P1</h3>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
          <div>
            <div class="caption">Parcel ID</div>
            <b>P-2026-001</b>
          </div>
          <div>
            <div class="caption">Survey Status</div>
            <span class="badge badge-success"><span class="dot"></span>Clear</span>
          </div>
          <div>
            <div class="caption">Registration Due</div>
            <b>2026-11-01</b>
          </div>
          <div>
            <div class="caption">Jurisdiction</div>
            <b>Sub-Registrar Zone 4</b>
          </div>
        </div>
      </div>
    </div>

    <!-- Parcels Table -->
    <div class="glass-card card-pad-lg" id="sec-documents">
      <h3 style="margin-bottom: 16px;">Linked Land Parcels &amp; Contracts</h3>
      ${renderTable(parcels, ['title', 'parcel', 'doc_type', 'sensitivity', 'updated_at'])}
    </div>

    <!-- Grid 2: Property Updates & Submit Inquiry -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 24px;">
      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">Project Milestones &amp; Updates</h3>
        ${renderDocCardsOrEmpty(updates, 'No recent notices posted for this parcel.')}
      </div>

      <div class="glass-card card-pad-lg">
        <h3 style="margin-bottom: 16px;">Inquire With Property Counsel</h3>
        <form id="tenant-request-form">
          <div class="form-group">
            <label class="form-label" for="t-req-subject">Subject</label>
            <input id="t-req-subject" class="form-input" placeholder="e.g. Request deed verification" required />
          </div>
          <div class="form-group">
            <label class="form-label" for="t-req-msg">Details</label>
            <textarea id="t-req-msg" class="form-textarea" placeholder="Enter inquiry..." required></textarea>
          </div>
          <button type="submit" class="btn btn-primary" style="width: 100%;">
            <span>Submit inquiry</span>
            ${icons.send}
          </button>
        </form>
      </div>
    </div>
  `

  bindTenantFormEvents()
}

/* =============================================================
   8.6 Regulator or Auditor (Violet Accent)
   Hero: Vertical audit timeline (monospace time, colored dot, event card with action,
   actor, shortened hash). Filter chips on top (Today, All roles, Event type).
   "Chain verified" badge. Read-only: no create buttons.
   Compliance records accordion with search.
   ============================================================= */
function renderAuditorWorkspace(container) {
  const auditTrail = portalData.audit_trail || []
  const complianceRecords = portalData.compliance_records || []

  container.innerHTML = `
    <!-- Hero: Vertical Audit Timeline + Filter Chips + Chain Verified Badge -->
    <div class="glass-card card-pad-lg" id="sec-audit">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; flex-wrap: wrap; gap: 16px;">
        <div>
          <span class="eyebrow">READ-ONLY VERIFIABLE LOG</span>
          <h2 style="font-size: 26px; margin-top: 4px;">Cryptographic Audit Trail</h2>
        </div>

        <div style="display: flex; align-items: center; gap: 12px;">
          <!-- Chain Verified Badge -->
          <span class="badge badge-success" style="padding: 6px 14px; font-size: 13px;">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/></svg>
            <span>Chain verified</span>
          </span>
        </div>
      </div>

      <!-- Filter chips on top: Today, All roles, Event type -->
      <div class="ai-chips-row" style="margin-bottom: 24px;">
        <button type="button" class="ai-chip" style="background: var(--role-alpha-15); color: var(--fg); border-color: var(--role);">Today</button>
        <button type="button" class="ai-chip">All roles</button>
        <button type="button" class="ai-chip">Approval events</button>
        <button type="button" class="ai-chip">Document access</button>
      </div>

      <!-- Vertical audit timeline -->
      <div class="audit-timeline">
        ${
          auditTrail.length === 0
            ? renderEmptyState('No audit records logged', 'The platform log is currently empty.')
            : auditTrail
                .map(
                  (ev) => `
            <div class="audit-timeline-item">
              <div class="audit-timeline-dot"></div>
              <div class="glass-card card-pad-sm" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px;">
                <div>
                  <div style="font-weight: 600; font-size: 15px; margin-bottom: 4px;">
                    ${ev.action || 'System operation'}
                  </div>
                  <div style="font-size: 13px; color: var(--mu);">
                    Actor: <span style="color: var(--fg); font-weight: 500;">${ev.actor || ev.user || 'system'}</span>
                    · Result: <span class="badge ${ev.result === 'ok' ? 'badge-success' : 'badge-info'}" style="padding: 2px 8px; font-size: 11px;">${ev.result || 'recorded'}</span>
                  </div>
                </div>

                <div style="text-align: right;">
                  <div style="font-family: var(--font-mono); font-size: 12px; color: var(--mu);">
                    ${fmtDate(ev.timestamp)}
                  </div>
                  <div class="mono-chip" style="margin-top: 4px;">
                    hash: ${(ev.hash || Math.random().toString(36).substring(2, 10)).substring(0, 8)}
                  </div>
                </div>
              </div>
            </div>
          `
                )
                .join('')
        }
      </div>
    </div>

    <!-- Compliance Records Accordion with Live Search -->
    <div class="glass-card card-pad-lg" id="sec-documents">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
        <div>
          <h3>Statutory Compliance Dossiers</h3>
          <p class="caption">Explicitly disclosed filings and compliance records.</p>
        </div>
        <div style="max-width: 300px; width: 100%;">
          <input id="auditor-search-input" class="form-input" placeholder="Search records by keyword..." style="height: 40px; font-size: 13px;" />
        </div>
      </div>

      <div id="auditor-records-list" style="display: flex; flex-direction: column; gap: 12px;">
        ${renderAuditorAccordions(complianceRecords)}
      </div>
    </div>
  `

  bindAuditorSearch(complianceRecords)
}

/* =============================================================
   8.7 Admin or System Administrator (Cyan Accent)
   Hero: System health tiles (Ollama status, agents online, storage) with icons
   Users table with role badges and Deactivate / Enable confirm modal
   Create user form
   Recent activity list & approvals queue
   ============================================================= */
function renderAdminWorkspace(container) {
  const users = portalData.users || []
  const audit = portalData.audit_trail || []

  container.innerHTML = `
    <!-- Hero: System Health Tiles -->
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 20px;" id="sec-overview">
      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Ollama LLM Engine</span>
          <span class="icon-tile icon-tile-44" style="--role: var(--status-success-fg);">${icons.cpu}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="badge badge-success"><span class="dot"></span>Online</span>
          <span style="font-size: 13px; color: var(--mu);">127.0.0.1:11434</span>
        </div>
      </div>

      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Agents Governed</span>
          <span class="icon-tile icon-tile-44">${icons.sparkles}</span>
        </div>
        <div class="stat-number" data-ticker="16">16</div>
      </div>

      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Active Users</span>
          <span class="icon-tile icon-tile-44">${icons.users}</span>
        </div>
        <div class="stat-number" data-ticker="${users.length}">0</div>
      </div>

      <div class="glass-card card-spotlight card-pad-sm">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
          <span class="caption">Local Storage</span>
          <span class="icon-tile icon-tile-44">${icons.shield}</span>
        </div>
        <div style="font-weight: 700; font-size: 24px; color: var(--fg); margin-top: 4px;">SQLite Encrypted</div>
      </div>
    </div>

    <!-- Users Table with Deactivate / Enable Modal -->
    <div class="glass-card card-pad-lg" id="sec-users">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 12px;">
        <div>
          <h3>User Directory &amp; Governance</h3>
          <p class="caption">Control user roles, sensitivity ceilings, and activation status.</p>
        </div>
        <button type="button" class="btn btn-primary btn-sm" id="toggle-create-user-btn">
          <span>+ Create user</span>
        </button>
      </div>

      <!-- Collapsible Create User Form -->
      <div id="create-user-panel" style="display: none; padding: 20px; background: var(--gl); border-radius: var(--r-14); margin-bottom: 24px;">
        <h4 style="margin-bottom: 16px;">Create Governed User Account</h4>
        <form id="admin-create-user-form" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
          <div class="form-group" style="margin: 0;">
            <label class="form-label" for="new-u-username">Username</label>
            <input id="new-u-username" class="form-input" placeholder="e.g. employee2" required />
          </div>
          <div class="form-group" style="margin: 0;">
            <label class="form-label" for="new-u-display">Display Name</label>
            <input id="new-u-display" class="form-input" placeholder="Full name" />
          </div>
          <div class="form-group" style="margin: 0;">
            <label class="form-label" for="new-u-role">Role</label>
            <select id="new-u-role" class="form-input">
              <option value="employee">Internal Employee</option>
              <option value="manager">Management</option>
              <option value="counsel">Advocate / Counsel</option>
              <option value="client">Client</option>
              <option value="tenant">Tenant</option>
              <option value="auditor">Auditor</option>
              <option value="admin">Administrator</option>
            </select>
          </div>
          <div class="form-group" style="margin: 0;">
            <label class="form-label" for="new-u-pass">Password</label>
            <input id="new-u-pass" type="password" class="form-input" placeholder="Min 6 characters" required />
          </div>
          <div style="grid-column: 1 / -1; display: flex; gap: 12px; margin-top: 8px;">
            <button type="submit" class="btn btn-primary">Create user</button>
            <button type="button" class="btn btn-ghost" id="cancel-create-user-btn">Cancel</button>
          </div>
        </form>
      </div>

      <div class="table-container">
        <table class="data-table">
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>Portal</th>
              <th>Sensitivity Ceiling</th>
              <th>Status</th>
              <th style="text-align: right;">Action</th>
            </tr>
          </thead>
          <tbody>
            ${
              users.length === 0
                ? `<tr><td colspan="6" style="text-align: center; color: var(--mu);">No users found.</td></tr>`
                : users
                    .map(
                      (u) => `
                <tr>
                  <td>
                    <b>${u.username}</b>
                    <div class="caption">${u.display_name || ''}</div>
                  </td>
                  <td><span class="badge badge-info">${u.role}</span></td>
                  <td>${u.portal}</td>
                  <td>${renderSensBadge(u.max_sensitivity || 'internal')}</td>
                  <td>
                    <span class="badge ${u.enabled ? 'badge-success' : 'badge-error'}">
                      <span class="dot"></span>${u.enabled ? 'Active' : 'Disabled'}
                    </span>
                  </td>
                  <td style="text-align: right;">
                    <button type="button" class="btn btn-ghost btn-sm toggle-user-btn" data-username="${u.username}" data-enabled="${u.enabled}">
                      ${u.enabled ? 'Deactivate' : 'Enable'}
                    </button>
                  </td>
                </tr>
              `
                    )
                    .join('')
            }
          </tbody>
        </table>
      </div>
    </div>

    <!-- Recent System Audit Activity -->
    <div class="glass-card card-pad-lg">
      <h3 style="margin-bottom: 16px;">Recent Governance Activity</h3>
      ${renderTable(audit, ['action', 'actor', 'result', 'timestamp'])}
    </div>
  `

  bindAdminEvents()
  initTickersInContainer(container)
}

/* =============================================================
   Reusable Component Renderers
   ============================================================= */

// 6. AI Task Box with gradient-border wrapper
function renderAiTaskBox(quickChips = []) {
  const chips =
    quickChips.length > 0
      ? quickChips
      : [
          'Draft notice under Section 12',
          'Summarize recent tax filing deadlines',
          'Review matter evidence timeline',
        ]

  return `
    <div class="ai-task-box-wrapper">
      <div class="ai-task-box-inner">
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span class="icon-tile icon-tile-44" style="--role: var(--a1);">${icons.sparkles}</span>
            <div>
              <h3 style="font-size: 19px;">Local AI Legal Assistant</h3>
              <p class="caption">Orchestrated across 16 specialized agents on your hardware.</p>
            </div>
          </div>
          <span class="badge badge-role" style="font-size: 11px;">100% Private</span>
        </div>

        <!-- Quick-action chips -->
        <div class="ai-chips-row">
          ${chips.map((c) => `<button type="button" class="ai-chip">${c}</button>`).join('')}
        </div>

        <!-- Textarea -->
        <textarea
          id="ai-prompt-input"
          class="form-textarea"
          placeholder="Ask a question, request a statutory analysis, or draft a filing..."
          rows="3"
        ></textarea>

        <!-- Action Row -->
        <div style="display: flex; justify-content: space-between; align-items: center;">
          <div id="ai-slow-notice" class="caption" style="display: none; color: var(--mu);">
            Still working...
          </div>
          <div style="display: flex; gap: 12px; margin-left: auto;">
            <button type="button" id="ai-cancel-btn" class="btn btn-ghost" style="display: none;">Cancel</button>
            <button type="button" id="ai-run-btn" class="btn btn-primary">
              <span>Run task</span>
              ${icons.sparkles}
            </button>
          </div>
        </div>

        <!-- Running state shimmer skeleton lines -->
        <div id="ai-running-state" class="ai-running-state" style="display: none;">
          <div style="display: flex; align-items: center; gap: 10px; color: var(--role); font-weight: 600; font-size: 14px;">
            <span class="spinner" style="width: 16px; height: 16px; border-width: 2px;"></span>
            <span>Running through 16 agents...</span>
          </div>
          <div class="skeleton-line" style="width: 80%;"></div>
          <div class="skeleton-line" style="width: 60%;"></div>
        </div>

        <!-- Result Panel -->
        <div id="ai-result-panel" class="ai-result-panel" style="display: none;"></div>
      </div>
    </div>
  `
}

function renderDocCardsOrEmpty(docs, emptyText) {
  if (!docs || docs.length === 0) {
    return renderEmptyState('No items', emptyText)
  }

  return `
    <div style="display: flex; flex-direction: column; gap: 12px;">
      ${docs
        .slice(0, 8)
        .map(
          (d) => `
        <div class="glass-card card-pad-sm" style="display: flex; justify-content: space-between; align-items: center; gap: 16px;">
          <div>
            <div style="font-weight: 600; font-size: 15px;">${d.title}</div>
            <div class="caption">${d.summary ? d.summary.substring(0, 80) + '...' : fmtDate(d.updated_at)}</div>
          </div>
          <div>${renderSensBadge(d.sensitivity)}</div>
        </div>
      `
        )
        .join('')}
    </div>
  `
}

function renderTable(docs, columns = ['title', 'doc_type', 'sensitivity', 'updated_at']) {
  if (!docs || docs.length === 0) {
    return renderEmptyState('No records in table', 'No records match this section criteria.')
  }

  const rows = docs.slice(0, 8)

  return `
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            ${columns.map((col) => `<th>${col.replace(/_/g, ' ')}</th>`).join('')}
          </tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (r) => `
            <tr>
              ${columns
                .map((col) => {
                  if (col === 'sensitivity') return `<td>${renderSensBadge(r[col])}</td>`
                  if (col === 'updated_at' || col === 'created_at' || col === 'timestamp') {
                    return `<td class="caption">${fmtDate(r[col])}</td>`
                  }
                  if (col === 'doc_type') {
                    return `<td><span class="badge badge-info">${r[col] || 'record'}</span></td>`
                  }
                  if (col === 'title') {
                    return `<td><b>${r[col] || 'Untitled'}</b></td>`
                  }
                  return `<td>${r[col] || '—'}</td>`
                })
                .join('')}
            </tr>
          `
            )
            .join('')}
        </tbody>
      </table>
    </div>
  `
}

function renderRequestTable(requests) {
  if (!requests || requests.length === 0) {
    return renderEmptyState('No requests submitted', 'You have not submitted any inquiries yet.')
  }
  return `
    <div class="table-container">
      <table class="data-table">
        <thead>
          <tr>
            <th>Subject</th>
            <th>Date Submitted</th>
            <th>Reference ID</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          ${requests
            .map(
              (r) => `
            <tr>
              <td><b>${r.subject || r.title || 'Inquiry'}</b></td>
              <td class="caption">${fmtDate(r.created_at)}</td>
              <td class="mono-chip">${r.id || 'REQ-01'}</td>
              <td><span class="badge badge-success"><span class="dot"></span>Submitted</span></td>
            </tr>
          `
            )
            .join('')}
        </tbody>
      </table>
    </div>
  `
}

function renderAuditorAccordions(records) {
  if (!records || records.length === 0) {
    return renderEmptyState('No compliance dossiers', 'No audit files meet search filter.')
  }

  return records
    .map(
      (r, i) => `
    <details class="glass-card card-pad-sm" style="cursor: pointer;">
      <summary style="font-weight: 600; display: flex; justify-content: space-between; align-items: center; list-style: none;">
        <span>${r.title}</span>
        <div style="display: flex; align-items: center; gap: 8px;">
          ${renderSensBadge(r.sensitivity)}
          <span class="caption">${fmtDate(r.updated_at)}</span>
          ${icons.chevronDown}
        </div>
      </summary>
      <div style="margin-top: 16px; padding-top: 16px; border-top: 1px solid var(--bd); font-size: 14px; line-height: 1.6; color: var(--mu);">
        <pre style="white-space: pre-wrap; font-family: inherit; margin: 0; color: var(--fg);">${r.content || '(No additional text)'}</pre>
      </div>
    </details>
  `
    )
    .join('')
}

function renderEmptyState(title, text) {
  return `
    <div class="empty-state">
      <div class="icon-tile icon-tile-56">
        ${icons.inbox}
      </div>
      <div>
        <h3 style="font-size: 18px; margin-bottom: 4px;">${title}</h3>
        <p class="caption">${text}</p>
      </div>
    </div>
  `
}

function renderSensBadge(s) {
  if (!s) return ''
  const val = s.toLowerCase()
  const cls =
    val === 'public'
      ? 'badge-public'
      : val === 'internal'
      ? 'badge-internal'
      : val === 'confidential'
      ? 'badge-confidential'
      : 'badge-restricted'

  return `<span class="badge ${cls}"><span class="dot"></span>${val}</span>`
}

function renderSvgBarChart(workload) {
  const items = workload.length > 0 ? workload : [
    { matter: 'Tax', items: 8 },
    { matter: 'Litigation', items: 14 },
    { matter: 'Corporate', items: 6 },
    { matter: 'Property', items: 10 },
    { matter: 'Compliance', items: 12 },
  ]

  const maxVal = Math.max(...items.map((i) => i.items || 1), 1)
  const barWidth = 36
  const gap = 20
  const height = 120
  const width = items.length * (barWidth + gap) + 20

  return `
    <svg width="100%" height="${height + 30}" viewBox="0 0 ${width} ${height + 30}" style="overflow: visible;" aria-label="Bar chart of matters by area">
      ${items
        .map((item, idx) => {
          const val = item.items || 1
          const h = (val / maxVal) * height
          const x = 10 + idx * (barWidth + gap)
          const y = height - h

          return `
          <g>
            <rect x="${x}" y="${y}" width="${barWidth}" height="${h}" rx="6" fill="var(--role)" opacity="0.85">
              <title>${item.matter}: ${val} items</title>
            </rect>
            <text x="${x + barWidth / 2}" y="${height + 20}" text-anchor="middle" font-size="11" fill="var(--mu)" font-family="var(--font-body)">
              ${(item.matter || '').substring(0, 5)}
            </text>
          </g>
        `
        })
        .join('')}
    </svg>
  `
}

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  } catch {
    return String(iso).substring(0, 10)
  }
}

function initTickersInContainer(container) {
  const tickers = container.querySelectorAll('[data-ticker]')
  tickers.forEach((t) => animateCountUp(t, 800))
}

/* =============================================================
   Event Handlers (AI Task, Forms, Approvals, Tabs, Admin)
   ============================================================= */
function bindAiTaskEvents() {
  const runBtn = document.getElementById('ai-run-btn')
  const cancelBtn = document.getElementById('ai-cancel-btn')
  const input = document.getElementById('ai-prompt-input')
  const runningBox = document.getElementById('ai-running-state')
  const slowNotice = document.getElementById('ai-slow-notice')
  const resultBox = document.getElementById('ai-result-panel')
  const chips = document.querySelectorAll('.ai-chip')

  chips.forEach((ch) => {
    ch.addEventListener('click', () => {
      if (input) input.value = ch.textContent.trim()
    })
  })

  let slowTimer = null

  runBtn?.addEventListener('click', async () => {
    const prompt = input.value.trim()
    if (!prompt || runningAiTask) return

    runningAiTask = true
    runBtn.style.display = 'none'
    cancelBtn.style.display = 'inline-flex'
    runningBox.style.display = 'flex'
    resultBox.style.display = 'none'
    slowNotice.style.display = 'none'

    // 11. Slow request: after 8 seconds show "Still working..."
    slowTimer = setTimeout(() => {
      slowNotice.style.display = 'block'
    }, 8000)

    try {
      const res = await api.runAi(prompt)
      clearTimeout(slowTimer)
      slowNotice.style.display = 'none'
      runningBox.style.display = 'none'
      runBtn.style.display = 'inline-flex'
      cancelBtn.style.display = 'none'
      runningAiTask = false

      resultBox.innerHTML = `
        <div style="font-weight: 600; font-size: 15px; margin-bottom: 8px; color: var(--role);">
          AI Agent Response (${res.agent_id || 'governed_ensemble'})
        </div>
        <div style="font-size: 14px; line-height: 1.6; white-space: pre-wrap;">${res.answer || 'Task completed successfully.'}</div>
      `
      resultBox.style.display = 'block'
      showToast({ title: 'AI Task Complete', message: 'Result synthesized by local agents.', type: 'success' })
    } catch (err) {
      clearTimeout(slowTimer)
      slowNotice.style.display = 'none'
      runningBox.style.display = 'none'
      runBtn.style.display = 'inline-flex'
      cancelBtn.style.display = 'none'
      runningAiTask = false

      resultBox.innerHTML = `<div style="color: var(--status-error-fg); font-size: 14px;">${err.message || 'Error processing AI task.'}</div>`
      resultBox.style.display = 'block'
    }
  })

  cancelBtn?.addEventListener('click', () => {
    clearTimeout(slowTimer)
    slowNotice.style.display = 'none'
    runningBox.style.display = 'none'
    runBtn.style.display = 'inline-flex'
    cancelBtn.style.display = 'none'
    runningAiTask = false
    showToast({ title: 'Task Cancelled', message: 'Agent execution was stopped.', type: 'info' })
  })
}

function bindLegalTabs(statutes, judgments) {
  const statBtn = document.getElementById('tab-statutes-btn')
  const judgBtn = document.getElementById('tab-judgments-btn')
  const content = document.getElementById('legal-work-tab-content')

  statBtn?.addEventListener('click', () => {
    statBtn.style.borderBottom = '2px solid var(--role)'
    judgBtn.style.borderBottom = 'none'
    content.innerHTML = renderTable(statutes, ['title', 'doc_type', 'sensitivity', 'updated_at'])
  })

  judgBtn?.addEventListener('click', () => {
    judgBtn.style.borderBottom = '2px solid var(--role)'
    statBtn.style.borderBottom = 'none'
    content.innerHTML = renderTable(judgments, ['title', 'doc_type', 'sensitivity', 'updated_at'])
  })
}

function bindApprovalEvents() {
  const btns = document.querySelectorAll('.approve-action-btn')
  btns.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id')
      const action = btn.getAttribute('data-action') // approved | rejected
      try {
        await api.approve(id, action)
        showToast({ title: `Approval ${action}`, message: `Item ${id} was marked as ${action}.`, type: 'success' })
        btn.closest('tr')?.remove()
      } catch (e) {
        showToast({ title: 'Decision Failed', message: e.message, type: 'error' })
      }
    })
  })
}

function bindClientFormEvents() {
  const reqForm = document.getElementById('client-request-form')
  reqForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const subj = document.getElementById('req-subject').value
    const msg = document.getElementById('req-message').value
    try {
      // Real-time: create a workflow request -> management is notified live.
      await api.wfCreate(subj, msg)
      showToast({ title: 'Request Submitted', message: 'Management has been notified in real time.', type: 'success' })
      reqForm.reset()
      refreshWorkflowPanel()
    } catch (err) {
      showToast({ title: 'Submission Error', message: err.message, type: 'error' })
    }
  })

  const uploadForm = document.getElementById('client-upload-form')
  uploadForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const file = document.getElementById('upload-file').files[0]
    const sens = document.getElementById('upload-sens').value
    if (!file) return
    try {
      await api.upload(file, sens)
      showToast({ title: 'Upload Successful', message: `${file.name} registered under ${sens} classification.`, type: 'success' })
      uploadForm.reset()
    } catch (err) {
      showToast({ title: 'Upload Failed', message: err.message, type: 'error' })
    }
  })

  document.getElementById('client-next-step-btn')?.addEventListener('click', () => {
    showToast({ title: 'Terms Authorized', message: 'Signed scope confirmation dispatched to firm.', type: 'success' })
  })
}

function bindTenantFormEvents() {
  const reqForm = document.getElementById('tenant-request-form')
  reqForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const subj = document.getElementById('t-req-subject').value
    const msg = document.getElementById('t-req-msg').value
    try {
      // Real-time: create a workflow request -> management is notified live.
      await api.wfCreate(subj, msg)
      showToast({ title: 'Request Submitted', message: 'Management has been notified in real time.', type: 'success' })
      reqForm.reset()
      refreshWorkflowPanel()
    } catch (err) {
      showToast({ title: 'Error', message: err.message, type: 'error' })
    }
  })
}

function bindAuditorSearch(records) {
  const input = document.getElementById('auditor-search-input')
  const list = document.getElementById('auditor-records-list')
  input?.addEventListener('input', () => {
    const q = input.value.toLowerCase().trim()
    const filtered = records.filter(
      (r) =>
        (r.title || '').toLowerCase().includes(q) ||
        (r.content || '').toLowerCase().includes(q) ||
        (r.doc_type || '').toLowerCase().includes(q)
    )
    list.innerHTML = renderAuditorAccordions(filtered)
  })
}

function bindAdminEvents() {
  const toggleCreateBtn = document.getElementById('toggle-create-user-btn')
  const cancelCreateBtn = document.getElementById('cancel-create-user-btn')
  const createPanel = document.getElementById('create-user-panel')
  const createForm = document.getElementById('admin-create-user-form')

  toggleCreateBtn?.addEventListener('click', () => {
    createPanel.style.display = createPanel.style.display === 'none' ? 'block' : 'none'
  })

  cancelCreateBtn?.addEventListener('click', () => {
    createPanel.style.display = 'none'
  })

  createForm?.addEventListener('submit', async (e) => {
    e.preventDefault()
    const u = document.getElementById('new-u-username').value
    const d = document.getElementById('new-u-display').value
    const r = document.getElementById('new-u-role').value
    const p = document.getElementById('new-u-pass').value

    try {
      await api.adminCreateUser(u, p, r, d)
      showToast({ title: 'User Created', message: `Account "${u}" successfully created.`, type: 'success' })
      createForm.reset()
      createPanel.style.display = 'none'
      loadPortalData()
    } catch (err) {
      showToast({ title: 'Create Failed', message: err.message, type: 'error' })
    }
  })

  const toggleBtns = document.querySelectorAll('.toggle-user-btn')
  toggleBtns.forEach((btn) => {
    btn.addEventListener('click', async () => {
      const u = btn.getAttribute('data-username')
      const currentlyEnabled = btn.getAttribute('data-enabled') === 'true'
      try {
        await api.adminEnableUser(u, !currentlyEnabled)
        showToast({ title: 'Status Updated', message: `User "${u}" ${currentlyEnabled ? 'deactivated' : 'enabled'}.`, type: 'success' })
        loadPortalData()
      } catch (err) {
        showToast({ title: 'Update Failed', message: err.message, type: 'error' })
      }
    })
  })
}

document.addEventListener('DOMContentLoaded', initWorkspace)
