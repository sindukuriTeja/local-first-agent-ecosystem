import { useEffect, useState } from 'react'
import { usePortalData } from '../hooks.js'
import { api } from '../api.js'
import { Kpi, Card, Alert, ApprovalsQueue, AuditTable, fmtDate } from '../components/ui.jsx'

const ROLES = ['employee', 'manager', 'counsel', 'client', 'tenant', 'auditor', 'admin']

function UsersManager({ onDone }) {
  const [users, setUsers] = useState([])
  const [err, setErr] = useState(null)
  const [ok, setOk] = useState(null)
  const [form, setForm] = useState({ username: '', password: '', role: 'employee', display_name: '' })
  const [busy, setBusy] = useState(false)

  async function load() {
    try {
      const r = await api.adminUsers()
      setUsers(r.users)
    } catch (e) { setErr(e.message) }
  }
  // load on mount
  useEffect(() => { load() }, [])

  async function toggle(u) {
    try {
      await api.adminEnableUser(u.username, !u.enabled)
      setOk(`User "${u.username}" ${u.enabled ? 'disabled' : 'enabled'}.`)
      await load()
    } catch (e) { setErr(e.message) }
  }

  async function create(e) {
    e.preventDefault()
    if (!form.username || !form.password) return
    setBusy(true); setErr(null); setOk(null)
    try {
      await api.adminCreateUser(form.username, form.password, form.role, form.display_name)
      setOk(`User "${form.username}" created.`)
      setForm({ username: '', password: '', role: 'employee', display_name: '' })
      await load()
    } catch (e2) { setErr(e2.message) }
    finally { setBusy(false) }
  }

  return (
    <div>
      {err && <Alert kind="err" onDismiss={() => setErr(null)}>{err}</Alert>}
      {ok && <Alert kind="ok" onDismiss={() => setOk(null)}>{ok}</Alert>}
      <div className="table-wrap">
        <table className="data">
          <thead><tr><th>User</th><th>Role</th><th>Portal</th><th>Sensitivity</th><th>Status</th><th style={{ textAlign: 'right' }}>Action</th></tr></thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.username}>
                <td><b>{u.username}</b><div className="muted small">{u.display_name}</div></td>
                <td><span className="badge type">{u.role}</span></td>
                <td>{u.portal}</td>
                <td><span className={`badge sens-${u.max_sensitivity}`}>{u.max_sensitivity}</span></td>
                <td><span className={`badge ${u.enabled ? 'on' : 'off'}`}>{u.enabled ? 'enabled' : 'disabled'}</span></td>
                <td style={{ textAlign: 'right' }}>
                  <button className="btn sm" onClick={() => toggle(u)}>{u.enabled ? 'Disable' : 'Enable'}</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form onSubmit={create} style={{ marginTop: 18, borderTop: '1px solid var(--line)', paddingTop: 16 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Create a new user</div>
        <div className="grid cols-4">
          <div className="field"><label>Username</label><input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></div>
          <div className="field"><label>Password</label><input value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
          <div className="field"><label>Role</label>
            <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div className="field"><label>Display name</label><input value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></div>
        </div>
        <div className="row end"><button className="btn primary" disabled={busy}>{busy ? <span className="spinner" /> : null} Create user</button></div>
      </form>
    </div>
  )
}

export default function AdminPortal() {
  const { data, loading, error, reload } = usePortalData()
  if (loading) return <div className="page-center"><span className="spinner" /></div>
  if (error) return <Alert kind="err">{error}</Alert>

  const kpi = data.kpi || {}
  const learning = data.learning
  return (
    <div>
      <div className="grid cols-4">
        <Kpi label="Documents" value={kpi.documents ?? 0} />
        <Kpi label="Agents" value={kpi.agents ?? 0} />
        <Kpi label="Pending approvals" value={kpi.pending_approvals ?? 0} />
        <Kpi label="Users" value={kpi.users ?? 0} accent />
      </div>

      <div className="section-title">User management</div>
      <Card>
        <UsersManager onDone={reload} />
      </Card>

      <div className="grid cols-2 mt-20">
        <Card title="AI agents" sub="The 16-agent orchestrator and their enabled state.">
          <div className="table-wrap scrollbox">
            <table className="data">
              <thead><tr><th>Agent</th><th style={{ textAlign: 'right' }}>State</th></tr></thead>
              <tbody>
                {(data.agents || []).map((a) => (
                  <tr key={a.id}>
                    <td><b>{a.name}</b><div className="muted small">{a.id}</div></td>
                    <td style={{ textAlign: 'right' }}><span className={`badge ${a.enabled ? 'on' : 'off'}`}>{a.enabled ? 'enabled' : 'disabled'}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card title="Pending approvals" sub="Approve or reject gated actions.">
          <ApprovalsQueue approvals={data.pending_approvals} onDecided={reload} />
        </Card>
      </div>

      <div className="section-title">Self-learning engine</div>
      <Card>
        {learning && learning.error ? (
          <div className="muted">{learning.error}</div>
        ) : learning ? (
          <div className="grid cols-4">
            <Kpi label="Learning runs" value={learning.total_runs ?? 0} />
            <Kpi label="Promoted insights" value={learning.total_promoted ?? 0} accent />
            <Kpi label="Hold-out accuracy" value={learning.holdout_accuracy != null ? `${(learning.holdout_accuracy * 100).toFixed(0)}%` : '—'} />
            <Kpi label="Budget / run" value={learning.budget_per_run ?? '—'} />
          </div>
        ) : <div className="muted">Learning engine not wired.</div>}
      </Card>

      <div className="section-title">Audit trail</div>
      <Card>
        <AuditTable entries={data.recent_audit} limit={30} />
      </Card>
    </div>
  )
}