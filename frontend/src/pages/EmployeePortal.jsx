import { usePortalData } from '../hooks.js'
import { Kpi, Card, DocTable, AiPanel, Empty, Alert } from '../components/ui.jsx'

export default function EmployeePortal() {
  const { data, loading, error } = usePortalData()
  if (loading) return <div className="page-center"><span className="spinner" /></div>
  if (error) return <Alert kind="err">{error}</Alert>

  const c = data.counts || {}
  return (
    <div>
      <div className="grid cols-4">
        <Kpi label="Assigned cases" value={c.cases ?? 0} />
        <Kpi label="Tax matters" value={c.tax ?? 0} />
        <Kpi label="Legal work" value={(data.legal_work?.length ?? 0)} />
        <Kpi label="Drafts" value={c.drafts ?? 0} />
      </div>

      <div className="section-title">AI-assisted tasks</div>
      <AiPanel prompts={data.ai_tasks} />

      <div className="section-title">My assigned cases</div>
      <Card>
        <DocTable docs={data.cases} empty="No cases assigned to you yet." />
      </Card>

      <div className="grid cols-2 mt-20">
        <div>
          <div className="section-title">Tax matters</div>
          <Card>
            <DocTable docs={data.tax_matters} empty="No tax matters." />
          </Card>
        </div>
        <div>
          <div className="section-title">Legal work (statutes &amp; judgments)</div>
          <Card>
            <DocTable docs={data.legal_work} empty="No legal work items." />
          </Card>
        </div>
      </div>

      <div className="section-title">Drafts in my queue</div>
      <Card>
        <DocTable docs={data.drafts} empty="No drafts awaiting you." />
      </Card>

      <div className="section-title">All documents in scope</div>
      <Card>
        <DocTable docs={data.documents} empty="No documents in your scope." />
      </Card>
    </div>
  )
}