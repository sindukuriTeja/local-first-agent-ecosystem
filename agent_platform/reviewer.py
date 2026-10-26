"""Reviewer web UI — a self-contained dashboard for the human reviewer.

Serves a single-page HTML app at ``/reviewer`` that lets an authorized
reviewer:

  * see the platform **overview** (agents, models, health, learning state)
  * review and **decide approvals** (drafts, external shares, voice)
  * browse **documents** in the knowledge store
  * inspect the **audit log**
  * watch the **self-learning engine** (dashboard + trigger a learn run)

It is backed entirely by the existing REST endpoints, so it is a thin
presentation layer over the same governance surface the API/CLI use.
The page is served locally (127.0.0.1) and requires no build step or
external CDN — everything is inline.

**Access control:** the console is a privileged governance surface (it
exposes full document contents, the audit log, approval decisions, and
learning controls). It therefore requires a valid session token, and the
data routes are restricted to approver roles (admin / manager / reviewer /
counsel). The page itself is open so the login form can render; all data
calls carry the bearer token and are rejected (401/403) otherwise.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel


class LearningReviewRequest(BaseModel):
    candidate_id: str
    decision: str  # approved | rejected | edited
    user: Optional[str] = None

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Reviewer Console — Local-First Agent Ecosystem</title>
<style>
  :root {
    --bg: #0f1420; --panel: #171e2e; --panel2: #1d2637; --line: #2a3550;
    --text: #e6ecf5; --muted: #8b98b4; --accent: #4f8cff; --accent2: #7c5cff;
    --ok: #34c77b; --warn: #f5a623; --bad: #ff5c6c; --chip: #223049;
    --mono: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text);
         font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  header { display: flex; align-items: center; gap: 14px; padding: 16px 22px;
           border-bottom: 1px solid var(--line); background: var(--panel);
           position: sticky; top: 0; z-index: 5; }
  header .logo { width: 34px; height: 34px; border-radius: 9px;
                 background: linear-gradient(135deg, var(--accent), var(--accent2));
                 display: grid; place-items: center; font-weight: 800; color: #fff; }
  header h1 { font-size: 16px; margin: 0; font-weight: 700; }
  header .sub { color: var(--muted); font-size: 12.5px; }
  header .spacer { flex: 1; }
  .pill { font-size: 12px; padding: 4px 10px; border-radius: 999px;
          background: var(--chip); color: var(--muted); border: 1px solid var(--line); }
  .pill.ok { color: var(--ok); border-color: rgba(52,199,123,.4); }
  nav { display: flex; gap: 4px; padding: 10px 22px 0; background: var(--panel);
        border-bottom: 1px solid var(--line); flex-wrap: wrap; }
  nav button { background: none; border: none; color: var(--muted); cursor: pointer;
               font-size: 14px; font-weight: 600; padding: 9px 14px; border-radius: 8px 8px 0 0;
               border-bottom: 2px solid transparent; }
  nav button.active { color: var(--text); border-bottom-color: var(--accent); }
  nav button:hover { color: var(--text); }
  main { padding: 22px; max-width: 1200px; margin: 0 auto; }
  .view { display: none; } .view.active { display: block; }
  .grid { display: grid; gap: 16px; }
  .grid.cols-4 { grid-template-columns: repeat(4, 1fr); }
  .grid.cols-3 { grid-template-columns: repeat(3, 1fr); }
  .grid.cols-2 { grid-template-columns: repeat(2, 1fr); }
  @media (max-width: 900px){ .grid.cols-4{grid-template-columns:repeat(2,1fr);}
    .grid.cols-3{grid-template-columns:1fr;} .grid.cols-2{grid-template-columns:1fr;} }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
          padding: 16px; }
  .stat .label { color: var(--muted); font-size: 12.5px; text-transform: uppercase;
                 letter-spacing: .04em; }
  .stat .value { font-size: 30px; font-weight: 800; margin-top: 4px; }
  .stat .hint { color: var(--muted); font-size: 12.5px; margin-top: 2px; }
  h2 { font-size: 15px; margin: 0 0 12px; color: var(--muted);
       text-transform: uppercase; letter-spacing: .05em; }
  table { width: 100%; border-collapse: collapse; font-size: 13.5px; }
  th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--line);
           vertical-align: top; }
  th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase;
       letter-spacing: .04em; }
  tr:last-child td { border-bottom: none; }
  .tag { display: inline-block; font-size: 11.5px; padding: 2px 8px; border-radius: 6px;
         background: var(--chip); color: var(--text); border: 1px solid var(--line); }
  .tag.ok { color: var(--ok); border-color: rgba(52,199,123,.4); }
  .tag.warn { color: var(--warn); border-color: rgba(245,166,35,.4); }
  .tag.bad { color: var(--bad); border-color: rgba(255,92,108,.4); }
  .tag.info { color: var(--accent); border-color: rgba(79,140,255,.4); }
  .btn { background: var(--accent); color: #fff; border: none; padding: 7px 13px;
         border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 600; }
  .btn:hover { filter: brightness(1.1); }
  .btn.ghost { background: var(--chip); color: var(--text); border: 1px solid var(--line); }
  .btn.ok { background: var(--ok); } .btn.bad { background: var(--bad); }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .row-actions { display: flex; gap: 6px; flex-wrap: wrap; }
  input, select, textarea { background: var(--panel2); color: var(--text);
         border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
         font-size: 13.5px; font-family: inherit; }
  input:focus, select:focus, textarea:focus { outline: none; border-color: var(--accent); }
  .toolbar { display: flex; gap: 10px; align-items: center; margin-bottom: 14px; flex-wrap: wrap; }
  .toolbar input, .toolbar select { min-width: 160px; }
  .toolbar .grow { flex: 1; }
  .empty { color: var(--muted); text-align: center; padding: 40px 10px; font-size: 14px; }
  .mono { font-family: var(--mono); font-size: 12.5px; }
  .muted { color: var(--muted); }
  .kv { display: grid; grid-template-columns: 150px 1fr; gap: 6px 14px; font-size: 13.5px; }
  .kv .k { color: var(--muted); }
  .bar { height: 8px; background: var(--panel2); border-radius: 999px; overflow: hidden; }
  .bar > span { display: block; height: 100%; background: linear-gradient(90deg,var(--accent),var(--accent2)); }
  .toast { position: fixed; bottom: 22px; right: 22px; background: var(--panel2);
           border: 1px solid var(--line); border-left: 3px solid var(--accent);
           padding: 12px 16px; border-radius: 10px; font-size: 13.5px; max-width: 360px;
           box-shadow: 0 8px 30px rgba(0,0,0,.4); opacity: 0; transform: translateY(10px);
           transition: .2s; pointer-events: none; z-index: 20; }
  .toast.show { opacity: 1; transform: translateY(0); }
  .toast.ok { border-left-color: var(--ok); } .toast.bad { border-left-color: var(--bad); }
  .doc-body { white-space: pre-wrap; font-family: var(--mono); font-size: 12.5px;
              color: var(--muted); max-height: 320px; overflow: auto; margin-top: 8px;
              padding: 12px; background: var(--panel2); border-radius: 8px; }
  .detail { margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--line); }
  a { color: var(--accent); text-decoration: none; } a:hover { text-decoration: underline; }
  /* login overlay */
  .login-overlay { position: fixed; inset: 0; background: var(--bg);
                   display: grid; place-items: center; z-index: 100; }
  .login-card { background: var(--panel); border: 1px solid var(--line);
                border-radius: 14px; padding: 28px; width: 340px;
                display: flex; flex-direction: column; gap: 12px; }
  .login-card .logo { width: 40px; height: 40px; border-radius: 10px;
                background: linear-gradient(135deg, var(--accent), var(--accent2));
                display: grid; place-items: center; font-weight: 800; color: #fff; font-size: 18px; }
  .login-card h1 { font-size: 17px; margin: 0; }
  .login-card .sub { color: var(--muted); font-size: 12.5px; margin-bottom: 6px; }
  .login-card input { width: 100%; }
  .login-card .btn { width: 100%; padding: 10px; }
  .demo-hint { color: var(--muted); font-size: 12px; margin-top: 4px; }
  .demo-logins { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
  .demo-btn { background: var(--panel2); border: 1px solid var(--line); color: var(--text);
              border-radius: 8px; padding: 7px 9px; font-size: 12px; cursor: pointer; text-align: left; }
  .demo-btn:hover { border-color: var(--accent); }
  .demo-btn .dname { font-weight: 600; } .demo-btn .dcred { color: var(--muted); font-size: 11px; }
</style>
</head>
<body>
<!-- LOGIN OVERLAY (shown until a valid approver session is established) -->
<div id="login-overlay" class="login-overlay" style="display:none">
  <div class="login-card">
    <div class="logo">L</div>
    <h1>Reviewer Console</h1>
    <div class="sub">Sign in with a reviewer / admin account</div>
    <form id="login-form">
      <input id="login-user" placeholder="username" autocomplete="username" style="margin-bottom:10px" />
      <input id="login-pass" type="password" placeholder="password" autocomplete="current-password" style="margin-bottom:12px" />
      <button class="btn" type="submit">Sign in</button>
    </form>
    <div class="demo-hint">Demo logins (approver roles):</div>
    <div id="demo-logins" class="demo-logins"></div>
  </div>
</div>

<header>
  <div class="logo">L</div>
  <div>
    <h1>Reviewer Console</h1>
    <div class="sub">Local-First Agent Ecosystem · 16-agent legal/compliance platform</div>
  </div>
  <div class="spacer"></div>
  <span class="pill" id="health-pill">…</span>
  <span class="pill" id="model-pill">…</span>
  <span class="pill" id="user-pill" style="display:none"></span>
  <button class="btn ghost" id="logout-btn" style="display:none" onclick="doLogout()">Sign out</button>
</header>
<nav id="nav">
  <button data-view="overview" class="active">Overview</button>
  <button data-view="approvals">Approvals <span id="ap-count"></span></button>
  <button data-view="documents">Documents</button>
  <button data-view="audit">Audit</button>
  <button data-view="learning">Self-Learning</button>
</nav>
<main>
  <!-- OVERVIEW -->
  <section class="view active" id="view-overview">
    <div class="grid cols-4" id="ov-stats"></div>
    <div class="grid cols-2" style="margin-top:16px">
      <div class="card"><h2>Agents</h2><div id="ov-agents"></div></div>
      <div class="card"><h2>Platform</h2><div class="kv" id="ov-platform"></div></div>
    </div>
  </section>

  <!-- APPROVALS -->
  <section class="view" id="view-approvals">
    <div class="card">
      <div class="toolbar">
        <h2 style="margin:0">Pending approvals</h2>
        <div class="grow"></div>
        <button class="btn ghost" onclick="loadApprovals()">Refresh</button>
      </div>
      <div id="ap-list"></div>
    </div>
  </section>

  <!-- DOCUMENTS -->
  <section class="view" id="view-documents">
    <div class="card">
      <div class="toolbar">
        <input id="doc-q" placeholder="Search documents…" onkeydown="if(event.key==='Enter')loadDocs()" />
        <select id="doc-sens">
          <option value="restricted">All sensitivities</option>
          <option value="internal">Up to internal</option>
          <option value="public">Public only</option>
        </select>
        <button class="btn" onclick="loadDocs()">Search</button>
        <div class="grow"></div>
        <button class="btn ghost" onclick="loadDocs()">List recent</button>
      </div>
      <div id="doc-list"></div>
    </div>
  </section>

  <!-- AUDIT -->
  <section class="view" id="view-audit">
    <div class="card">
      <div class="toolbar">
        <input id="au-actor" placeholder="actor (e.g. agent_7_drafting)" />
        <input id="au-action" placeholder="action" />
        <input id="au-user" placeholder="user" />
        <select id="au-limit"><option>50</option><option>100</option><option>200</option></select>
        <button class="btn" onclick="loadAudit()">Query</button>
        <div class="grow"></div>
        <span class="muted" id="au-count"></span>
      </div>
      <div id="au-list"></div>
    </div>
  </section>

  <!-- LEARNING -->
  <section class="view" id="view-learning">
    <div class="grid cols-4" id="learn-stats"></div>
    <div class="card" style="margin-top:16px">
      <div class="toolbar">
        <h2 style="margin:0">Self-learning engine</h2>
        <div class="grow"></div>
        <button class="btn" id="learn-btn" onclick="runLearn()">Run learning pass</button>
      </div>
      <div id="learn-report" class="muted">No run yet in this session.</div>
      <div class="detail">
        <h2>Pending human review</h2>
        <div id="learn-pending"></div>
      </div>
      <div class="detail">
        <h2>Recent promotions</h2>
        <div id="learn-promos"></div>
      </div>
    </div>
  </section>
</main>
<div class="toast" id="toast"></div>

<script>
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const TOKEN_KEY = 'lfae_reviewer_token';
let state = { approvals: [], docs: [], audit: [], me: null };

function getToken() { return localStorage.getItem(TOKEN_KEY); }
function setToken(t) { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); }

function toast(msg, kind) {
  const t = $('#toast'); t.textContent = msg;
  t.className = 'toast show ' + (kind || '');
  clearTimeout(t._t); t._t = setTimeout(() => t.className = 'toast', 3200);
}
function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
function tag(label, cls) { return `<span class="tag ${cls||''}">${esc(label)}</span>`; }
function statusTag(s) {
  const map = { ok:'ok', approved:'ok', success:'ok', promoted:'ok', active:'ok',
    pending:'warn', needs_approval:'warn', rejected:'bad', error:'bad',
    failure:'bad', abstain:'warn', corrected:'info', public:'info',
    internal:'', confidential:'warn', restricted:'bad' };
  return tag(s, map[s] || '');
}

// All data calls carry the bearer token. On 401 we drop the token and
// re-show the login screen; on 403 the user is not an approver.
async function api(path, opts) {
  opts = opts || {};
  const headers = Object.assign({}, opts.headers || {});
  if (getToken()) headers['Authorization'] = 'Bearer ' + getToken();
  const r = await fetch(path, Object.assign({}, opts, { headers }));
  if (r.status === 401) { setToken(null); showLogin(); throw new Error('not authenticated'); }
  if (r.status === 403) { let d=''; try { d=(await r.json()).detail; } catch(e){}
    throw new Error(d || 'forbidden'); }
  if (!r.ok) { let d=''; try { d=(await r.json()).detail || JSON.stringify(await r.json()); } catch(e){ d=r.statusText; }
    throw new Error(d || r.status); }
  return r.json();
}
const post = (path, body) => api(path, { method:'POST',
  headers:{'Content-Type':'application/json'}, body: JSON.stringify(body) });

// ---- auth / login ----
function showLogin() {
  $('#login-overlay').style.display = 'grid';
  $('#logout-btn').style.display = 'none';
  $('#user-pill').style.display = 'none';
  loadDemoLogins();
}
function hideLogin() {
  $('#login-overlay').style.display = 'none';
  if (state.me) {
    $('#user-pill').textContent = state.me.username + ' (' + state.me.role + ')';
    $('#user-pill').style.display = '';
    $('#logout-btn').style.display = '';
  }
}
async function loadDemoLogins() {
  try {
    const r = await fetch('/api/auth/demo');
    const d = await r.json();
    const approver = new Set(['admin','manager','reviewer','counsel']);
    const box = $('#demo-logins'); box.innerHTML = '';
    (d.logins || []).forEach(l => {
      const u = l.username;
      // only offer approver-role demo accounts to the reviewer console
      const roleOf = { admin:'admin', manager1:'manager', reviewer:'reviewer',
                       counsel1:'counsel' }[u];
      if (!approver.has(roleOf)) return;
      const b = document.createElement('button');
      b.className = 'demo-btn'; b.type = 'button';
      b.innerHTML = `<div class="dname">${esc(l.name)}</div>
                     <div class="dcred">${esc(u)} / ${esc(l.password)}</div>`;
      b.onclick = () => { $('#login-user').value = u; $('#login-pass').value = l.password; doLogin(u, l.password); };
      box.appendChild(b);
    });
  } catch(e) { /* demo list is best-effort */ }
}
async function doLogin(username, password) {
  try {
    const r = await fetch('/api/auth/login', { method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ username, password }) });
    if (!r.ok) throw new Error('invalid credentials');
    const d = await r.json();
    setToken(d.token);
    state.me = d.user;
    hideLogin();
    enterConsole();
  } catch(e) { toast('Sign in failed: ' + e.message, 'bad'); }
}
function doLogout() {
  const t = getToken();
  if (t) fetch('/api/auth/logout', { method:'POST',
    headers:{'Authorization':'Bearer ' + t} }).catch(()=>{});
  setToken(null); state.me = null;
  showLogin();
}
async function enterConsole() {
  // Validate the session and confirm the user is an approver.
  try {
    const me = await api('/api/auth/me');
    state.me = me.user;
    if (!state.me.can_approve) {
      setToken(null); showLogin();
      toast('This console requires a reviewer/admin account.', 'bad');
      return;
    }
    hideLogin();
    loadOverview(); loadApprovals();
  } catch(e) { /* 401 already re-shows login */ }
}

// ---- nav ----
$$('#nav button').forEach(b => b.onclick = () => {
  $$('#nav button').forEach(x => x.classList.remove('active'));
  b.classList.add('active');
  $$('.view').forEach(v => v.classList.remove('active'));
  $('#view-' + b.dataset.view).classList.add('active');
  ({overview:loadOverview, approvals:loadApprovals, documents:loadDocs,
    audit:loadAudit, learning:loadLearning})[b.dataset.view]();
});

// ---- overview ----
async function loadOverview() {
  const [h, agents, learn] = await Promise.all([
    api('/health'), api('/agents'),
    api('/learning').catch(() => null)]);
  $('#health-pill').textContent = 'Ollama ' + (h.ollama_available ? 'online' : 'offline');
  $('#health-pill').className = 'pill ' + (h.ollama_available ? 'ok' : '');
  $('#model-pill').textContent = h.default_model;
  const stats = [
    ['Agents', h.agents, 'specialist agents'],
    ['Pending approvals', h.pending_approvals ?? '—', 'awaiting review'],
    ['Documents', h.documents ?? '—', 'in knowledge store'],
    ['Learning runs', learn ? learn.total_runs : '—', 'self-learning passes'],
  ];
  $('#ov-stats').innerHTML = stats.map(([l,v,hint]) =>
    `<div class="card stat"><div class="label">${l}</div>
     <div class="value">${esc(v)}</div><div class="hint">${hint}</div></div>`).join('');
  $('#ov-agents').innerHTML = `<table><tr><th>ID</th><th>Name</th><th></th></tr>` +
    agents.map(a => `<tr><td class="mono">${esc(a.id)}</td><td>${esc(a.name)}</td>
      <td>${a.enabled ? tag('enabled','ok') : tag('disabled','')}</td></tr>`).join('') + '</table>';
  $('#ov-platform').innerHTML = [
    ['Platform', h.platform], ['Phase', h.phase],
    ['Default model', h.default_model], ['Ollama', h.ollama_available ? 'online' : 'offline'],
  ].map(([k,v]) => `<div class="k">${k}</div><div>${esc(v)}</div>`).join('');
}

// ---- approvals ----
async function loadApprovals() {
  state.approvals = await api('/approvals');
  const c = $('#ap-count'); c.textContent = state.approvals.length ? `(${state.approvals.length})` : '';
  if (!state.approvals.length) { $('#ap-list').innerHTML =
    `<div class="empty">No pending approvals. Nice and clean.</div>`; return; }
  $('#ap-list').innerHTML = `<table><tr><th>ID</th><th>Kind</th><th>Title</th>
    <th>Requested by</th><th>When</th><th>Decide</th></tr>` +
    state.approvals.map(a => `<tr>
      <td class="mono">${esc(a.id)}</td><td>${tag(a.kind,'info')}</td>
      <td>${esc(a.title)}
        <div class="muted mono" style="margin-top:4px">${esc(JSON.stringify(a.payload||{}).slice(0,180))}</div>
      </td><td>${esc(a.requested_by)}</td>
      <td class="muted">${esc((a.requested_at||'').slice(0,19).replace('T',' '))}</td>
      <td><div class="row-actions">
        <button class="btn ok" onclick="decide('${a.id}','approved')">Approve</button>
        <button class="btn bad" onclick="decide('${a.id}','rejected')">Reject</button>
        <button class="btn ghost" onclick="decide('${a.id}','corrected')">Correct</button>
      </div></td></tr>`).join('') + '</table>';
}
async function decide(id, decision) {
  const note = prompt('Decision note (optional):', '') || '';
  // The decision is attributed to the authenticated session user (the
  // server re-checks that this role is an approver).
  try {
    await post('/approvals/decide', { approval_id:id, user: state.me.username,
                                      decision, note });
    toast(`Approval ${id} → ${decision}`, decision==='rejected'?'bad':'ok');
    loadApprovals();
  } catch(e){ toast('Error: '+e.message, 'bad'); }
}

// ---- documents ----
async function loadDocs() {
  const q = $('#doc-q').value.trim();
  const sens = $('#doc-sens').value;
  try {
    if (q) state.docs = await api(`/search?q=${encodeURIComponent(q)}&sensitivity_max=${sens}`);
    else state.docs = await api(`/documents?sensitivity_max=${sens}&limit=100`);
  } catch(e){ toast('Search needs the retrieval endpoint; showing recent docs.', 'bad');
    state.docs = await api(`/documents?sensitivity_max=${sens}&limit=100`); }
  if (!state.docs.length) { $('#doc-list').innerHTML = `<div class="empty">No documents.</div>`; return; }
  $('#doc-list').innerHTML = `<table><tr><th>Title</th><th>Type</th><th>Sensitivity</th>
    <th>Source</th><th>Updated</th></tr>` +
    state.docs.map(d => `<tr style="cursor:pointer" onclick="toggleDoc('${d.id}')">
      <td>${esc(d.title)}</td><td>${tag(d.doc_type||'note','')}</td>
      <td>${statusTag(d.sensitivity)}</td><td class="mono">${esc(d.source||'')}</td>
      <td class="muted">${esc((d.updated_at||d.created_at||'').slice(0,10))}</td></tr>
      <tr id="doc-${d.id}" style="display:none"><td colspan="5">
        <div class="doc-body">${esc(d.content||'')}</div></td></tr>`).join('') + '</table>';
}
function toggleDoc(id) {
  const row = $('#doc-'+id); if (row) row.style.display = row.style.display==='none' ? '' : 'none';
}

// ---- audit ----
async function loadAudit() {
  const p = new URLSearchParams();
  if ($('#au-actor').value) p.set('actor', $('#au-actor').value);
  if ($('#au-action').value) p.set('action', $('#au-action').value);
  if ($('#au-user').value) p.set('user', $('#au-user').value);
  p.set('limit', $('#au-limit').value);
  state.audit = await api('/audit?' + p.toString());
  $('#au-count').textContent = state.audit.length + ' entries';
  if (!state.audit.length) { $('#au-list').innerHTML = `<div class="empty">No audit entries match.</div>`; return; }
  $('#au-list').innerHTML = `<table><tr><th>Time</th><th>Actor</th><th>Action</th>
    <th>User</th><th>Result</th><th>Detail</th></tr>` +
    state.audit.map(e => `<tr><td class="muted mono">${esc((e.at||'').slice(0,19).replace('T',' '))}</td>
      <td class="mono">${esc(e.actor)}</td><td>${esc(e.action)}</td>
      <td>${esc(e.user||'—')}</td><td>${statusTag(e.result||'')}</td>
      <td class="mono muted">${esc(JSON.stringify(e.detail||{}).slice(0,160))}</td></tr>`).join('') + '</table>';
}

// ---- learning ----
async function loadLearning() {
  const d = await api('/learning');
  const last = d.last_run || {};
  const acc = d.holdout_accuracy != null ? (d.holdout_accuracy*100).toFixed(1)+'%' : '—';
  const stats = [
    ['Total runs', d.total_runs, 'learning passes'],
    ['Hold-out accuracy', acc, 'exam ground truth'],
    ['Promoted', d.total_promoted, 'capabilities added'],
    ['Budget / run', d.budget_per_run, 'candidates capped'],
  ];
  $('#learn-stats').innerHTML = stats.map(([l,v,hint]) =>
    `<div class="card stat"><div class="label">${l}</div>
     <div class="value">${esc(v)}</div><div class="hint">${hint}</div></div>`).join('');
  if (d.last_run) {
    $('#learn-report').innerHTML =
      `<div class="kv">
        <div class="k">Last run</div><div class="mono">${esc(last.run_id)}</div>
        <div class="k">Trajectories</div><div>${esc(last.trajectories_processed)}</div>
        <div class="k">Mined</div><div>${esc(last.candidates_mined)}</div>
        <div class="k">Promoted / rejected</div>
          <div>${esc(last.promoted)} / ${esc(last.rejected)}</div>
        <div class="k">Notes</div><div class="muted">${esc((last.notes||[]).join(' · '))}</div>
      </div>`;
  }
  const pending = d.pending_reviews || [];
  $('#learn-pending').innerHTML = pending.length ?
    `<table><tr><th>ID</th><th>Kind</th><th>Scope</th><th>Statement</th><th>Decide</th></tr>` +
    pending.map(p => `<tr><td class="mono">${esc(p.id)}</td>
      <td>${tag(p.kind,'info')}</td><td class="mono">${esc(p.scope)}</td>
      <td>${esc(p.statement)}</td>
      <td><div class="row-actions">
        <button class="btn ok" onclick="reviewCand('${p.id}','approved')">Approve</button>
        <button class="btn bad" onclick="reviewCand('${p.id}','rejected')">Reject</button>
      </div></td></tr>`).join('') + '</table>' :
    `<div class="empty">No candidates awaiting review.</div>`;
  const promos = d.recent_promotions || [];
  $('#learn-promos').innerHTML = promos.length ?
    `<table><tr><th>ID</th><th>Kind</th><th>Scope</th><th>Statement</th></tr>` +
    promos.map(p => `<tr><td class="mono">${esc(p.candidate_id)}</td>
      <td>${tag(p.kind,'info')}</td><td class="mono">${esc(p.scope)}</td>
      <td>${esc(p.statement)}</td></tr>`).join('') :
    `<div class="empty">No promotions yet. Run a learning pass to mine candidates.</div>`;
}
async function reviewCand(id, decision) {
  try {
    await post('/learn/review', { candidate_id:id, decision, user: state.me.username });
    toast(`Candidate ${id} → ${decision}`, decision==='rejected'?'bad':'ok');
    loadLearning();
  } catch(e){ toast('Error: '+e.message, 'bad'); }
}
async function runLearn() {
  const btn = $('#learn-btn'); btn.disabled = true; btn.textContent = 'Running…';
  $('#learn-report').innerHTML = '<span class="muted">Running budgeted learning pass…</span>';
  try {
    const r = await post('/learn', {});
    toast(`Learning run ${r.run_id}: ${r.promoted} promoted, ${r.rejected} rejected`, 'ok');
    loadLearning();
  } catch(e){ toast('Error: '+e.message, 'bad'); }
  finally { btn.disabled = false; btn.textContent = 'Run learning pass'; }
}

// ---- init ----
(async function init() {
  if (getToken()) {
    try {
      const me = await api('/api/auth/me');
      state.me = me.user;
      if (state.me.can_approve) { hideLogin(); enterConsole(); return; }
    } catch(e) { /* fall through to login */ }
  }
  showLogin();
})();
</script>
</body>
</html>
"""


