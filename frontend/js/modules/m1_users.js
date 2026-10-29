/**
 * Module M1: Login, User Management, Roles & Permissions, Access Requests, Profile
 * Routes: /login, /admin/users, /profile
 */
import { api } from '../services/api.js';
import { state } from '../services/state.js';
import { renderStatusBadge, renderStepper, renderTableSkeleton } from '../components/shared.js';
import { formatDate } from '../formatters.js';

export async function renderLoginView(container) {
  container.innerHTML = `
    <div style="min-height: calc(100vh - 120px); display: flex; align-items: center; justify-content: center; padding: 20px;">
      <div class="card" style="width: 100%; max-width: 440px; padding: 36px; box-shadow: var(--shadow-lg);">
        <div style="text-align: center; margin-bottom: 28px;">
          <div style="width: 48px; height: 48px; background: linear-gradient(135deg, #6366F1, #4338CA); border-radius: 12px; margin: 0 auto 16px; display:flex; align-items:center; justify-content:center; color:#fff; font-size:22px; font-weight:bold;">M</div>
          <h2 style="font-size: var(--font-size-lg); font-weight: 700; color: var(--text-main);">Sign in to Meridian</h2>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">Group Enterprise Law, Debt & Asset Platform</p>
        </div>

        <!-- Unusual Login Alert Banner (State specified in M1) -->
        <div id="unusual-login-alert" style="display:none; background: var(--color-warning-bg); border: 1px solid var(--color-warning-border); padding: 10px 14px; border-radius: 8px; font-size: 12px; color: var(--color-warning-text); margin-bottom: 16px;">
          ⚠️ <strong>Unusual Login Alert:</strong> New sign-in attempt detected from unrecognized subnet. Multi-factor verification is required.
        </div>

        <!-- Step 1: Email / SSO -->
        <div id="login-step-email">
          <button type="button" class="btn btn-secondary" style="width: 100%; margin-bottom: 16px; justify-content: center;" onclick="window.triggerMFA('sso@meridianinfra.in')">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            Sign in with Enterprise SSO (SAML 2.0)
          </button>

          <div style="display:flex; align-items:center; text-align:center; margin: 20px 0; color: var(--text-tertiary); font-size: 12px;">
            <div style="flex:1; border-bottom: 1px solid var(--border-subtle);"></div>
            <span style="padding: 0 10px;">or email address</span>
            <div style="flex:1; border-bottom: 1px solid var(--border-subtle);"></div>
          </div>

          <div class="form-group">
            <label class="form-label">Corporate Email</label>
            <input type="email" id="login-email" class="form-control" value="admin@meridianinfra.in" placeholder="name@meridianinfra.in" />
          </div>

          <button type="button" class="btn btn-primary" style="width: 100%; justify-content: center; margin-top: 8px;" onclick="window.triggerMFA()">
            Continue to Verification →
          </button>
        </div>

        <!-- Step 2: 6-digit MFA Code Entry (auto-advance & 30s resend timer) -->
        <div id="login-step-mfa" style="display: none;">
          <div style="text-align: center; margin-bottom: 20px;">
            <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">Enter Two-Factor Code</div>
            <div style="font-size: 12px; color: var(--text-muted);">A 6-digit code was sent to your authenticator application.</div>
          </div>

          <div style="display: flex; gap: 8px; justify-content: center; margin-bottom: 24px;">
            <input type="text" maxlength="1" class="mfa-box form-control" style="width: 44px; height: 50px; text-align: center; font-size: 20px; font-weight: bold;" autofocus />
            <input type="text" maxlength="1" class="mfa-box form-control" style="width: 44px; height: 50px; text-align: center; font-size: 20px; font-weight: bold;" />
            <input type="text" maxlength="1" class="mfa-box form-control" style="width: 44px; height: 50px; text-align: center; font-size: 20px; font-weight: bold;" />
            <input type="text" maxlength="1" class="mfa-box form-control" style="width: 44px; height: 50px; text-align: center; font-size: 20px; font-weight: bold;" />
            <input type="text" maxlength="1" class="mfa-box form-control" style="width: 44px; height: 50px; text-align: center; font-size: 20px; font-weight: bold;" />
            <input type="text" maxlength="1" class="mfa-box form-control" style="width: 44px; height: 50px; text-align: center; font-size: 20px; font-weight: bold;" />
          </div>

          <button type="button" class="btn btn-primary" style="width: 100%; justify-content: center;" onclick="window.completeLogin()">
            Verify & Authenticate
          </button>

          <div style="display:flex; justify-content:space-between; align-items:center; margin-top: 16px; font-size: 12px;">
            <button type="button" style="color:var(--text-muted);" onclick="window.backToEmail()">← Back</button>
            <span id="mfa-resend-countdown" style="color:var(--text-tertiary);">Resend code in 30s</span>
          </div>

          <!-- Session Timeout Warning Notice -->
          <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border-subtle); font-size: 11px; color: var(--text-tertiary); text-align: center;">
            🔒 Inactivity warning enabled: Active session will prompt 2 minutes before expiration.
          </div>
        </div>
      </div>
    </div>
  `;

  // Attach MFA box auto-advance logic
  const boxes = container.querySelectorAll('.mfa-box');
  boxes.forEach((box, i) => {
    box.addEventListener('input', (e) => {
      if (box.value.length === 1 && i < boxes.length - 1) {
        boxes[i + 1].focus();
      }
    });
    box.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && !box.value && i > 0) {
        boxes[i - 1].focus();
      }
    });
  });

  window.triggerMFA = () => {
    document.getElementById('login-step-email').style.display = 'none';
    document.getElementById('login-step-mfa').style.display = 'block';
    boxes[0].focus();
    let seconds = 30;
    const timer = setInterval(() => {
      seconds--;
      const el = document.getElementById('mfa-resend-countdown');
      if (el) {
        if (seconds > 0) {
          el.textContent = `Resend code in ${seconds}s`;
        } else {
          el.innerHTML = `<a href="javascript:void(0)" onclick="window.triggerMFA()">Resend code</a>`;
          clearInterval(timer);
        }
      }
    }, 1000);
  };

  window.backToEmail = () => {
    document.getElementById('login-step-email').style.display = 'block';
    document.getElementById('login-step-mfa').style.display = 'none';
  };

  window.completeLogin = () => {
    window.MeridianApp.showToast('Authentication successful. Welcome, Rajesh Sharma.', 'success');
    window.location.hash = '#/home';
  };
}

