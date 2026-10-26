import { usePortalData } from '../hooks.js'
import { Kpi, Card, ApprovalsQueue, AuditTable, Alert, SensBadge } from '../components/ui.jsx'

function SensDist({ dist }) {
  const entries = Object.entries(dist || {})
  if (entries.length === 0) return <div className="muted">No data.</div>
  const total = entries.reduce((s, [, v]) => s + v, 0) || 1
  const order = ['public', 'internal', 'confidential', 'restricted']
  const sorted = order.filter((k) => dist[k]).map((k) => [k, dist[k]])
  return (
    <div>
      <div style={{ display: 'flex', height: 14, borderRadius: 7, overflow: 'hidden', border: '1px solid var(--line)' }}>
        {sorted.map(([k, v]) => (
          <div key={k} style={{ width: `${(v / total) * 100}%`, background: `var(--${k === 'public' ? 'ok' : k === 'internal' ? 'navy-600' : k === 'confidential' ? 'warn' : 'danger'})` }} title={`${k}: ${v}`} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 10 }}>
        {sorted.map(([k, v]) => (
          <span key={k} className="small" style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <SensBadge s={k} /> {v}
          </span>
        ))}
      </div>
    </div>
  )
}

export default function ManagementPortal() {
  const { data, loading, error } = usePortalData()
  if (loading) return <div className="page-center"><span className="spinner" /></div>
  if (error) return <Alert kind="err">{error}</Alert>

  const kpi = data.kpi || {}
  return (
    <div>
      <div className="grid cols-4">
        <Kpi label="Documents" value={kpi.documents ?? 0} accent />
        <Kpi label="Open cases" value={kpi.open_cases ?? 0} />
        <Kpi label="Pending approvals" value={kpi.pending_approvals ?? 0} />
        <Kpi label="Tax matters" value={kpi.tax_matters ?? 0} />
      </div>
      <div className="grid cols-4 mt-20">
        <Kpi label="Land parcels" value={kpi.land_parcels ?? 0} />
        <Kpi label="Entity profiles" value={kpi.entities ?? 0} />
        <Kpi label="Compliance records" value={data.counts?.compliance ?? 0} />
        <Kpi label="Drafts" value={data.counts?.drafts ?? 0} />
      </div>

      <div className="grid cols-2 mt-20">
        <Card title="Workload by matter" sub="Open case work grouped by matter / client.">
          {data.workload && data.workload.length ? (
            <div className="table-wrap">
              <table className="data">
                <thead><tr><th>Matter</th><th>Client</th><th>Deadline</th><th style={{ textAlign: 'right' }}>Items</th></tr></thead>
                <tbody>
                  {data.workload.map((w) => (
                    <tr key={w.matter}>
                      <td><b>{w.matter}</b></td>
                      <td>{w.client || <span className="muted">—</span>}</td>
                      <td className="muted">{w.deadline || '—'}</td>
                      <td style={{ textAlign: 'right' }}>{w.items}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : <div className="empty">No workload recorded.</div>}
        </Card>

        <Card title="Risk alerts" sub="Latest compliance snapshots.">
          {data.risk_alerts && data.risk_alerts.length ? (
            <div style={{ display: 'grid', gap: 12 }}>
              {data.risk_alerts.map((r, i) => (
                <div key={i} style={{ border: '1px solid var(--line)', borderLeft: '3px solid var(--warn)', borderRadius: 8, padding: '12px 14px' }}>
                  <div style={{ fontWeight: 600 }}>{r.title}</div>
                  <div className="muted small" style={{ marginTop: 4 }}>{r.summary}</div>
                </div>
              ))}
            </div>
          ) : <div className="empty">No risk alerts.</div>}
        </Card>
      </div>

      <div className="grid cols-2 mt-20">
        <Card title="Pending approvals" sub="Approve or reject gated actions.">
          <ApprovalsQueue approvals={data.pending_approvals} />
        </Card>
        <Card title="Sensitivity distribution" sub="How documents are classified across the firm.">
          <SensDist dist={data.sensitivity_distribution} />
        </Card>
      </div>

      <div className="section-title">Recent activity</div>
      <Card>
        <AuditTable entries={data.recent_audit} limit={12} />
      </Card>
    </div>
  )
}