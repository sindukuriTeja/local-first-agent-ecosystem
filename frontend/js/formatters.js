/**
 * Formatters for Indian enterprise standards
 * - Currency (INR format ₹ 12,34,56,789 & Lakh/Crore toggle)
 * - Area (Acres & Sq Ft toggle)
 * - Dates (DD MMM YYYY)
 * - AsOfStamp
 */

// Global display preferences
let currencyMode = 'lakhCrore'; // 'lakhCrore' | 'full'
let areaMode = 'acres';          // 'acres' | 'sqft'

export function setCurrencyMode(mode) {
  currencyMode = mode;
  window.dispatchEvent(new CustomEvent('unit-preference-changed', { detail: { type: 'currency', mode } }));
}

export function getCurrencyMode() {
  return currencyMode;
}

export function setAreaMode(mode) {
  areaMode = mode;
  window.dispatchEvent(new CustomEvent('unit-preference-changed', { detail: { type: 'area', mode } }));
}

export function getAreaMode() {
  return areaMode;
}

/**
 * Format an amount in INR with Indian numbering system and Lakh/Crore support
 * @param {number} amount 
 * @param {boolean} [forceFull=false]
 * @returns {string}
 */
export function formatINR(amount, forceFull = false) {
  if (amount === undefined || amount === null || isNaN(amount)) return '₹ 0';
  const num = Number(amount);
  const sign = num < 0 ? '-' : '';
  const abs = Math.abs(num);

  if (currencyMode === 'lakhCrore' && !forceFull) {
    if (abs >= 10000000) {
      return `${sign}₹ ${(abs / 10000000).toFixed(2)} Cr`;
    } else if (abs >= 100000) {
      return `${sign}₹ ${(abs / 100000).toFixed(2)} Lakhs`;
    }
  }

  // Standard Indian comma separator format: 12,34,56,789
  const formatted = abs.toLocaleString('en-IN', {
    maximumFractionDigits: 0
  });
  return `${sign}₹ ${formatted}`;
}

/**
 * Format land area with toggle between Acres and Sq Ft
 * 1 Acre = 43,560 sq ft
 * @param {number} acres
 * @returns {string}
 */
export function formatArea(acres) {
  if (acres === undefined || acres === null || isNaN(acres)) return '0 acres';
  const a = Number(acres);
  if (areaMode === 'sqft') {
    const sqft = Math.round(a * 43560);
    return `${sqft.toLocaleString('en-IN')} sq ft`;
  }
  return `${a.toFixed(2)} acres`;
}

/**
 * Format date string to DD MMM YYYY
 * @param {string|Date} dateInput
 * @returns {string}
 */
export function formatDate(dateInput) {
  if (!dateInput) return '—';
  if (window.dayjs) {
    const d = window.dayjs(dateInput);
    if (d.isValid()) return d.format('DD MMM YYYY');
  }
  // Fallback if dayjs not ready
  try {
    const d = new Date(dateInput);
    if (!isNaN(d.getTime())) {
      const day = String(d.getDate()).padStart(2, '0');
      const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
      return `${day} ${months[d.getMonth()]} ${d.getFullYear()}`;
    }
  } catch (e) {
    // Ignore
  }
  return String(dateInput);
}

/**
 * Renders an AsOfStamp string
 * @param {string} [dateStr="28 Oct 2026"]
 * @returns {string}
 */
export function asOfStamp(dateStr = '28 Oct 2026') {
  return `<span class="as-of-stamp" title="All metrics verified against authoritative sources as of this timestamp">
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
    Data as of ${dateStr}
  </span>`;
}
