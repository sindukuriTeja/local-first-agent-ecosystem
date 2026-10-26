import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

const PORTAL_META = {
  employee: { title: 'Internal Employee', icon: '🧑‍💼', tagline: 'Assigned cases, documents, tax, legal work and AI tasks.' },
  management: { title: 'Management / Executive', icon: '📊', tagline: 'Firm-wide operations, analytics, risk and workload.' },
  counsel: { title: 'Advocate / External Counsel', icon: '⚖️', tagline: 'Assigned cases, research, draft review and collaboration.' },
  client: { title: 'Client', icon: '🏢', tagline: 'Submit requests, upload documents, track cases and reports.' },
  tenant: { title: 'Tenant / Buyer / Vendor', icon: '🏠', tagline: 'Property & project info, requests and updates.' },
  auditor: { title: 'Regulator / Auditor', icon: '🔎', tagline: 'Explicitly shared compliance & audit records.' },
  admin: { title: 'Admin / System Administrator', icon: '🛡️', tagline: 'Platform overview, users, AI ops, governance and audit.' },
}

function initials(name) {
  if (!name) return '?'
  const parts = name.replace(/\(.*\)/, '').trim().split(/\s+/)
  return ((parts[0]?.[0] || '') + (parts[1]?.[0] || '')).toUpperCase() || '?'
}

export default function Shell({ children }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const meta = PORTAL_META[user?.portal] || { title: 'Portal', icon: '📁', tagline: '' }

  async function doLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="mark">Local-First Agent</div>
          <div className="name">Legal &amp; Compliance Ecosystem</div>
          <div className="sub">16-agent platform · local Ollama</div>
        </div>
        <nav className="nav">
          <div className="navlabel">Your workspace</div>
          <a className="active" href="#" onClick={(e) => { e.preventDefault(); navigate(`/portal/${user.portal}`) }}>
            <span className="ico">{meta.icon}</span>
            <span>{meta.title}</span>
          </a>
        </nav>
        <div className="sidebar-foot">
          <div className="userchip">
            <div className="avatar">{initials(user.display_name)}</div>
            <div className="who">
              <div className="nm">{user.display_name}</div>
              <div className="rl">{user.role} · {user.portal}</div>
            </div>
          </div>
          <button className="logout-btn" onClick={doLogout}>Sign out</button>
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div>
            <h1>{meta.icon} {meta.title}</h1>
            <div className="tagline">{meta.tagline}</div>
          </div>
          <div className="muted small">Signed in as <b>{user.username}</b></div>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}