/**
 * Main Application Orchestrator
 * Coordinates Navigation, Role Visibility, Topbar Controls, Drawer, and Module Views
 */
import { state } from './services/state.js';
import { Router } from './router.js';
import { DrawerController, DocumentViewerModal } from './components/drawer.js';
import { setCurrencyMode, setAreaMode, getCurrencyMode, getAreaMode } from './formatters.js';

// Module view imports (dynamically loaded or imported)
import { renderHomeView, renderAskView } from './modules/m2_home_ask.js';
import { renderLoginView, renderUsersView, renderProfileView } from './modules/m1_users.js';
import { renderDocumentsView, renderVerificationQueueView, renderDuplicatesView } from './modules/m3_documents.js';
import { renderCompaniesView, renderCompanyDetailView, renderGroupTreeView, renderFilingTrackerView } from './modules/m4_companies.js';
import { renderLoansView, renderLoanDetailView, renderExposureLedgerView, renderSettlementsView, renderSecurityReleaseView } from './modules/m5_loans.js';
import { renderLandView, renderParcelDetailView, renderEncumbranceRegisterView } from './modules/m6_land.js';
import { renderMattersView, renderMatterDetailView, renderHearingDiaryView, renderCreateMatterView } from './modules/m7_matters.js';
import { renderResearchView, renderSavedResearchView } from './modules/m8_research.js';
import { renderDraftingView, renderDraftEditorView } from './modules/m9_drafting.js';
import { renderTaxView, renderTaxDetailView } from './modules/m10_tax.js';
import { renderCalendarView, renderTasksView, renderLimitationCalcView } from './modules/m11_calendar.js';
import { renderNotificationsView, renderMessageApprovalView, renderCallLogView } from './modules/m12_notifications.js';
import { renderApprovalsView, renderApprovalReviewView } from './modules/m13_approvals.js';
import { renderReportsView, renderReportBuilderView } from './modules/m14_reports.js';
import { renderKnowledgeView, renderOutsideLookupsView } from './modules/m15_knowledge.js';
import { renderSecurityView, renderAuditLogView } from './modules/m16_security.js';
import { renderAdminView, renderAgentDetailView, renderQualityTestsView } from './modules/m17_admin.js';

class MeridianApp {
  constructor() {
    this.drawer = new DrawerController();
    this.docViewer = new DocumentViewerModal();
    this.router = null;
  }

  async start() {
    // 1. Initialize State and load all JSON mock databases
    await state.init();

    // 2. Initialize Drawers
    this.drawer.init();

    // 3. Setup Global Nav & Sidebar
    this.renderSidebar();

    // 4. Setup Topbar & Listeners
    this.setupTopbar();

    // 5. Setup Command Palette
    this.setupCommandPalette();

    // 6. Setup Router
    this.setupRouter();

    // 7. Setup Logout & Auth management
    this.setupLogout();

    // 8. Setup Profile Menus (topbar avatar dropdown & sidebar bottom popover)
    this.setupProfileMenus();

    // 9. Initial active nav highlighting
    this.updateActiveNav(window.location.hash || '#/home');

    // Listen to role changes to re-render sidebar and navigate appropriately
    state.on('role-changed', () => {
      this.renderSidebar();
      this.updateUserUI();
      this.updateActiveNav(window.location.hash || '#/home');
      this.router.handleRoute();
      this.showToast(`Switched active role to ${state.currentRole}`, 'info');
    });

    state.on('company-changed', () => {
      this.router.handleRoute();
      this.showToast(`Active group company filter changed`, 'info');
    });

    // Expose global controller
    window.MeridianApp = this;
  }

