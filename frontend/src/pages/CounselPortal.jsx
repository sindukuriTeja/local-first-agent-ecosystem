import { usePortalData } from '../hooks.js'
import { Kpi, Card, DocTable, AiPanel, Alert } from '../components/ui.jsx'

export default function CounselPortal() {
  const { data, loading, error } = usePortalData()
  if (loading) return <div className="page-center"><span className="spinner" /></div>
  if (error) return <Alert kind="err">{error}</Alert>

  const c = data.counts || {}
  return (
    <div>
      <div className="grid cols-3">
        <Kpi label="Assigned cases" value={c.cases ?? 0} accent />
        <Kpi label="Drafts to review" value={c.drafts ?? 0} />
        <Kpi label="Research items" value={data.research?.length ?? 0} />
      </div>

      <div className="section-title">AI-assisted tasks</div>
      <AiPanel prompts={data.ai_tasks} />

      <div className="section-title">My assigned cases</div>
      <Card>
        <DocTable docs={data.cases} empty="No cases assigned to you." />
      </Card>

      <div className="grid cols-2 mt-20">
        <div>
          <div className="section-title">Drafts awaiting your review</div>
          <Card>
            <DocTable docs={data.drafts_to_review} empty="No drafts to review." />
          </Card>
        </div>
        <div>
          <div className="section-title">Legal research</div>
          <Card>
            <DocTable docs={data.research} empty="No research items." />
          </Card>
        </div>
      </div>

      <div className="section-title">All documents in scope</div>
      <Card>
        <DocTable docs={data.documents} empty="No documents in your scope." />
      </Card>
    </div>
  )
}