export async function renderUsersView(container) {
  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>Administration</span>
        <span class="breadcrumb-separator">/</span>
        <span>User Management</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">User Management & Permissions</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Enterprise role-based access control (RBAC), multi-entity assignment, and active sessions.
          </p>
        </div>
        <div class="page-actions">
          <button type="button" class="btn btn-secondary btn-sm" onclick="window.openAccessRequestsModal()">
            Access Requests (3)
          </button>
          <button type="button" class="btn btn-primary btn-sm" onclick="window.openAddUserModal()">
            + Add User (Stepper)
          </button>
        </div>
      </div>
    </div>

    <!-- Tabs: Users List, Roles & Permissions Matrix, Access Requests -->
    <div class="tabs-nav">
      <button class="tab-btn active" onclick="window.switchUserTab('list')">All Users</button>
      <button class="tab-btn" onclick="window.switchUserTab('matrix')">Roles & Permissions Matrix</button>
      <button class="tab-btn" onclick="window.switchUserTab('requests')">Access Requests Inbox</button>
    </div>

    <div id="users-tab-content">
      ${renderTableSkeleton(6, 6)}
    </div>
  `;

  const users = await api.getUsers();
  renderUserListTable(users);

  window.switchUserTab = (tab) => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');
    const target = document.getElementById('users-tab-content');
    if (tab === 'list') {
      renderUserListTable(users);
    } else if (tab === 'matrix') {
      renderPermissionsMatrix(target);
    } else if (tab === 'requests') {
      renderAccessRequestsInbox(target);
    }
  };
}

function renderUserListTable(users) {
  const target = document.getElementById('users-tab-content');
  if (!target) return;

  target.innerHTML = `
    <div class="table-container">
      <div class="table-toolbar">
        <input type="text" class="table-search-input" id="user-filter-input" placeholder="Search user name, email, or role..." />
        <div class="filter-chip-group">
          <span class="filter-chip active" onclick="window.filterUsers('all')">All Roles</span>
          <span class="filter-chip" onclick="window.filterUsers('Administrator')">Admin</span>
          <span class="filter-chip" onclick="window.filterUsers('Lawyer')">Lawyer</span>
          <span class="filter-chip" onclick="window.filterUsers('Manager / Board member')">Board / Manager</span>
          <span class="filter-chip" onclick="window.filterUsers('Tax team member')">Tax</span>
        </div>
      </div>
      <table class="data-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Email</th>
            <th>Role</th>
            <th>Assigned Companies</th>
            <th>Last Login</th>
            <th>MFA</th>
            <th>Status</th>
            <th style="text-align:right;">Actions</th>
          </tr>
        </thead>
        <tbody>
          ${users.map(u => `
            <tr>
              <td>
                <div style="display:flex; align-items:center; gap:10px;">
                  <div class="user-avatar" style="width:28px; height:28px; font-size:11px;">${u.avatar}</div>
                  <strong style="color:var(--text-main);">${u.name}</strong>
                </div>
              </td>
              <td>${u.email}</td>
              <td><span style="font-weight:600; color:var(--primary);">${u.role}</span></td>
              <td>${u.allowedCompanies.includes('ALL') ? 'All Group Companies' : u.allowedCompanies.join(', ')}</td>
              <td style="font-size:12px; color:var(--text-muted);">${u.lastLogin}</td>
              <td>${u.mfaEnabled ? '✓ Enforced' : '✕ Disabled'}</td>
              <td>${renderStatusBadge(u.status)}</td>
              <td style="text-align:right;">
                <button class="btn btn-secondary btn-sm" onclick="window.openEditUser('${u.id}')">Edit</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderPermissionsMatrix(target) {
  const roles = ['Administrator', 'Manager / Board member', 'Lawyer', 'Tax team member', 'Company secretary', 'Finance team member', 'Staff member', 'External counsel'];
  const modules = ['Companies', 'Loans & Settlements', 'Land & Title', 'Cases & Matters', 'Tax Notices', 'Documents', 'Drafting', 'Approvals', 'Reports', 'AI Control'];

  target.innerHTML = `
    <div class="card">
      <div style="font-weight:700; font-size:15px; margin-bottom:6px;">Enterprise RBAC Permission Matrix</div>
      <p style="font-size:12px; color:var(--text-muted); margin-bottom:16px;">
        Fine-grained matrix specifying View, Create, Edit, Approve, and Bulk Export actions per module according to Section 4 specifications.
      </p>
      <div style="overflow-x:auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Role</th>
              ${modules.map(m => `<th>${m}</th>`).join('')}
            </tr>
          </thead>
          <tbody>
            ${roles.map(r => `
              <tr>
                <td><strong>${r}</strong></td>
                ${modules.map(m => {
                  let badge = 'View';
                  if (r === 'Administrator') badge = 'Full Control';
                  else if (r === 'Manager / Board member' && (m === 'Approvals' || m === 'Reports' || m === 'Loans & Settlements')) badge = 'Approve & View';
                  else if (r === 'Lawyer' && (m === 'Cases & Matters' || m === 'Drafting')) badge = 'Create & Edit';
                  else if (r === 'Tax team member' && m === 'Tax Notices') badge = 'Create & Edit';
                  else if (r === 'External counsel' && m !== 'Cases & Matters' && m !== 'Documents') badge = '—';
                  return `<td><span style="font-size:11px; padding:2px 6px; background:var(--bg-subtle); border-radius:4px;">${badge}</span></td>`;
                }).join('')}
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

function renderAccessRequestsInbox(target) {
  target.innerHTML = `
    <div class="card">
      <div style="font-weight:700; font-size:15px; margin-bottom:16px;">Pending Privilege & Access Requests</div>
      <div style="display:flex; flex-direction:column; gap:12px;">
        <div style="padding:16px; border:1px solid var(--border-subtle); border-radius:8px; display:flex; justify-content:space-between; align-items:center;">
          <div>
            <div style="font-weight:600; font-size:14px;">Adv. Harish Salve Associates requests temporary read access to Survey 89/2 (Parcel P-003)</div>
            <div style="font-size:12px; color:var(--text-muted); margin-top:2px;">Reason: Required to prepare rejoinder in companion title suit OS 891/2025. Requested until: 30 Nov 2026.</div>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Access request rejected.', 'warning')">Reject</button>
            <button class="btn btn-primary btn-sm" onclick="window.MeridianApp.showToast('Temporary access approved until 30 Nov 2026.', 'success')">Approve with Expiry</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

export async function renderProfileView(container) {
  const user = state.currentUser || { name: 'Rajesh Sharma', email: 'admin@meridianinfra.in', role: 'Administrator' };

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>My Profile</span>
      </div>
      <h1 class="page-title">Personal Settings & Session</h1>
    </div>

    <div style="display:grid; grid-template-columns: 1fr 2fr; gap:24px;">
      <div class="card">
        <div style="text-align:center; padding-bottom:16px; border-bottom:1px solid var(--border-subtle); margin-bottom:16px;">
          <div class="user-avatar" style="width:64px; height:64px; font-size:24px; margin:0 auto 12px;">${user.avatar || 'US'}</div>
          <h2 style="font-size:16px; font-weight:700;">${user.name}</h2>
          <div style="font-size:13px; color:var(--primary); font-weight:600;">${user.role}</div>
          <div style="font-size:12px; color:var(--text-muted);">${user.email}</div>
        </div>

        <div style="display:flex; flex-direction:column; gap:12px; font-size:13px;">
          <div style="display:flex; justify-content:space-between;">
            <span style="color:var(--text-muted);">MFA Status:</span>
            <span style="color:var(--color-success); font-weight:600;">Active (TOTP)</span>
          </div>
          <div style="display:flex; justify-content:space-between;">
            <span style="color:var(--text-muted);">Session Idle Timeout:</span>
            <span>15 minutes</span>
          </div>
        </div>

        <div style="margin-top:24px; padding-top:16px; border-top:1px solid var(--border-subtle);">
          <button type="button" class="btn btn-secondary logout-trigger-btn" onclick="window.MeridianApp?.setupLogout && window.document.getElementById('signout-modal')?.classList.add('active')" style="color:var(--color-danger); border-color:var(--color-danger); width:100%; justify-content:center; gap:8px;">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/></svg>
            <span>Sign out of Nushift</span>
          </button>
        </div>
      </div>

      <div class="card">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:16px;">Notification Channels & Quiet Hours</h3>
        <div style="display:flex; flex-direction:column; gap:16px;">
          <label style="display:flex; align-items:center; gap:10px; font-size:13px;">
            <input type="checkbox" checked /> Email alerts for high-priority legal & tax notices
          </label>
          <label style="display:flex; align-items:center; gap:10px; font-size:13px;">
            <input type="checkbox" checked /> In-app desktop notification banners
          </label>
          <label style="display:flex; align-items:center; gap:10px; font-size:13px;">
            <input type="checkbox" /> Automated voice calls for unacknowledged 48-hour deadlines
          </label>
          <div style="padding-top:12px; border-top:1px solid var(--border-subtle);">
            <div style="font-weight:600; font-size:13px; margin-bottom:4px;">Quiet Hours</div>
            <div style="font-size:12px; color:var(--text-muted); margin-bottom:8px;">Do not send non-critical alerts between 10:00 PM and 08:00 AM IST.</div>
            <input type="text" class="form-control" style="max-width:240px;" value="22:00 - 08:00 IST" />
          </div>
        </div>

        <h3 style="font-size:15px; font-weight:700; margin-top:24px; margin-bottom:12px;">Recent Login History</h3>
        <div style="font-size:12px; color:var(--text-muted); line-height:1.8;">
          • 28 Oct 2026, 09:14 AM — Mumbai, India (IP: 103.21.144.12) • Current Session<br>
          • 27 Oct 2026, 08:50 AM — Mumbai, India (IP: 103.21.144.12)<br>
          • 26 Oct 2026, 10:02 AM — Mumbai, India (IP: 103.21.144.12)
        </div>
      </div>
    </div>
  `;
}