  setupRouter() {
    const mainContainer = document.getElementById('main-content');

    const routes = {
      // M2: Home & Ask
      '/home': () => renderHomeView(mainContainer),
      '/ask': () => renderAskView(mainContainer),

      // M1: Login & Users
      '/login': () => renderLoginView(mainContainer),
      '/profile': () => renderProfileView(mainContainer),
      '/admin/users': () => renderUsersView(mainContainer),

      // M3: Documents
      '/documents': () => renderDocumentsView(mainContainer),
      '/documents/queue': () => renderVerificationQueueView(mainContainer),
      '/documents/duplicates': () => renderDuplicatesView(mainContainer),
      '/documents/:id': (params) => this.openDocViewer(params.id, 1),

      // M4: Companies
      '/companies': () => renderCompaniesView(mainContainer),
      '/companies/tree': () => renderGroupTreeView(mainContainer),
      '/companies/filings': () => renderFilingTrackerView(mainContainer),
      '/companies/:id': (params) => renderCompanyDetailView(mainContainer, params.id),

      // M5: Loans
      '/loans': () => renderLoansView(mainContainer),
      '/loans/ledger': () => renderExposureLedgerView(mainContainer),
      '/loans/settlements': () => renderSettlementsView(mainContainer),
      '/loans/release': () => renderSecurityReleaseView(mainContainer),
      '/loans/:id': (params) => renderLoanDetailView(mainContainer, params.id),

      // M6: Land
      '/land': () => renderLandView(mainContainer),
      '/land/encumbrances': () => renderEncumbranceRegisterView(mainContainer),
      '/land/:id': (params) => renderParcelDetailView(mainContainer, params.id),

      // M7: Matters
      '/matters': () => renderMattersView(mainContainer),
      '/matters/create': () => renderCreateMatterView(mainContainer),
      '/matters/diary': () => renderHearingDiaryView(mainContainer),
      '/matters/:id': (params) => renderMatterDetailView(mainContainer, params.id),

      // M8: Research
      '/research': () => renderResearchView(mainContainer),
      '/research/saved': () => renderSavedResearchView(mainContainer),

      // M9: Drafting
      '/drafting': () => renderDraftingView(mainContainer),
      '/drafting/editor': () => renderDraftEditorView(mainContainer, null),
      '/drafting/editor/:id': (params) => renderDraftEditorView(mainContainer, params.id),

      // M10: Tax
      '/tax': () => renderTaxView(mainContainer),
      '/tax/:id': (params) => renderTaxDetailView(mainContainer, params.id),

      // M11: Calendar & Tasks
      '/calendar': () => renderCalendarView(mainContainer),
      '/calendar/tasks': () => renderTasksView(mainContainer),
      '/calendar/limitation': () => renderLimitationCalcView(mainContainer),

      // M12: Notifications & Voice
      '/notifications': () => renderNotificationsView(mainContainer),
      '/notifications/messages': () => renderMessageApprovalView(mainContainer),
      '/notifications/calls': () => renderCallLogView(mainContainer),

      // M13: Approvals
      '/approvals': () => renderApprovalsView(mainContainer),
      '/approvals/:id': (params) => renderApprovalReviewView(mainContainer, params.id),

      // M14: Reports
      '/reports': () => renderReportsView(mainContainer),
      '/reports/builder': () => renderReportBuilderView(mainContainer),

      // M15: Knowledge Hub
      '/knowledge': () => renderKnowledgeView(mainContainer),
      '/knowledge/lookups': () => renderOutsideLookupsView(mainContainer),

      // M16: Security & Audit
      '/security': () => renderSecurityView(mainContainer),
      '/security/audit': () => renderAuditLogView(mainContainer),

      // M17: Administration
      '/admin': () => renderAdminView(mainContainer),
      '/admin/agents/:id': (params) => renderAgentDetailView(mainContainer, params.id),
      '/admin/tests': () => renderQualityTestsView(mainContainer),

      // Fallback
      '*': () => renderHomeView(mainContainer)
    };

    this.router = new Router(routes, (route, params, handler) => {
      this.updateActiveNav(window.location.hash);
      if (route === 'blocked') {
        mainContainer.innerHTML = `
          <div style="padding:60px; text-align:center;">
            <div style="font-size:36px; margin-bottom:16px;">🛡️</div>
            <h2>Access Restricted</h2>
            <p style="color:var(--text-muted); margin-top:8px; max-width:480px; margin-left:auto; margin-right:auto;">
              Your current role (<strong>${state.currentRole}</strong>) is not authorized to view this record or module.
            </p>
            <div style="margin-top:24px;">
              <a href="#/home" class="btn btn-primary">Return to Home</a>
            </div>
          </div>
        `;
      } else if (handler) {
        handler(params);
      }
    });

    this.router.init();
  }

