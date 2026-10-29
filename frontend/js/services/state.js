/**
 * Central State Store & Cross-Module Event Bus
 * Implements Section 4 (Role Visibility), Section 8 (Cross-module behavior wiring)
 */

class AppState {
  constructor() {
    // Resolve active role from URL or session
    const urlParams = new URLSearchParams(window.location.search);
    const roleParam = urlParams.get('role') || sessionStorage.getItem('nushift_role') || localStorage.getItem('nushift_role');
    const roleMap = {
      'admin': 'Administrator',
      'administrator': 'Administrator',
      'management': 'Management',
      'advocate': 'Advocate',
      'counsel': 'Advocate',
      'client': 'Client',
      'tenant': 'Tenant or Buyer',
      'auditor': 'Auditor',
      'employee': 'Internal Employee',
      'staff': 'Internal Employee'
    };
    const resolvedRole = (roleParam && roleMap[roleParam.toLowerCase()]) || roleParam;

    this.currentRole = resolvedRole || localStorage.getItem('meridian_role') || 'Administrator';
    this.selectedCompanyId = localStorage.getItem('meridian_company') || 'ALL';
    this.theme = localStorage.getItem('nushift_theme') || localStorage.getItem('meridian_theme') || 'dark';
    this.currentUser = null;
    this.listeners = new Map();

    // Data caches
    this.companies = [];
    this.lenders = [];
    this.loans = [];
    this.parcels = [];
    this.matters = [];
    this.taxNotices = [];
    this.documents = [];
    this.users = [];
    this.filings = [];
    this.approvals = [];
    this.tasks = [];
    this.notifications = [];
    this.auditLogs = [];
    this.research = [];
    this.templates = [];
    this.knowledge = [];
    this.outsideLookups = [];
    this.agents = [];
    this.reports = [];

    this.initialized = false;
  }

  async init() {
    if (this.initialized) return;

    try {
      const [
        comps, lends, lns, prcls, matts, tax, docs, usrs, fils, apps, tsks, notifs, auds, res, tmpls, kb, outLookups, agts, rpts
      ] = await Promise.all([
        this.fetchMock('companies.json'),
        this.fetchMock('lenders.json'),
        this.fetchMock('loans.json'),
        this.fetchMock('parcels.json'),
        this.fetchMock('matters.json'),
        this.fetchMock('tax_notices.json'),
        this.fetchMock('documents.json'),
        this.fetchMock('users.json'),
        this.fetchMock('filings.json'),
        this.fetchMock('approvals.json'),
        this.fetchMock('calendar_tasks.json'),
        this.fetchMock('notifications.json'),
        this.fetchMock('audit_log.json'),
        this.fetchMock('research.json'),
        this.fetchMock('templates.json'),
        this.fetchMock('knowledge.json'),
        this.fetchMock('outside_lookups.json'),
        this.fetchMock('agents.json'),
        this.fetchMock('reports.json')
      ]);

      this.companies = comps || [];
      this.lenders = lends || [];
      this.loans = lns || [];
      this.parcels = prcls || [];
      this.matters = matts || [];
      this.taxNotices = tax || [];
      this.documents = docs || [];
      this.users = usrs || [];
      this.filings = fils || [];
      this.approvals = apps || [];
      this.tasks = tsks || [];
      this.notifications = notifs || [];
      this.auditLogs = auds || [];
      this.research = res || [];
      this.templates = tmpls || [];
      this.knowledge = kb || [];
      this.outsideLookups = outLookups || [];
      this.agents = agts || [];
      this.reports = rpts || [];

      // Set user for current role
      this.updateCurrentUser();
      this.updateRoleAccent();
      this.initialized = true;
      this.applyTheme(this.theme);
    } catch (e) {
      console.error('Failed to initialize state from mock data:', e);
    }
  }

  async fetchMock(file) {
    // Try relative paths robustly
    const paths = [
      `./mock-data/${file}`,
      `/mock-data/${file}`,
      `../mock-data/${file}`
    ];
    for (const p of paths) {
      try {
        const res = await fetch(p);
        if (res.ok) return await res.json();
      } catch (err) {
        // try next
      }
    }
    return [];
  }

