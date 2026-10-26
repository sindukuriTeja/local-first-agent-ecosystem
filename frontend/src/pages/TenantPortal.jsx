import { usePortalData } from '../hooks.js'
import { Kpi, Card, DocTable, RequestForm, UploadForm, Alert, fmtDate } from '../components/ui.jsx'

export default function TenantPortal() {
  const { data, loading, error, reload } = usePortalData()
  if (loading) return <div className="page-center"><span className="spinner" /></div>
  if (error) return <Alert kind="err">{error}</Alert>

  const c = data.counts || {}
  return (
    <div>
      <div className="grid cols-3">
        <Kpi label="Parcels / projects" value={c.land ?? 0} accent />
        <Kpi label="My requests" value={c.requests ?? 0} />
        <Kpi label="Updates" value={data.updates?.length ?? 0} />
      </div>

      <div className="grid cols-2 mt-20">
        <RequestForm onDone={reload} />
        <UploadForm onDone={reload} />
      </div>

      <div className="section-title">My parcels &amp; projects</div>
      <Card>
        <DocTable
          docs={data.parcels}
          columns={[
            { key: 'title', label: 'Parcel / project' },
            { key: 'parcel', label: 'Parcel ID' },
            { key: 'doc_type', label: 'Type', render: (v) => <span className="badge type">{v?.replace(/_/g, ' ')}</span> },
            { key: 'sensitivity', label: 'Sensitivity', render: (v) => <span className={`badge sens-${v}`}>{v}</span> },
            { key: 'updated_at', label: 'Updated', render: (v) => <span className="muted nowrap">{fmtDate(v)}</span> },
          ]}
          empty="No parcels or projects are linked to you yet."
        />
      </Card>

      <div className="grid cols-2 mt-20">
        <div>
          <div className="section-title">Latest updates</div>
          <Card>
            <DocTable docs={data.updates} empty="No updates yet." />
          </Card>
        </div>
        <div>
          <div className="section-title">My request history</div>
          <Card>
            {data.my_requests && data.my_requests.length ? (
              <div className="table-wrap">
                <table className="data">
                  <thead><tr><th>Subject</th><th>Submitted</th><th>Ref</th></tr></thead>
                  <tbody>
                    {data.my_requests.map((r) => (
                      <tr key={r.id}>
                        <td><b>{r.subject || r.title}</b></td>
                        <td className="muted nowrap">{fmtDate(r.created_at)}</td>
                        <td className="muted small">{r.id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="empty">You haven't submitted any requests yet.</div>}
          </Card>
        </div>
      </div>
    </div>
  )
}