def reviewer_page() -> HTMLResponse:
    return HTMLResponse(_PAGE)


def make_reviewer_routes(app, get_platform):
    """Register the reviewer page + the small extra endpoints the UI needs.

    - GET  /reviewer          the dashboard page (open; shows the login form)
    - GET  /documents         list knowledge-store documents   (auth + approver)
    - GET  /search            hybrid retrieval (doc search box) (auth + approver)
    - GET  /learning          learning dashboard                (auth + approver)
    - POST /learn             trigger a budgeted learning pass  (auth + approver)
    - POST /learn/review      decide a pending learning candidate (auth + approver)

    The data routes require a valid session token AND an approver role
    (admin / manager / reviewer / counsel), because the console exposes
    full document contents, the audit log, approval decisions, and
    learning controls. `get_platform` is the server's lazy platform
    factory, so the routes work even before the first request.
    """

    def _current_user(authorization: Optional[str] = Header(default=None)):
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="missing bearer token")
        token = authorization.split(" ", 1)[1].strip()
        p = get_platform()
        user = p.auth.user_for_token(token)
        if user is None:
            raise HTTPException(status_code=401, detail="invalid or expired session")
        if not user.can_approve:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user.role}' is not authorized for the reviewer console.",
            )
        return user

    @app.get("/reviewer", response_class=HTMLResponse)
    def _reviewer(request: Request):
        get_platform()  # ensure the platform is built
        return reviewer_page()

    @app.get("/documents")
    def _documents(user=Depends(_current_user),
                   sensitivity_max: str = "restricted", limit: int = 100):
        p = get_platform()
        return [
            {
                "id": d.id, "title": d.title, "content": d.content,
                "source": d.source, "doc_type": d.doc_type,
                "sensitivity": d.sensitivity, "tenant": d.tenant,
                "created_at": d.created_at, "updated_at": d.updated_at,
            }
            for d in p.knowledge.list_documents(
                sensitivity_max=sensitivity_max, limit=limit)
        ]

    @app.get("/search")
    def _search(user=Depends(_current_user), q: str = "",
                sensitivity_max: str = "restricted", top_k: int = 12):
        p = get_platform()
        results = p.knowledge.search(q, sensitivity_max=sensitivity_max, top_k=top_k)
        return [
            {
                "id": r.record.id, "title": r.record.title,
                "content": (r.matched_chunks[0] if r.matched_chunks else r.record.content),
                "source": r.record.source, "doc_type": r.record.doc_type,
                "sensitivity": r.record.sensitivity,
                "score": round(r.score, 4),
                "created_at": r.record.created_at, "updated_at": r.record.updated_at,
            }
            for r in results
        ]

    @app.get("/learning")
    def _learning(user=Depends(_current_user)):
        p = get_platform()
        return p.learning_dashboard()

    @app.post("/learn")
    def _learn(user=Depends(_current_user)):
        p = get_platform()
        return p.learn()

    @app.post("/learn/review")
    def _learn_review(body: LearningReviewRequest, user=Depends(_current_user)):
        p = get_platform()
        try:
            ok = p.review_learning_candidate(
                body.candidate_id, body.decision,
                decided_by=body.user or user.username)
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e))
        return {"ok": ok, "candidate_id": body.candidate_id,
                "decision": body.decision}

    return app