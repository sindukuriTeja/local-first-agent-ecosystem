import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'
import { api } from '../api.js'

const PORTAL_ICONS = {
  employee: '🧑‍💼', management: '📊', counsel: '⚖️', client: '🏢',
  tenant: '🏠', auditor: '🔎', admin: '🛡️',
}

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [logins, setLogins] = useState([])
  const [sel, setSel] = useState(null)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  useEffect(() => {
    api.demo().then((r) => {
      setLogins(r.logins)
      if (r.logins.length) {
        const first = r.logins[0]
        setSel(first.portal)
        setUsername(first.username)
        setPassword(first.password)
      }
    }).catch(() => { /* offline demo still works */ })
  }, [])

  function pick(l) {
    setSel(l.portal)
    setUsername(l.username)
    setPassword(l.password)
  }

  async function submit(e) {
    e.preventDefault()
    if (!username || !password) return
    setBusy(true); setErr(null)
    try {
      const user = await login(username, password)
      navigate(`/portal/${user.portal}`, { replace: true })
    } catch (e2) {
      setErr(e2.message || 'Login failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-hero">
        <div>
          <div className="mark">Local-First Agent Ecosystem</div>
          <h2>One governed platform. Seven role-based portals.</h2>
          <p>A 16-agent legal &amp; compliance platform running on local Ollama inference, with a sensitivity ladder, approval gates and a full audit trail.</p>
          <div className="feats">
            <div><span className="dot">◆</span> Role-scoped access — you only see what your role may see</div>
            <div><span className="dot">◆</span> Approval gates for drafts, external sharing and voice</div>
            <div><span className="dot">◆</span> Append-only audit trail on every action</div>
            <div><span className="dot">◆</span> Local inference — your data stays on your machine</div>
          </div>
        </div>
        <div className="foot">Demo build · demo credentials only · not for production use</div>
      </div>

      <div className="login-body">
        <div className="login-card">
          <div className="head">
            <h1>Sign in to your portal</h1>
            <p>Pick a demo role to autofill, or enter credentials directly.</p>
          </div>

          <div className="portal-grid">
            {logins.map((l) => (
              <button
                key={l.portal}
                className={'portal-tile' + (sel === l.portal ? ' sel' : '')}
                onClick={() => pick(l)}
                type="button"
              >
                <div className="pt-name"><span>{PORTAL_ICONS[l.portal] || '📁'}</span>{l.name}</div>
                <div className="pt-cred">{l.username} · {l.password}</div>
              </button>
            ))}
          </div>

          <form className="login-form" onSubmit={submit}>
            <div className="creds-hint">
              Demo login — e.g. <code>employee1 / employee123</code>. Click a role above to autofill.
            </div>
            <div className="field">
              <label>Username</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
            </div>
            <div className="field">
              <label>Password</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
            </div>
            {err && <div className="alert err">{err}</div>}
            <button className="btn primary" style={{ width: '100%', justifyContent: 'center', padding: '11px' }} disabled={busy} type="submit">
              {busy ? <span className="spinner" /> : null} Sign in
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}