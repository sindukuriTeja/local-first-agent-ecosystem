/**
 * Internationalization (i18n) strings dictionary
 * Default language: English (en)
 */
export const translations = {
  en: {
    // Brand & Header
    brandName: "Nushift",
    brandSubtitle: "Law, tax and compliance, shifted into one intelligent workspace.",
    searchPlaceholder: "Ask anything or search records... (Ctrl+K)",
    switchCompany: "Company",
    allCompanies: "All Group Companies",
    dataAsOf: "Data as of",
    notifications: "Notifications",
    switchRole: "Switch role (demo)",
    myProfile: "My Profile",
    logout: "Sign Out",

    // Navigation Groups
    groupWork: "Work",
    groupRecords: "Records",
    groupIntelligence: "Intelligence",
    groupInsights: "Insights",
    groupSystem: "System",

    // Navigation Modules
    navHome: "Home",
    navApprovals: "Approvals",
    navCalendar: "Calendar and Tasks",
    navNotifications: "Notifications",
    navDocuments: "Documents",
    navCompanies: "Companies",
    navLoans: "Loans & Settlements",
    navLand: "Land and Title",
    navMatters: "Cases & Matters",
    navTax: "Tax Management",
    navAsk: "Ask Intelligence",
    navResearch: "Legal Research",
    navDrafting: "Drafting & Templates",
    navKnowledge: "Knowledge Hub",
    navReports: "Reports & Dashboards",
    navSecurity: "Security & Audit",
    navAdmin: "AI Control & Admin",
    navUsers: "User Management",

    // Shared States
    loading: "Loading information...",
    retry: "Retry",
    empty: "No records found.",
    notFound: "Not found",
    requestAccess: "Request access",
    verified: "Verified",
    unreviewed: "Unreviewed",
    corrected: "Corrected",
    rejected: "Rejected",
    calculated: "Calculated",
    scenario: "Scenario",
    draftNeedsApproval: "Draft – Needs Approval",
    approved: "Approved",
    unverifiedCitation: "Unverified citation",
    originalUnchanged: "Original document unchanged (Read-Only)",
    notCertifiedValuation: "Not a certified valuation",
    lawyerReviewPending: "Lawyer review pending",
    aiGenerated: "AI Generated"
  }
};

let currentLang = 'en';

export function t(key, fallback = '') {
  return translations[currentLang]?.[key] || fallback || key;
}

export function setLanguage(lang) {
  if (translations[lang]) {
    currentLang = lang;
  }
}

export function getLanguage() {
  return currentLang;
}
