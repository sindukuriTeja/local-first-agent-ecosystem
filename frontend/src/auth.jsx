import { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api, getToken, getUser, setSession, clearSession } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getUser())
  const [checking, setChecking] = useState(!!getToken())

  // Validate the stored token on first load (it may have expired server-side).
  useEffect(() => {
    if (!getToken()) return
    api.me()
      .then((r) => setUser(r.user))
      .catch(() => { clearSession(); setUser(null) })
      .finally(() => setChecking(false))
  }, [])

  const login = useCallback(async (username, password) => {
    const r = await api.login(username, password)
    setSession(r.token, r.user)
    setUser(r.user)
    return r.user
  }, [])

  const logout = useCallback(async () => {
    try { await api.logout() } catch { /* ignore */ }
    clearSession()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, checking, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}