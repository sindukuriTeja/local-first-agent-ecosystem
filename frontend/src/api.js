// Thin fetch wrapper for the backend. The token is kept in localStorage and
// attached as `Authorization: Bearer <token>` on every authenticated call.

const TOKEN_KEY = 'lfae_token'
const USER_KEY = 'lfae_user'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || null
}
export function getUser() {
  try {
    return JSON.parse(localStorage.getItem(USER_KEY) || 'null')
  } catch {
    return null
  }
}
export function setSession(token, user) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}
export function clearSession() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const headers = {}
  const token = getToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  let payload
  if (isForm) {
    payload = body // FormData — let the browser set the content-type
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }
  const res = await fetch(path, { method, headers, body: payload })
  let data = null
  const text = await res.text()
  if (text) {
    try { data = JSON.parse(text) } catch { data = { raw: text } }
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
    return request(`/api/portal/upload?sensitivity=${encodeURIComponent(sensitivity)}`,
      { method: 'POST', body: fd, isForm: true })
  },
  approve: (approval_id, decision, note = '') =>
    request('/api/portal/approve', {
      method: 'POST',
      body: { approval_id, decision, note },
    }),

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

  // legacy / info
  health: () => request('/health'),
}