  // Section 4 Role-aware sidebar generator with outline SVG icons (no emojis)
  renderSidebar() {
    const nav = document.getElementById('sidebar-nav');
    if (!nav) return;

    const navIcons = {
      home: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>`,
      approvals: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`,
      calendar: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></svg>`,
      notifications: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>`,
      documents: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 8 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>`,
      companies: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="20" x="4" y="2" rx="2" ry="2"/><path d="M9 22v-4h6v4"/><path d="M8 6h.01"/><path d="M16 6h.01"/><path d="M8 10h.01"/><path d="M16 10h.01"/><path d="M8 14h.01"/><path d="M16 14h.01"/></svg>`,
      loans: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>`,
      land: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 3 4 8 5-5 5 15H2L8 3z"/></svg>`,
      matters: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/></svg>`,
      tax: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M14 8H8"/><path d="M16 12H8"/><path d="M13 16H8"/></svg>`,
      ask: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>`,
      research: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" x2="21" y1="16.65" y2="16.65"/></svg>`,
      drafting: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>`,
      knowledge: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>`,
      reports: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/></svg>`,
      security: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
      admin: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`,
      users: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`
    };

    const role = state.currentRole;
    const canSee = (moduleKey) => {
      if (role === 'Administrator' || role === 'admin') return true;
      if (role === 'External counsel') return moduleKey === 'matters' || moduleKey === 'documents';
      if (role === 'Manager / Board member' || role === 'Management' || role === 'management') return ['home', 'reports', 'loans', 'land', 'approvals', 'ask', 'companies'].includes(moduleKey);
      if (role === 'Lawyer' || role === 'Advocate' || role === 'advocate') return ['home', 'matters', 'research', 'drafting', 'documents', 'approvals', 'calendar'].includes(moduleKey);
      if (role === 'Tax team member') return ['home', 'tax', 'drafting', 'documents', 'calendar'].includes(moduleKey);
      if (role === 'Company secretary') return ['home', 'companies', 'documents', 'calendar'].includes(moduleKey);
      if (role === 'Finance team member' || role === 'Auditor' || role === 'auditor') return ['home', 'loans', 'land', 'documents', 'calendar', 'reports', 'security'].includes(moduleKey);
      if (role === 'Staff member' || role === 'Internal Employee' || role === 'employee') return ['home', 'documents', 'calendar', 'notifications', 'matters', 'tax'].includes(moduleKey);
      if (role === 'Client' || role === 'client') return ['home', 'documents', 'matters', 'approvals'].includes(moduleKey);
      if (role === 'Tenant or Buyer' || role === 'tenant') return ['home', 'land', 'documents'].includes(moduleKey);
      return true;
    };

    const groups = [
      {
        name: 'Work',
        items: [
          { key: 'home', label: 'Home', route: '#/home', icon: navIcons.home },
          { key: 'approvals', label: 'Approvals', route: '#/approvals', icon: navIcons.approvals, badge: '6' },
          { key: 'calendar', label: 'Calendar & Tasks', route: '#/calendar', icon: navIcons.calendar },
          { key: 'notifications', label: 'Notifications', route: '#/notifications', icon: navIcons.notifications, badge: '2' }
        ]
      },
      {
        name: 'Records',
        items: [
          { key: 'documents', label: 'Documents', route: '#/documents', icon: navIcons.documents },
          { key: 'companies', label: 'Companies', route: '#/companies', icon: navIcons.companies },
          { key: 'loans', label: 'Loans & Settlements', route: '#/loans', icon: navIcons.loans },
          { key: 'land', label: 'Land & Title', route: '#/land', icon: navIcons.land },
          { key: 'matters', label: 'Cases & Matters', route: '#/matters', icon: navIcons.matters },
          { key: 'tax', label: 'Tax Matters', route: '#/tax', icon: navIcons.tax }
        ]
      },
      {
        name: 'Intelligence',
        items: [
          { key: 'ask', label: 'Ask Intelligence', route: '#/ask', icon: navIcons.ask },
          { key: 'research', label: 'Legal Research', route: '#/research', icon: navIcons.research },
          { key: 'drafting', label: 'Drafting & Templates', route: '#/drafting', icon: navIcons.drafting },
          { key: 'knowledge', label: 'Knowledge Hub', route: '#/knowledge', icon: navIcons.knowledge }
        ]
      },
      {
        name: 'Insights',
        items: [
          { key: 'reports', label: 'Reports & Dashboards', route: '#/reports', icon: navIcons.reports }
        ]
      },
      {
        name: 'System',
        items: [
          { key: 'security', label: 'Security & Audit', route: '#/security', icon: navIcons.security },
          { key: 'admin', label: 'AI Control & Admin', route: '#/admin', icon: navIcons.admin },
          { key: 'users', label: 'User Management', route: '#/admin/users', icon: navIcons.users }
        ]
      }
    ];

    let html = '';
    groups.forEach(g => {
      const visibleItems = g.items.filter(item => canSee(item.key));
      if (visibleItems.length > 0) {
        html += `<div class="nav-group-title">${g.name}</div>`;
        visibleItems.forEach(item => {
          html += `
            <a href="${item.route}" class="nav-item" data-route="${item.route}">
              <span class="nav-item-icon">${item.icon}</span>
              <span class="nav-item-label">${item.label}</span>
              ${item.badge ? `<span class="nav-item-badge">${item.badge}</span>` : ''}
            </a>
          `;
        });
      }
    });

    nav.innerHTML = html;
  }

  updateActiveNav(hash) {
    const links = document.querySelectorAll('.nav-item');
    const currentPath = (hash || window.location.hash || '#/home').replace(/^#\/?/, '').split('/')[0] || 'home';
    links.forEach(l => {
      const href = l.getAttribute('href') || '';
      const linkPath = href.replace(/^#\/?/, '').split('/')[0];
      const isActive = linkPath === currentPath;
      l.classList.toggle('active', isActive);
    });
  }

  setupTopbar() {
    // Theme toggle
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
      themeBtn.addEventListener('click', () => state.toggleTheme());
    }

    // Sidebar collapse toggle
    const sbToggle = document.getElementById('sidebar-toggle-btn');
    const sidebar = document.getElementById('app-sidebar');
    if (sbToggle && sidebar) {
      sbToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
      });
    }

    // Search / Palette trigger
    const searchBtn = document.getElementById('topbar-search-btn');
    if (searchBtn) {
      searchBtn.addEventListener('click', () => this.openCommandPalette());
    }

    // Keyboard Shortcuts (Ctrl+K for palette, Ctrl+\ for sidebar)
    window.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        this.openCommandPalette();
      }
      if ((e.ctrlKey || e.metaKey) && e.key === '\\') {
        e.preventDefault();
        sidebar?.classList.toggle('collapsed');
      }
      if (e.key === 'Escape') {
        this.closeCommandPalette();
        this.drawer.close();
      }
    });

    this.updateUserUI();
  }

  // Setup Profile Menus (Topbar dropdown and Sidebar bottom popover)
  setupProfileMenus() {
    const topbarTrigger = document.getElementById('topbar-profile-trigger');
    const topbarMenu = document.getElementById('topbar-profile-menu');
    const sidebarCard = document.getElementById('sidebar-profile-card');
    const sidebarMenu = document.getElementById('sidebar-profile-menu');

    const toggleMenu = (menu, trigger, otherMenu, otherTrigger) => {
      if (!menu) return;
      const isOpen = menu.classList.contains('open');
      if (otherMenu) {
        otherMenu.classList.remove('open');
        otherMenu.style.display = 'none';
        otherTrigger?.setAttribute('aria-expanded', 'false');
      }
      if (isOpen) {
        menu.classList.remove('open');
        menu.style.display = 'none';
        trigger?.setAttribute('aria-expanded', 'false');
      } else {
        menu.classList.add('open');
        menu.style.display = 'block';
        trigger?.setAttribute('aria-expanded', 'true');
      }
    };

    if (topbarTrigger && topbarMenu) {
      topbarTrigger.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleMenu(topbarMenu, topbarTrigger, sidebarMenu, sidebarCard);
      });
    }

    if (sidebarCard && sidebarMenu) {
      sidebarCard.addEventListener('click', (e) => {
        e.stopPropagation();
        toggleMenu(sidebarMenu, sidebarCard, topbarMenu, topbarTrigger);
      });
    }

    // Close on click outside
    document.addEventListener('click', (e) => {
      if (topbarMenu && topbarMenu.classList.contains('open')) {
        if (!topbarMenu.contains(e.target) && !topbarTrigger?.contains(e.target)) {
          topbarMenu.classList.remove('open');
          topbarMenu.style.display = 'none';
          topbarTrigger?.setAttribute('aria-expanded', 'false');
        }
      }
      if (sidebarMenu && sidebarMenu.classList.contains('open')) {
        if (!sidebarMenu.contains(e.target) && !sidebarCard?.contains(e.target)) {
          sidebarMenu.classList.remove('open');
          sidebarMenu.style.display = 'none';
          sidebarCard?.setAttribute('aria-expanded', 'false');
        }
      }
    });

    // Close on Escape key
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (topbarMenu) {
          topbarMenu.classList.remove('open');
          topbarMenu.style.display = 'none';
          topbarTrigger?.setAttribute('aria-expanded', 'false');
        }
        if (sidebarMenu) {
          sidebarMenu.classList.remove('open');
          sidebarMenu.style.display = 'none';
          sidebarCard?.setAttribute('aria-expanded', 'false');
        }
      }
    });
  }

  updateUserUI() {
    const roleLabel = document.getElementById('sidebar-role-label');
    const avatarBadge = document.getElementById('user-avatar-badge');
    const userNameEl = document.getElementById('sidebar-user-name');
    const userRoleEl = document.getElementById('sidebar-user-role');
    const userAvatarEl = document.getElementById('sidebar-user-avatar');
    const dropdownAvatar = document.getElementById('dropdown-user-avatar');
    const dropdownName = document.getElementById('dropdown-user-name');
    const dropdownRole = document.getElementById('dropdown-user-role');

    const user = state.currentUser || { name: 'Rajesh Sharma', role: 'Administrator', avatar: 'RS' };
    const role = state.currentRole || user.role || 'Administrator';
    const initials = user.avatar || (user.name ? user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() : 'US');

    if (roleLabel) roleLabel.textContent = `Role: ${role}`;
    if (avatarBadge) avatarBadge.textContent = initials;
    if (userAvatarEl) userAvatarEl.textContent = initials;
    if (userNameEl) userNameEl.textContent = user.name || 'User';
    if (userRoleEl) userRoleEl.textContent = role;
    if (dropdownAvatar) dropdownAvatar.textContent = initials;
    if (dropdownName) dropdownName.textContent = user.name || 'User';
    if (dropdownRole) dropdownRole.textContent = role;
  }

  setupLogout() {
    const logoutBtns = document.querySelectorAll(
      '.logout-trigger-btn, #sidebar-logout-btn, #topbar-logout-btn, #sidebar-popup-signout-btn, #topbar-signout-btn'
    );
    const modal = document.getElementById('signout-modal');
    const confirmBtn = document.getElementById('confirm-signout-btn');
    const cancelBtn = document.getElementById('cancel-signout-btn');

    const openModal = (e) => {
      if (e) e.preventDefault();
      // Close open dropdowns
      const topMenu = document.getElementById('topbar-profile-menu');
      if (topMenu) {
        topMenu.classList.remove('open');
        topMenu.style.display = 'none';
      }
      const sideMenu = document.getElementById('sidebar-profile-menu');
      if (sideMenu) {
        sideMenu.classList.remove('open');
        sideMenu.style.display = 'none';
      }

      if (modal) {
        modal.classList.add('active');
      } else if (confirm('Are you sure you want to sign out of Nushift?')) {
        this.performSignout();
      }
    };

    logoutBtns.forEach(btn => {
      btn.addEventListener('click', openModal);
    });

    cancelBtn?.addEventListener('click', () => {
      modal?.classList.remove('active');
    });

    confirmBtn?.addEventListener('click', () => {
      this.performSignout();
    });

    modal?.addEventListener('click', (e) => {
      if (e.target === modal) modal.classList.remove('active');
    });
  }

  performSignout() {
    sessionStorage.removeItem('nushift_role');
    localStorage.removeItem('nushift_token');
    localStorage.removeItem('nushift_user');
    localStorage.removeItem('lfae_token');
    localStorage.removeItem('lfae_user');
    this.showToast('Signed out of Nushift successfully.', 'info');
    setTimeout(() => {
      window.location.href = 'roles.html';
    }, 350);
  }

  // Command Palette
  setupCommandPalette() {
    const backdrop = document.getElementById('command-palette-backdrop');
    const input = document.getElementById('command-palette-input');

    if (backdrop) {
      backdrop.addEventListener('click', (e) => {
        if (e.target === backdrop) this.closeCommandPalette();
      });
    }

    if (input) {
      input.addEventListener('input', (e) => {
        this.renderCommandResults(e.target.value);
      });
    }
  }

  openCommandPalette() {
    const backdrop = document.getElementById('command-palette-backdrop');
    const input = document.getElementById('command-palette-input');
    backdrop?.classList.add('open');
    input?.focus();
    if (input) input.value = '';
    this.renderCommandResults('');
  }

  closeCommandPalette() {
    const backdrop = document.getElementById('command-palette-backdrop');
    backdrop?.classList.remove('open');
  }

  renderCommandResults(q) {
    const list = document.getElementById('command-palette-results');
    if (!list) return;

    const term = (q || '').trim().toLowerCase();

    // Suggested actions & records
    const catalog = [
      {
        title: 'Ask AI Intelligence',
        subtitle: 'Search central enterprise knowledge base',
        route: '#/ask',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>`
      },
      {
        title: 'Facility LN-001 Northern National Bank',
        subtitle: 'Sanction ₹ 85.00 Cr • DRT Recovery',
        route: '#/loans/LN-001',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="20" height="14" x="2" y="5" rx="2"/><line x1="2" x2="22" y1="10" y2="10"/></svg>`
      },
      {
        title: 'Survey No. 112/3 Hinjewadi Parcel (12.5 acres)',
        subtitle: 'Mortgaged to NNB • Pune',
        route: '#/land/P-001',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m8 3 4 8 5-5 5 15H2L8 3z"/></svg>`
      },
      {
        title: 'Matter M-2025-014: NNB vs Meridian Realty',
        subtitle: 'Debts Recovery Tribunal-I, Mumbai',
        route: '#/matters/M-2025-014',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/></svg>`
      },
      {
        title: 'GST Notice FY 2021-22 DRC-01 (Demand ₹ 1.84 Cr)',
        subtitle: 'Due in 9 days • Meridian Realty',
        route: '#/tax/TAX-081',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M14 8H8"/><path d="M16 12H8"/></svg>`
      },
      {
        title: 'OTS Settlement Proposal: Apex Housing Finance',
        subtitle: 'Pending Board Approval • LN-003',
        route: '#/approvals',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>`
      },
      {
        title: 'Exposure Ledger with Reconciliation Audit',
        subtitle: 'Lender-wise sanctioned vs claimed',
        route: '#/loans/ledger',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/></svg>`
      },
      {
        title: 'Security Release Protocol',
        subtitle: 'Upload No-Dues and discharge mortgages',
        route: '#/loans/release',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>`
      },
      {
        title: 'AI Control & 16 Agents Status Graph',
        subtitle: 'Inspect model routes & execution safety',
        route: '#/admin',
        icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>`
      }
    ];

