/**
 * API Service Layer Base
 * Simulates async REST API calls with 300ms to 450ms network latency
 * Handles error simulations, loading states, and state delegation.
 */
import { state } from './state.js';

export function delay(ms = 350) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// Ensure state is loaded before any service executes
async function ensureReady() {
  if (!state.initialized) {
    await state.init();
  }
}

// Deep clone to prevent direct screen mutation of raw mock state
export function clone(data) {
  return JSON.parse(JSON.stringify(data));
}

export const api = {
  // Companies
  async getCompanies() {
    await ensureReady();
    await delay();
    return clone(state.companies);
  },
  async getCompanyById(id) {
    await ensureReady();
    await delay();
    const c = state.companies.find(x => x.id === id);
    if (!c) throw new Error(`Company ${id} not found`);
    return clone(c);
  },

  // Lenders
  async getLenders() {
    await ensureReady();
    await delay();
    return clone(state.lenders);
  },

  // Loans
  async getLoans() {
    await ensureReady();
    await delay();
    return clone(state.loans);
  },
  async getLoanById(id) {
    await ensureReady();
    await delay();
    const l = state.loans.find(x => x.id === id);
    if (!l) throw new Error(`Loan facility ${id} not found`);
    return clone(l);
  },
  async releaseSecurity(loanId, parcelId, docName) {
    await ensureReady();
    await delay(450);
    state.releaseSecurity(loanId, parcelId, docName);
    return { success: true, message: `Security charge over ${parcelId} released.` };
  },

  // Parcels
  async getParcels() {
    await ensureReady();
    await delay();
    return clone(state.parcels);
  },
  async getParcelById(id) {
    await ensureReady();
    await delay();
    const p = state.parcels.find(x => x.id === id);
    if (!p) throw new Error(`Parcel ${id} not found`);
    return clone(p);
  },
  async verifyParcel(id) {
    await ensureReady();
    await delay(300);
    const p = state.parcels.find(x => x.id === id);
    if (p) {
      p.verificationStatus = 'Verified';
      state.logAudit({
        actor: `${state.currentUser.name} (${state.currentRole})`,
        action: 'Parcel Title Verified',
        record: id,
        module: 'Land and Title',
        details: 'Verified revenue extract and title chain.'
      });
    }
    return { success: true };
  },

  // Matters
  async getMatters() {
    await ensureReady();
    await delay();
    return clone(state.matters);
  },
  async getMatterById(id) {
    await ensureReady();
    await delay();
    const m = state.matters.find(x => x.id === id);
    if (!m) throw new Error(`Matter ${id} not found`);
    return clone(m);
  },
  async addDocumentToMatter(matterId, docData) {
    await ensureReady();
    await delay(400);
    state.addDocumentToMatter(matterId, docData);
    return { success: true };
  },
  async approveLegalAnalysis(matterId) {
    await ensureReady();
    await delay(300);
    const m = state.matters.find(x => x.id === id);
    if (m) {
      m.reviewStatus = 'Approved by Lawyer';
    }
    return { success: true };
  },

  // Documents
  async getDocuments() {
    await ensureReady();
    await delay();
    return clone(state.documents);
  },
  async getDocumentById(id) {
    await ensureReady();
    await delay();
    const d = state.documents.find(x => x.id === id);
    if (!d) throw new Error(`Document ${id} not found`);
    return clone(d);
  },
  async uploadDocument(doc) {
    await ensureReady();
    await delay(500);
    const newDoc = {
      id: `DOC-NEW-${Date.now().toString().slice(-3)}`,
      name: doc.name || 'Uploaded_Document.pdf',
      type: doc.type || 'General Record',
      companyId: doc.companyId || 'COMP-001',
      companyName: 'Meridian Infra Holdings Ltd',
      confidentiality: doc.confidentiality || 'Internal',
      status: 'Unreviewed',
      confidence: 94,
      uploadedBy: state.currentUser.name,
      uploadDate: '28 Oct 2026',
      fileSize: '2.4 MB',
      pageCount: 6,
      extractedFields: [
        { id: 'F-NEW-1', name: 'Document Title', value: doc.name, confidence: 96, status: 'Unreviewed', critical: false }
      ]
    };
    state.documents.unshift(newDoc);
    state.logAudit({
      actor: state.currentUser.name,
      action: 'Document Uploaded',
      record: newDoc.id,
      module: 'Document Management',
      details: `Uploaded ${newDoc.name} with ${newDoc.confidentiality} confidentiality.`
    });
    return clone(newDoc);
  },
  async verifyField(docId, fieldId, newStatus, correctedValue) {
    await ensureReady();
    await delay(250);
    const doc = state.documents.find(d => d.id === docId);
    if (doc) {
      const field = doc.extractedFields?.find(f => f.id === fieldId);
      if (field) {
        field.status = newStatus;
        if (correctedValue !== undefined) field.value = correctedValue;
      }
    }
    return { success: true };
  },

  // Tax
  async getTaxNotices() {
    await ensureReady();
    await delay();
    return clone(state.taxNotices);
  },
  async getTaxNoticeById(id) {
    await ensureReady();
    await delay();
    const t = state.taxNotices.find(x => x.id === id);
    if (!t) throw new Error(`Tax notice ${id} not found`);
    return clone(t);
  },

  // Filings
  async getFilings() {
    await ensureReady();
    await delay();
    return clone(state.filings);
  },
  async markFilingCompleted(id, filingData) {
    await ensureReady();
    await delay(400);
    const f = state.filings.find(x => x.id === id);
    if (f) {
      f.status = 'Filed';
      f.srn = filingData.srn || 'SRN-2026-9921';
      f.acknowledgementNumber = filingData.ack || 'ACK-MCA-2026';
      f.filedDate = '28 Oct 2026';
      f.paymentStatus = 'Paid';
    }
    return { success: true };
  },

  // Approvals
  async getApprovals() {
    await ensureReady();
    await delay();
    return clone(state.approvals);
  },
  async submitApprovalDecision(id, decision, comment) {
    await ensureReady();
    await delay(350);
    state.submitApprovalDecision(id, decision, comment);
    return { success: true };
  },

  // Calendar & Tasks
  async getCalendarTasks() {
    await ensureReady();
    await delay();
    return clone(state.tasks);
  },
  async acknowledgeTask(id) {
    await ensureReady();
    await delay(250);
    const t = state.tasks.find(x => x.id === id);
    if (t) t.acknowledged = true;
    return { success: true };
  },

  // Notifications
  async getNotifications() {
    await ensureReady();
    await delay();
    return clone(state.notifications);
  },
  async acknowledgeNotification(id) {
    await ensureReady();
    await delay(250);
    const n = state.notifications.find(x => x.id === id);
    if (n) {
      n.acknowledged = true;
      n.status = 'Acknowledged';
    }
    return { success: true };
  },
  async fastForwardNotification(id) {
    await ensureReady();
    await delay(300);
    state.fastForwardAlertEscalation(id);
    return { success: true };
  },

  // Research
  async getResearchItems() {
    await ensureReady();
    await delay();
    return clone(state.research);
  },

  // Templates
  async getTemplates() {
    await ensureReady();
    await delay();
    return clone(state.templates);
  },

  // Knowledge Hub
  async getKnowledgeFacts() {
    await ensureReady();
    await delay();
    return clone(state.knowledge);
  },
  async getOutsideLookups() {
    await ensureReady();
    await delay();
    return clone(state.outsideLookups);
  },

  // Audit Log
  async getAuditLogs() {
    await ensureReady();
    await delay();
    return clone(state.auditLogs);
  },

  // Users
  async getUsers() {
    await ensureReady();
    await delay();
    return clone(state.users);
  },

  // AI Agents
  async getAgents() {
    await ensureReady();
    await delay();
    return clone(state.agents);
  },

  // Reports
  async getReports() {
    await ensureReady();
    await delay();
    return clone(state.reports);
  }
};
