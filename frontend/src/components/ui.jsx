import { useState } from 'react'
import { api } from '../api.js'

export function Kpi({ label, value, hint, accent }) {
  return (
    <div className={'kpi' + (accent ? ' accent' : '')}>
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  )
}

export function SensBadge({ s }) {
  if (!s) return null
  return <span className={`badge sens-${s}`}>{s}</span>
}

export function TypeBadge({ t }) {
  if (!t) return null
  return <span className="badge type">{t.replace(/_/g, ' ')}</span>
}

export function StatusBadge({ s }) {
  if (!s) return null
  return <span className={`badge status-${s}`}>{s}</span>
}

export function Empty({ icon = '📭', text = 'Nothing here yet.' }) {
  return (
    <div className="empty">
      <div className="big">{icon}</div>
      <div>{text}</div>
    </div>
  )
}

export function Alert({ kind, children, onDismiss }) {
  if (!children) return null
  return (
    <div className={`alert ${kind}`} style={onDismiss ? { display: 'flex', justifyContent: 'space-between', gap: 12 } : {}}>
      <span>{children}</span>
      {onDismiss && <button className="btn ghost sm" onClick={onDismiss}>✕</button>}
    </div>
  )
}

export function Card({ title, sub, children, actions, pad = true }) {
  return (
    <div className={'card' + (pad ? '' : ' card-pad')}>
      {(title || actions) && (
        <div className={pad ? '' : 'card-head'} style={pad ? { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 14 } : { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div>
            {title && <h3>{title}</h3>}
            {sub && <div className="cardsub">{sub}</div>}
          </div>
          {actions}
        </div>
      )}
      <div className={pad ? '' : 'card-body'}>{children}</div>
    </div>
  )
}

export function DocTable({ docs, columns, empty = 'No records found.' }) {
  if (!docs || docs.length === 0) return <Empty text={empty} />
  const cols = columns || [
    { key: 'title', label: 'Title' },
    { key: 'doc_type', label: 'Type', render: (v) => <TypeBadge t={v} /> },
    { key: 'sensitivity', label: 'Sensitivity', render: (v) => <SensBadge s={v} /> },
    { key: 'matter', label: 'Matter' },
    { key: 'client', label: 'Client' },
    { key: 'updated_at', label: 'Updated', render: (v) => <span className="muted nowrap">{fmtDate(v)}</span> },
  ]
  return (
    <div className="table-wrap">
      <table className="data">
        <thead>
          <tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr>
        </thead>
        <tbody>
          {docs.map((d) => (
            <tr key={d.id}>
              {cols.map((c) => (
                <td key={c.key}>
                  {c.render ? c.render(d[c.key], d) : (d[c.key] ?? <span className="muted">—</span>)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function fmtDate(s) {
  if (!s) return '—'
  const d = new Date(s)
  if (isNaN(d)) return s
  return d.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

// AI-assisted task runner: quick prompts + freeform, shows the governed result.
export function AiPanel({ prompts }) {
  const [prompt, setPrompt] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState(null)
  const [err, setErr] = useState(null)

  async function run(p) {
    if (!p || !p.trim()) return
    setBusy(true); setErr(null); setResult(null)
    try {
      const r = await api.runAi(p.trim())
      setResult(r)
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="AI-assisted tasks" sub="Runs through the governed 16-agent orchestrator (local Ollama).">
      {prompts && prompts.length > 0 && (
        <div className="row" style={{ flexWrap: 'wrap', marginBottom: 12 }}>
          {prompts.map((p) => (
            <button key={p.label} className="btn sm" disabled={busy} onClick={() => { setPrompt(p.prompt); run(p.prompt) }}>
              {p.label}
            </button>
          ))}
        </div>
      )}
      <div className="row">
        <textarea
          placeholder="Ask the platform a task, e.g. 'Summarize my assigned cases and upcoming deadlines.'"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ minHeight: 64 }}
        />
      </div>
      <div className="row end" style={{ marginTop: 4 }}>
        <button className="btn gold" disabled={busy} onClick={() => run(prompt)}>
          {busy ? <span className="spinner" /> : '✨'} Run task
        </button>
      </div>
      {err && <Alert kind="err" onDismiss={() => setErr(null)}>{err}</Alert>}
      {result && (
        <div className="ai-result">
          {result.answer || (result.error ? `⚠️ ${result.error}` : 'No answer returned.')}
          {!result.answer && result.error && /ollama|connection|unavailable/i.test(result.error) && (
            <div className="muted small" style={{ marginTop: 8 }}>
              The local Ollama model is not reachable. Start Ollama and pull the configured model
              (e.g. <code>ollama pull llama3.1:8b</code>) to run AI tasks. Everything else in this
              portal works without it.
            </div>
          )}
          <div className="ai-meta">
            {result.agent_id && <span>agent: <b>{result.agent_id}</b></span>}
            {result.status && <span>status: <b>{result.status}</b></span>}
            {result.approval_id && <span>approval: <b>{result.approval_id}</b></span>}
            {result.latency_ms != null && <span>{result.latency_ms} ms</span>}
            {result.sources && result.sources.length > 0 && <span>{result.sources.length} source(s)</span>}
          </div>
        </div>
      )}
    </Card>
  )
}

// Submit a request (client / tenant).
export function RequestForm({ onDone }) {
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [err, setErr] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (!subject.trim() || !message.trim()) return
    setBusy(true); setErr(null); setMsg(null)
    try {
      const r = await api.submitRequest(subject.trim(), message.trim())
      setMsg(`Request submitted (ref ${r.doc_id}). The firm has been notified.`)
      setSubject(''); setMessage('')
      if (onDone) onDone()
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Submit a request" sub="Send a request to the firm. It is logged and appears in your request history.">
      <form onSubmit={submit}>
        <div className="field">
          <label>Subject</label>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="e.g. Updated status on my matter" />
        </div>
        <div className="field">
          <label>Message</label>
          <textarea value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Describe what you need…" />
        </div>
        {err && <Alert kind="err" onDismiss={() => setErr(null)}>{err}</Alert>}
        {msg && <Alert kind="ok" onDismiss={() => setMsg(null)}>{msg}</Alert>}
        <div className="row end">
          <button className="btn primary" disabled={busy} type="submit">
            {busy ? <span className="spinner" /> : null} Submit request
          </button>
        </div>
      </form>
    </Card>
  )
}

// Document upload (client / tenant).
export function UploadForm({ onDone }) {
  const [file, setFile] = useState(null)
  const [sens, setSens] = useState('internal')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState(null)
  const [err, setErr] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (!file) return
    setBusy(true); setErr(null); setMsg(null)
    try {
      const r = await api.upload(file, sens)
      setMsg(r.status === 'error' ? `Upload processed with a note: ${r.error || 'see agent'}` : `Document "${file.name}" ingested (${r.status}).`)
      setFile(null)
      if (onDone) onDone()
    } catch (e2) {
      setErr(e2.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card title="Upload a document" sub="Documents are run through intake/OCR and classified for sensitivity.">
      <form onSubmit={submit}>
        <div className="field">
          <label>File</label>
          <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        </div>
        <div className="field">
          <label>Declared sensitivity</label>
          <select value={sens} onChange={(e) => setSens(e.target.value)}>
            <option value="public">public</option>
            <option value="internal">internal</option>
            <option value="confidential">confidential</option>
          </select>
        </div>
        {err && <Alert kind="err" onDismiss={() => setErr(null)}>{err}</Alert>}
        {msg && <Alert kind="ok" onDismiss={() => setMsg(null)}>{msg}</Alert>}
        <div className="row end">
          <button className="btn primary" disabled={busy || !file} type="submit">
            {busy ? <span className="spinner" /> : '⬆️'} Upload
          </button>
        </div>
      </form>
    </Card>
  )
}

// Approvals queue (management / admin / counsel).
export function ApprovalsQueue({ approvals, onDecided }) {
  const [busyId, setBusyId] = useState(null)
  const [note, setNote] = useState({})
  const [err, setErr] = useState(null)

  async function decide(id, decision) {
    setBusyId(id); setErr(null)
    try {
      await api.approve(id, decision, note[id] || '')
      if (onDecided) onDecided()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusyId(null)
    }
  }

  if (!approvals || approvals.length === 0) return <Empty icon="✅" text="No pending approvals." />
  return (
    <div>
      {err && <Alert kind="err" onDismiss={() => setErr(null)}>{err}</Alert>}
      <div className="table-wrap">
        <table className="data">
          <thead>
            <tr><th>Approval</th><th>Kind</th><th>Requested by</th><th>When</th><th>Note</th><th style={{ textAlign: 'right' }}>Decision</th></tr>
          </thead>
          <tbody>
            {approvals.map((a) => (
              <tr key={a.id}>
                <td><b>{a.title}</b><div className="muted small">{a.id}</div></td>
                <td><span className="badge type">{a.kind}</span></td>
                <td>{a.requested_by}</td>
                <td className="muted nowrap">{fmtDate(a.requested_at)}</td>
                <td style={{ minWidth: 160 }}>
                  <input placeholder="optional note" value={note[a.id] || ''}
                    onChange={(e) => setNote((n) => ({ ...n, [a.id]: e.target.value }))} />
                </td>
                <td>
                  <div className="row" style={{ justifyContent: 'flex-end' }}>
                    <button className="btn sm" disabled={busyId === a.id} onClick={() => decide(a.id, 'approved')}>
                      {busyId === a.id ? <span className="spinner" /> : '✓ Approve'}
                    </button>
                    <button className="btn sm danger" disabled={busyId === a.id} onClick={() => decide(a.id, 'rejected')}>
                      ✕ Reject
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function AuditTable({ entries, limit = 20 }) {
  const rows = (entries || []).slice(0, limit)
  if (rows.length === 0) return <Empty icon="🧾" text="No audit entries yet." />
  return (
    <div className="table-wrap scrollbox">
      <table className="data">
        <thead>
          <tr><th>Time</th><th>Actor</th><th>Action</th><th>Result</th><th>Detail</th></tr>
        </thead>
        <tbody>
          {rows.map((e, i) => (
            <tr key={i}>
              <td className="audit-time">{fmtDate(e.timestamp || e.ts)}</td>
              <td>{e.actor}</td>
              <td><span className="badge type">{e.action}</span></td>
              <td>{e.result ? <StatusBadge s={e.result} /> : <span className="muted">—</span>}</td>
              <td className="muted small">{e.detail ? JSON.stringify(e.detail) : '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}