  updateCurrentUser() {
    let savedUser = null;
    try {
      const raw = localStorage.getItem('nushift_user') || localStorage.getItem('lfae_user');
      if (raw) savedUser = JSON.parse(raw);
    } catch {}

    const roleLow = (this.currentRole || '').toLowerCase();
    const matchedUser = this.users.find(u => 
      (u.role && u.role.toLowerCase() === roleLow) ||
      (u.portal && u.portal.toLowerCase() === roleLow) ||
      (roleLow.includes('admin') && u.role === 'Administrator') ||
      (roleLow.includes('manage') && (u.role === 'Management' || u.role === 'Manager / Board member')) ||
      (roleLow.includes('advocate') && (u.role === 'Advocate' || u.role === 'Lawyer')) ||
      (roleLow.includes('counsel') && (u.role === 'Advocate' || u.role === 'External counsel')) ||
      (roleLow.includes('auditor') && (u.role === 'Auditor' || u.role === 'Finance team member')) ||
      (roleLow.includes('client') && u.role === 'Client') ||
      (roleLow.includes('tenant') && u.role === 'Tenant or Buyer') ||
      (roleLow.includes('employee') && (u.role === 'Internal Employee' || u.role === 'Staff member'))
    ) || this.users[0] || {
      id: 'USR-001',
      name: 'Rajesh Sharma',
      role: this.currentRole,
      avatar: 'RS'
    };

    if (savedUser && (savedUser.display_name || savedUser.name)) {
      const displayName = savedUser.display_name || savedUser.name;
      const initials = displayName.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase() || 'US';
      this.currentUser = {
        ...matchedUser,
        name: displayName,
        avatar: initials,
        backendUser: savedUser
      };
    } else {
      this.currentUser = matchedUser;
    }
  }

  setRole(newRole) {
    this.currentRole = newRole;
    localStorage.setItem('meridian_role', newRole);
    localStorage.setItem('nushift_role', newRole);
    sessionStorage.setItem('nushift_role', newRole);
    this.updateCurrentUser();
    this.updateRoleAccent();
    this.emit('role-changed', { role: newRole, user: this.currentUser });
    this.logAudit({
      actor: `${this.currentUser.name} (${this.currentRole})`,
      actorType: 'User',
      action: 'Switched Active Role',
      record: newRole,
      module: 'Security & Access',
      details: `Switched demo role context to ${newRole}.`
    });
  }

  updateRoleAccent() {
    const roleColors = {
      'Internal Employee': '#60A5FA',
      'Staff member': '#60A5FA',
      'employee': '#60A5FA',
      'Management': '#F59E0B',
      'Manager / Board member': '#F59E0B',
      'management': '#F59E0B',
      'Advocate': '#F472B6',
      'Lawyer': '#F472B6',
      'External counsel': '#F472B6',
      'advocate': '#F472B6',
      'Client': '#34D399',
      'client': '#34D399',
      'Tenant or Buyer': '#FB923C',
      'tenant': '#FB923C',
      'Auditor': '#A78BFA',
      'Finance team member': '#A78BFA',
      'auditor': '#A78BFA',
      'Administrator': '#22D3EE',
      'admin': '#22D3EE'
    };
    const color = roleColors[this.currentRole] || '#22D3EE';
    document.documentElement.style.setProperty('--role', color);
    document.documentElement.style.setProperty('--primary', color);
  }

  setSelectedCompany(companyId) {
    this.selectedCompanyId = companyId;
    localStorage.setItem('meridian_company', companyId);
    this.emit('company-changed', { companyId });
  }

  toggleTheme() {
    this.theme = this.theme === 'light' ? 'dark' : 'light';
    localStorage.setItem('meridian_theme', this.theme);
    this.applyTheme(this.theme);
    this.emit('theme-changed', { theme: this.theme });
  }

  applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
  }

  // Event listener subscription
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, []);
    }
    this.listeners.get(event).push(callback);
  }

  emit(event, data) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).forEach(cb => cb(data));
    }
  }

  // Cross-Module Behavior 1: Releasing security on a loan changes linked parcel to Free everywhere
  releaseSecurity(loanId, parcelId, certificateDocName = 'No Dues Certificate') {
    // 1. Update parcel
    const parcel = this.parcels.find(p => p.id === parcelId);
    if (parcel) {
      parcel.status = 'Free';
      parcel.encumbrances = parcel.encumbrances.filter(e => e.party !== 'Northern National Bank' && !e.type.includes('Mortgage'));
      parcel.encumbrances.unshift({
        type: 'Discharged Mortgage',
        party: 'Security Released',
        amount: 0,
        date: '28 Oct 2026',
        status: 'Released upon No Dues Certificate',
        ecReference: 'REL/2026/8912'
      });
      parcel.verificationStatus = 'Verified';
    }

    // 2. Update loan record security status
    const loan = this.loans.find(l => l.id === loanId);
    if (loan) {
      const sec = loan.securities.find(s => s.parcelId === parcelId);
      if (sec) sec.status = 'Released';
      loan.status = 'Security Released';
    }

    // 3. Write to Audit Log
    this.logAudit({
      actor: `${this.currentUser.name} (${this.currentRole})`,
      actorType: 'User',
      action: 'Security Released',
      record: `Parcel ${parcelId} linked to ${loanId}`,
      module: 'Loans and Settlements',
      details: `Security charge discharged. Parcel ${parcelId} marked Free across all registries based on ${certificateDocName}.`
    });

    this.emit('security-released', { loanId, parcelId });
  }

  // Cross-Module Behavior 2: Adding a document to a matter adds a timeline event and updates the fact sheet
  addDocumentToMatter(matterId, documentData) {
    const matter = this.matters.find(m => m.id === matterId);
    if (!matter) return;

    // Add timeline event
    const newTimelineEvent = {
      date: '28 Oct 2026',
      title: `Document Added: ${documentData.name}`,
      evidence: documentData.type || 'Legal Filing',
      docId: documentData.id
    };
    matter.timeline.unshift(newTimelineEvent);

    // Add fact sheet point
    if (documentData.extractedFields && documentData.extractedFields.length > 0) {
      const f = documentData.extractedFields[0];
      matter.facts.push({
        id: `F-${Date.now().toString().slice(-4)}`,
        fact: `${f.name}: ${f.value} (Extracted from ${documentData.name})`,
        source: { docId: documentData.id, docName: documentData.name, page: 1 },
        status: 'Verified'
      });
    }

    this.logAudit({
      actor: `${this.currentUser.name} (${this.currentRole})`,
      actorType: 'User',
      action: 'Document Linked to Matter',
      record: matterId,
      module: 'Cases and Matters',
      details: `Added document ${documentData.id} to matter file. Generated timeline event and updated fact sheet.`
    });

    this.emit('matter-updated', { matterId });
  }

  // Cross-Module Behavior 3: Unacknowledged alert moves through escalation steps (Fast-forward demo)
  fastForwardAlertEscalation(notifId) {
    const notif = this.notifications.find(n => n.id === notifId);
    if (!notif) return;

    if (notif.escalationStage < 5) {
      notif.escalationStage += 1;
      const currentStep = notif.escalationSteps[notif.escalationStage - 1];
      if (currentStep) {
        currentStep.completed = true;
        currentStep.status = 'Triggered (Fast-Forward Simulation)';
      }
      const nextStep = notif.escalationSteps[notif.escalationStage];
      if (nextStep) {
        nextStep.active = true;
      }

      // If voice call stage is reached, ensure it is in Approvals
      if (notif.escalationStage === 4 && notif.voiceCall) {
        const existingApp = this.approvals.find(a => a.type === 'Outgoing messages' && a.title.includes(notif.recordId));
        if (!existingApp) {
          this.approvals.unshift({
            id: `APP-VOICE-${Date.now().toString().slice(-3)}`,
            type: 'Outgoing messages',
            title: `Voice Call Escalation: ${notif.title}`,
            requestedBy: 'Voice Notification Agent',
            requestDate: '28 Oct 2026',
            age: 'Just now',
            priority: 'Urgent',
            status: 'Pending',
            targetRole: 'Administrator',
            summary: notif.voiceCall.text,
            sourceDocId: 'DOC-014',
            sourceDocName: 'Hearing Notice',
            sourcePage: 1,
            aiOutput: notif.voiceCall,
            history: []
          });
        }
      }

      this.logAudit({
        actor: 'Fast-Forward Demo Simulator',
        actorType: 'System Guard',
        action: 'Alert Escalated',
        record: notifId,
        module: 'Notifications and Voice Alerts',
        details: `Simulated escalation to Step ${notif.escalationStage} for alert ${notif.title}.`
      });

      this.emit('notification-escalated', { notifId, stage: notif.escalationStage });
    }
  }

  // Cross-Module Behavior 4: Approvals submission & state advancement
  submitApprovalDecision(approvalId, decision, comment) {
    const item = this.approvals.find(a => a.id === approvalId);
    if (!item) return;

    item.status = decision; // 'Approved' | 'Rejected' | 'Corrected'
    item.history.unshift({
      action: decision,
      user: `${this.currentUser.name} (${this.currentRole})`,
      time: '28 Oct 2026, 02:30 PM',
      comment: comment || 'Decision recorded in compliance with enterprise approval policy.'
    });

    // If settlement approval
    if (item.type === 'Settlements' && decision === 'Approved') {
      const loan = this.loans.find(l => l.borrowerName.includes('Projects') || l.id === 'LN-003');
      if (loan) {
        loan.settlementStage = 'Agreed';
      }
    }

    this.logAudit({
      actor: `${this.currentUser.name} (${this.currentRole})`,
      actorType: 'User',
      action: `Approval Decision: ${decision}`,
      record: approvalId,
      module: 'Approvals and Review',
      details: `${decision} action recorded for ${item.title}. Comment: ${comment || 'No comment'}`
    });

    this.emit('approval-decided', { approvalId, decision });
  }

  logAudit(entry) {
    const newEntry = {
      id: `AUD-${Date.now().toString().slice(-4)}`,
      timestamp: '28 Oct 2026, 02:35 PM',
      actor: entry.actor || this.currentUser.name,
      actorType: entry.actorType || 'User',
      action: entry.action || 'Action Performed',
      record: entry.record || 'General Record',
      module: entry.module || 'System',
      details: entry.details || '',
      sourceUsed: entry.sourceUsed || 'User Session',
      ip: '103.21.144.12',
      immutable: true
    };
    this.auditLogs.unshift(newEntry);
    this.emit('audit-logged', newEntry);
  }
}

export const state = new AppState();
