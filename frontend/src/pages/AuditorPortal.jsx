import { useState } from 'react'
import { usePortalData } from '../hooks.js'
import { Kpi, Card, Alert, SensBadge, TypeBadge, fmtDate } from '../components/ui.jsx'

export default function AuditorPortal() {
  const { data, loading, error } = usePortalData()
  const [q, setQ] = useState('')
  if (loading) return <div className="page-center"><span className="spinner" /></div>
  if (error) return <Alert kind="err">{error}</Alert>

  const records = (data.compliance_records || []).filter((r) => {
    if (!q.trim()) return true
    const s = q.toLowerCase()
    return (r.title || '').toLowerCase().includes(s) ||
           (r.content || '').toLowerCase().includes(s) ||
           (r.doc_type || '').toLowerCase().includes(s)
  })

  return (
    <div>
      <div className="alert info">{data.note || 'You see only explicitly shared compliance/audit records (controlled access).'}</div>

      <div className="grid cols-3">
        <Kpi label="Compliance records" value={data.compliance_records?.length ?? 0} accent />
        <Kpi label="Audit trail entries" value={data.audit_trail?.length ?? 0} />
        <Kpi label="Matching" value={records.length} />
      </div>

      <div className="section-title">Compliance &amp; audit records</div>
      <Card>
        <div className="row" style={{ marginBottom: 14, maxWidth: 420 }}>
          <input placeholder="Search records by title, content or type…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        {records.length === 0 && <div className="empty">No matching records.</div>}
        <div style={{ display: 'grid', gap: 12 }}>
          {records.map((r) => (
            <details key={r.id} style={{ border: '1px solid var(--line)', borderRadius: 10, padding: '12px 14px' }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                {r.title}
                <span style={{ marginLeft: 'auto', display: 'inline-flex', gap: 6 }}>
                  <TypeBadge t={r.doc_type} />
                  <SensBadge s={r.sensitivity} />
                  <span className="muted small">{fmtDate(r.updated_at)}</span>
                </span>
              </summary>
              <pre style={{ whiteSpace: 'pre-wrap', fontFamily: 'inherit', fontSize: 13, color: 'var(--ink-soft)', marginTop: 10, background: '#f8fafc', padding: 12, borderRadius: 8, border: '1px solid var(--line)' }}>
                {r.content || '(no content)'}
              </pre>
            </details>
          ))}
        </div>
      </Card>

      <div className="section-title">Audit trail</div>
      <Card>
        <AuditTrail entries={data.audit_trail} />
      </Card>
    </div>
  )
}

function AuditTrail({ entries }) {
  const rows = (entries || []).slice(-100).reverse()
  if (rows.length === 0) return <div className="empty">No audit entries.</div>
  return (
    <div className="table-wrap scrollbox">
      <table className="data">
        <thead><tr><th>Time</th><th>Actor</th><th>Action</th><th>User</th><th>Result</th><th>Detail</th></tr></thead>
        <tbody>
          {rows.map((e, i) => (
            <tr key={i}>
              <td className="audit-time">{fmtDate(e.timestamp)}</td>
              <td>{e.actor}</td>
              <td><span className="badge type">{e.action}</span></td>
              <td>{e.user || <span className="muted">—</span>}</td>
              <td>{e.result || <span className="muted">—</span>}</td>
              <td className="muted small">{e.detail && Object.keys(e.detail).length ? JSON.stringify(e.detail) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}