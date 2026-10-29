// Thin fetch wrapper for Nushift backend. Preserves all endpoints and auth logic.
const TOKEN_KEY = 'nushift_token'
const USER_KEY = 'nushift_user'
const LEGACY_TOKEN_KEY = 'lfae_token'
const LEGACY_USER_KEY = 'lfae_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || localStorage.getItem(LEGACY_TOKEN_KEY) || null
}

export function getUser() {
  try {
    const raw = localStorage.getItem(USER_KEY) || localStorage.getItem(LEGACY_USER_KEY)
    return JSON.parse(raw || 'null')
  } catch {
    return null
  }
}

export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
  // sync legacy keys for backwards-compatibility
  localStorage.setItem(LEGACY_TOKEN_KEY, token)
  localStorage.setItem(LEGACY_USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
  localStorage.removeItem(LEGACY_TOKEN_KEY)
  localStorage.removeItem(LEGACY_USER_KEY)
  sessionStorage.removeItem('nushift_role')
}

// Base URL resolution: if frontend is served on a different port (e.g. 8080), route to backend on 8000
const API_BASE = (typeof window !== 'undefined' && window.location.port && window.location.port !== '8000' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'))
  ? (window.__API_BASE__ || 'http://127.0.0.1:8000')
  : ''

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  let payload
  if (isForm) {
    payload = body // FormData browser sets boundary
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const url = (path.startsWith('http') || !API_BASE) ? path : (API_BASE + path)
  const res = await fetch(url, { method, headers, body: payload })
  let data = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = { raw: text }
    }
  }
  if (!res.ok) {
    const detail = data && (data.detail || data.error)
    throw new Error(typeof detail === 'string' ? detail : `HTTP ${res.status}`)
  }
  return data
}

export const api = {
  // auth
  login: (username, password) =>
    request('/api/auth/login', { method: 'POST', body: { username, password } }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  demo: () => request('/api/auth/demo'),

  // portals
  portals: () => request('/api/portals'),
  portal: () => request('/api/portal'),
  runAi: (prompt, state = {}) =>
    request('/api/portal/ai', { method: 'POST', body: { prompt, state } }),
  submitRequest: (subject, message) =>
    request('/api/portal/request', { method: 'POST', body: { subject, message } }),
  upload: (file, sensitivity = 'internal') => {
    const fd = new FormData()
    fd.append('file', file)
    return request(`/api/portal/upload?sensitivity=${encodeURIComponent(sensitivity)}`, {
      method: 'POST',
      body: fd,
      isForm: true,
    })
  },
  approve: (approval_id, decision, note = '') =>
    request('/api/portal/approve', {
      method: 'POST',
      body: { approval_id, decision, note },
    }),

  // real-time collaboration workflow
  wfList: () => request('/api/workflow'),
  wfCreate: (subject, message, matter = null) =>
    request('/api/workflow', { method: 'POST', body: { subject, message, matter } }),
  wfApprove: (body) => request('/api/workflow/approve', { method: 'POST', body }),
  wfReject: (body) => request('/api/workflow/reject', { method: 'POST', body }),
  wfStart: (body) => request('/api/workflow/start', { method: 'POST', body }),
  wfActivity: (body) => request('/api/workflow/activity', { method: 'POST', body }),
  wfAi: (body) => request('/api/workflow/ai', { method: 'POST', body }),
  wfInput: (body) => request('/api/workflow/input', { method: 'POST', body }),
  wfAnswerInput: (body) => request('/api/workflow/input/answer', { method: 'POST', body }),
  wfComplete: (body) => request('/api/workflow/complete', { method: 'POST', body }),

  // admin
  adminUsers: () => request('/api/admin/users'),
  adminCreateUser: (username, password, role, display_name = '') =>
    request('/api/admin/users', {
      method: 'POST',
      body: { username, password, role, display_name },
    }),
  adminEnableUser: (username, enabled) =>
    request('/api/admin/users/enable', {
      method: 'POST',
      body: { username, enabled },
    }),

  // system / health
  health: () => request('/health'),
}