    const filtered = catalog.filter(item => 
      !term || item.title.toLowerCase().includes(term) || item.subtitle.toLowerCase().includes(term)
    );

    list.innerHTML = filtered.map(item => `
      <div class="command-item" onclick="window.MeridianApp.closeCommandPalette(); window.location.hash='${item.route}'">
        <span class="command-item-icon">${item.icon}</span>
        <div style="flex:1;">
          <div style="font-weight:600; font-size:13px;">${item.title}</div>
          <div style="font-size:11px; color:var(--text-tertiary);">${item.subtitle}</div>
        </div>
        <span style="font-size:11px; color:var(--text-tertiary);">Jump ↵</span>
      </div>
    `).join('') || `<div style="padding:24px; text-align:center; color:var(--text-muted); font-size:13px;">No matching records or commands.</div>`;
  }

  // Toasts
  showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    const icon = type === 'success' ? '✓' : type === 'danger' ? '✕' : type === 'warning' ? '⚠' : 'ℹ';
    toast.innerHTML = `
      <div style="font-weight:bold; color:var(--primary);">${icon}</div>
      <div style="flex:1; font-weight:500;">${message}</div>
    `;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 150ms ease';
      setTimeout(() => toast.remove(), 160);
    }, 3500);
  }

  // Unit toggles
  toggleCurrencyMode(mode) {
    setCurrencyMode(mode);
    document.getElementById('btn-unit-cr')?.classList.toggle('active', mode === 'lakhCrore');
    document.getElementById('btn-unit-inr')?.classList.toggle('active', mode === 'full');
    this.router?.handleRoute();
  }

  toggleAreaMode(mode) {
    setAreaMode(mode);
    document.getElementById('btn-area-acres')?.classList.toggle('active', mode === 'acres');
    document.getElementById('btn-area-sqft')?.classList.toggle('active', mode === 'sqft');
    this.router?.handleRoute();
  }

  // Global Quick View Triggers
  openQuickView(type, record) {
    this.drawer.open(type, record);
  }

  openDocViewer(docId, page = 1) {
    this.docViewer.open(docId, page);
  }
}

// Instantiate and start
const app = new MeridianApp();
document.addEventListener('DOMContentLoaded', () => app.start());
