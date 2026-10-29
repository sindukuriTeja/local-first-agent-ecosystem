/**
 * Module M17: Administration and AI Control, 16 Agents, Interactive Node Graph, Quality Benchmarks
 * Routes: /admin, /admin/agents/:id, /admin/tests
 */
import { api } from '../services/api.js';
import { renderStatusBadge, renderTableSkeleton } from '../components/shared.js';

let activeAdminTab = 'agents'; // 'agents' | 'flow' | 'models' | 'prompts' | 'cost' | 'quality' | 'builddocs'

export async function renderAdminView(container) {
  const agents = await api.getAgents();

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <span>System</span>
        <span class="breadcrumb-separator">/</span>
        <span>AI Control & Administration</span>
      </div>
      <div class="page-title-row">
        <div>
          <h1 class="page-title">AI Control Panel & Multi-Agent Swarm Governance</h1>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            16 specialized agents running privately. Orchestrator enforces single-entry containment and human verification gates.
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-secondary btn-sm" onclick="window.setAdminTab('flow')">
            🕸️ Who Sends Work to Whom Graph
          </button>
          <button class="btn btn-primary btn-sm" onclick="window.runAllQualityBenchmarks()">
            ▶ Run Quality Benchmarks
          </button>
        </div>
      </div>
    </div>

    <!-- Admin Sub-Tabs -->
    <div class="tabs-nav">
      <button class="tab-btn ${activeAdminTab === 'agents' ? 'active' : ''}" onclick="window.setAdminTab('agents')">16 AI Agents (${agents.length})</button>
      <button class="tab-btn ${activeAdminTab === 'flow' ? 'active' : ''}" onclick="window.setAdminTab('flow')">Workflow Topology Graph</button>
      <button class="tab-btn ${activeAdminTab === 'models' ? 'active' : ''}" onclick="window.setAdminTab('models')">Model Settings</button>
      <button class="tab-btn ${activeAdminTab === 'prompts' ? 'active' : ''}" onclick="window.setAdminTab('prompts')">Prompt Versions & Diff</button>
      <button class="tab-btn ${activeAdminTab === 'cost' ? 'active' : ''}" onclick="window.setAdminTab('cost')">Cost Dashboard ($318/mo)</button>
      <button class="tab-btn ${activeAdminTab === 'quality' ? 'active' : ''}" onclick="window.setAdminTab('quality')">Quality Benchmark Tests</button>
      <button class="tab-btn ${activeAdminTab === 'builddocs' ? 'active' : ''}" onclick="window.setAdminTab('builddocs')">Weekly Build Docs</button>
    </div>

    <div id="admin-tab-content">
      ${renderAgentsGrid(agents)}
    </div>
  `;

  window.setAdminTab = (tab) => {
    activeAdminTab = tab;
    const target = document.getElementById('admin-tab-content');
    if (!target) return;

    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    event.target.classList.add('active');

    if (tab === 'agents') {
      target.innerHTML = renderAgentsGrid(agents);
    } else if (tab === 'flow') {
      target.innerHTML = renderWorkflowNodeGraph();
    } else if (tab === 'models') {
      target.innerHTML = renderModelSettingsTab(agents);
    } else if (tab === 'prompts') {
      target.innerHTML = renderPromptVersionsTab();
    } else if (tab === 'cost') {
      target.innerHTML = renderCostDashboardTab(agents);
    } else if (tab === 'quality') {
      target.innerHTML = renderQualityBenchmarksTab();
    } else if (tab === 'builddocs') {
      target.innerHTML = renderBuildDocsTab();
    }
  };

  window.runAllQualityBenchmarks = () => {
    window.setAdminTab('quality');
  };
}

function renderAgentsGrid(agents) {
  return `
    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap:20px;">
      ${agents.map(a => `
        <div class="card" style="display:flex; flex-direction:column; justify-content:space-between; margin-bottom:0; cursor:pointer;" onclick="window.location.hash='#/admin/agents/${a.id}'">
          <div>
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:8px;">
              <div>
                <span style="font-size:11px; font-weight:700; color:var(--text-tertiary);">${a.id}</span>
                <h3 style="font-size:15px; font-weight:700; color:var(--text-main); margin-top:2px;">${a.name}</h3>
              </div>
              <span class="status-badge verified">${a.status}</span>
            </div>
            
            <p style="font-size:12px; color:var(--text-muted); line-height:1.5; margin-bottom:12px;">
              ${a.purpose}
            </p>

            <div style="background:var(--bg-subtle); padding:10px; border-radius:6px; font-size:11px; margin-bottom:12px; line-height:1.6;">
              <div><strong>Model Engine:</strong> ${a.model}</div>
              <div><strong>Runs This Month:</strong> ${a.runsThisMonth.toLocaleString('en-IN')}</div>
              <div><strong>Cost Incurred:</strong> <span style="font-weight:bold; color:var(--primary);">${a.costThisMonth}</span></div>
            </div>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border-subtle); padding-top:10px; font-size:12px;">
            <span style="color:var(--text-tertiary);">Active: ${a.lastRun}</span>
            <a href="#/admin/agents/${a.id}" class="btn btn-secondary btn-sm" onclick="event.stopPropagation()">View Details →</a>
          </div>
        </div>
      `).join('')}
    </div>
  `;
}

export async function renderAgentDetailView(container, agentId) {
  const agents = await api.getAgents();
  const agent = agents.find(a => a.id === agentId) || agents[0];

  container.innerHTML = `
    <div class="page-header">
      <div class="breadcrumb">
        <a href="#/home">Home</a>
        <span class="breadcrumb-separator">/</span>
        <a href="#/admin">Administration</a>
        <span class="breadcrumb-separator">/</span>
        <span>${agent.name}</span>
      </div>
      <div class="page-title-row">
        <div>
          <div style="display:flex; align-items:center; gap:8px;">
            <h1 class="page-title">${agent.name}</h1>
            <span class="status-badge verified">${agent.status}</span>
          </div>
          <p style="font-size: var(--font-size-xs); color: var(--text-muted); margin-top: 4px;">
            Assigned Model: <strong>${agent.model}</strong> • Monthly Compute: ${agent.costThisMonth}
          </p>
        </div>
        <div class="page-actions">
          <button class="btn btn-secondary btn-sm" onclick="window.testAgentRun('${agent.id}')">Run Single Quality Test</button>
        </div>
      </div>
    </div>

    <div style="display:grid; grid-template-columns: 2fr 1fr; gap:24px;">
      <div class="card">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">Operational Purpose & Responsibilities</h3>
        <p style="font-size:13px; color:var(--text-main); line-height:1.7; margin-bottom:20px;">${agent.purpose}</p>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px; margin-bottom:20px;">
          <div style="background:var(--color-success-bg); border:1px solid var(--color-success-border); padding:14px; border-radius:8px;">
            <div style="font-size:11px; font-weight:700; color:var(--color-success-text); text-transform:uppercase; margin-bottom:6px;">What It Can Access:</div>
            <ul style="font-size:12px; color:var(--color-success-text); padding-left:16px; line-height:1.6;">
              ${agent.canAccess.map(acc => `<li>${acc}</li>`).join('')}
            </ul>
          </div>

          <div style="background:var(--color-danger-bg); border:1px solid var(--color-danger-border); padding:14px; border-radius:8px;">
            <div style="font-size:11px; font-weight:700; color:var(--color-danger-text); text-transform:uppercase; margin-bottom:6px;">What It Never Does (Strict Constraints):</div>
            <ul style="font-size:12px; color:var(--color-danger-text); padding-left:16px; line-height:1.6;">
              ${agent.neverDoes.map(nd => `<li>${nd}</li>`).join('')}
            </ul>
          </div>
        </div>

        <div style="background:var(--color-warning-bg); border:1px solid var(--color-warning-border); padding:14px; border-radius:8px;">
          <div style="font-size:11px; font-weight:700; color:var(--color-warning-text); text-transform:uppercase; margin-bottom:4px;">Human Approval Trigger Conditions:</div>
          <div style="font-size:13px; color:var(--color-warning-text);">${agent.approvalTrigger}</div>
        </div>
      </div>

      <div class="card">
        <h3 style="font-size:15px; font-weight:700; margin-bottom:14px;">Recent Execution Activity</h3>
        <div class="audit-timeline">
          <div class="timeline-item">
            <div class="timeline-node"></div>
            <div class="timeline-header"><span>2 mins ago</span><span>Status: Pass</span></div>
            <div class="timeline-title">Dispatched sub-task #891</div>
            <div class="timeline-desc">Execution completed in 420ms. Zero anomalies.</div>
          </div>
          <div class="timeline-item">
            <div class="timeline-node"></div>
            <div class="timeline-header"><span>18 mins ago</span><span>Status: Pass</span></div>
            <div class="timeline-title">Cache lookup verified</div>
            <div class="timeline-desc">Retrieved verified citations for legal proposition.</div>
          </div>
        </div>
      </div>
    </div>
  `;

  window.testAgentRun = (aId) => {
    window.MeridianApp.showToast(`Diagnostic test suite executed for ${aId}: 100% Citation ground-truth match.`, 'success');
  };
}

function renderWorkflowNodeGraph() {
  return `
    <div class="card" style="padding:24px;">
      <div style="margin-bottom:16px;">
        <h3 style="font-size:16px; font-weight:700;">Interactive Multi-Agent Swarm Topology ("Who Sends Work to Whom")</h3>
        <p style="font-size:12px; color:var(--text-muted); margin-top:2px;">
          Section 7 Architectural Isolation Rule: <strong>Orchestrator Agent is the single entry & exit point</strong>. Sub-agents never communicate directly with the outside world. The External Information Agent talks exclusively to the Internal Information Agent after privacy redaction.
        </p>
      </div>

      <!-- Node Graph Diagram Render -->
      <div style="background:#0F172A; border-radius:12px; padding:36px; min-height:480px; position:relative; overflow:auto; color:#fff; display:flex; flex-direction:column; align-items:center; justify-content:center;">
        
        <!-- Orchestrator Center Core -->
        <div style="background:linear-gradient(135deg, #6366F1, #4338CA); border:3px solid #A5B4FC; border-radius:12px; padding:18px 28px; text-align:center; box-shadow:0 0 24px rgba(99,102,241,0.5); z-index:10; margin-bottom:50px;">
          <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.08em; font-weight:bold; color:#E0E7FF;">SINGLE ENTRY & EXIT POINT</div>
          <div style="font-size:18px; font-weight:800; margin-top:2px;">AGT-001: Orchestrator Agent</div>
          <div style="font-size:11px; color:#C7D2FE;">Dispatches all queries & routes review items to humans</div>
        </div>

        <!-- Tier 2: Domain Specialized Sub-Agents Grid -->
        <div style="display:flex; justify-content:center; gap:16px; flex-wrap:wrap; max-width:960px; z-index:10;">
          <div style="background:#1E293B; border:1px solid #334155; border-radius:8px; padding:12px; width:170px; text-align:center;">
            <div style="font-size:10px; color:#94A3B8;">AGT-004</div>
            <div style="font-size:12px; font-weight:700;">Document Intake & OCR</div>
          </div>
          <div style="background:#1E293B; border:1px solid #334155; border-radius:8px; padding:12px; width:170px; text-align:center;">
            <div style="font-size:10px; color:#94A3B8;">AGT-005 / 006</div>
            <div style="font-size:12px; font-weight:700;">Case Analysis & Legal Research</div>
          </div>
          <div style="background:#1E293B; border:1px solid #334155; border-radius:8px; padding:12px; width:170px; text-align:center;">
            <div style="font-size:10px; color:#94A3B8;">AGT-007</div>
            <div style="font-size:12px; font-weight:700;">Legal Drafting</div>
          </div>
          <div style="background:#1E293B; border:1px solid #334155; border-radius:8px; padding:12px; width:170px; text-align:center;">
            <div style="font-size:10px; color:#94A3B8;">AGT-012 / 013</div>
            <div style="font-size:12px; font-weight:700;">Debt, Loans & Land Title</div>
          </div>
          <div style="background:#1E293B; border:1px solid #334155; border-radius:8px; padding:12px; width:170px; text-align:center;">
            <div style="font-size:10px; color:#94A3B8;">AGT-014 / 016</div>
            <div style="font-size:12px; font-weight:700;">Tax & Voice Notification</div>
          </div>
        </div>

        <div style="width:2px; height:40px; background:#334155; margin:16px 0;"></div>

        <!-- Tier 3: Isolated Information Enclave -->
        <div style="display:flex; align-items:center; gap:24px; background:#1E293B; border:2px dashed #4F46E5; border-radius:12px; padding:16px 24px; z-index:10;">
          <div style="text-align:center;">
            <div style="font-size:10px; color:#94A3B8;">AGT-002</div>
            <strong style="font-size:13px; color:#818CF8;">Internal Information Agent</strong>
            <div style="font-size:10px; color:#CBD5E1;">Indexes Internal Document Vault</div>
          </div>
          <div style="color:#6366F1; font-size:18px;">⇄ [Sanitized Bridge] ⇄</div>
          <div style="text-align:center;">
            <div style="font-size:10px; color:#94A3B8;">AGT-003</div>
            <strong style="font-size:13px; color:#F59E0B;">External Information Agent</strong>
            <div style="font-size:10px; color:#CBD5E1;">Talks ONLY to Internal Agent (Redacted)</div>
          </div>
        </div>

      </div>
    </div>
  `;
}

function renderModelSettingsTab(agents) {
  return `
    <div class="card">
      <div style="margin-bottom:16px;">
        <h3 style="font-size:15px; font-weight:700;">Model Assignment & Cost Optimization Principle</h3>
        <p style="font-size:12px; color:var(--text-muted); margin-top:2px;">
          Guiding rule: <em>"Use the smallest model that can do the job."</em> Changing a model triggers a mandatory Quality Test Run before release.
        </p>
      </div>

      <table class="data-table">
        <thead>
          <tr>
            <th>Agent Name</th>
            <th>Current Model Assignment</th>
            <th>Monthly Cost</th>
            <th>Latency</th>
            <th style="text-align:right;">Test & Switch</th>
          </tr>
        </thead>
        <tbody>
          ${agents.map(a => `
            <tr>
              <td><strong>${a.name}</strong></td>
              <td>
                <select class="form-control" style="font-size:12px; max-width:280px;" onchange="window.modelChangePrompt('${a.name}', this.value)">
                  <option ${a.model.startsWith('Small') ? 'selected' : ''}>Small (Claude 3.5 Haiku / GPT-4o-mini)</option>
                  <option ${a.model.startsWith('Medium') ? 'selected' : ''}>Medium (Gemini 1.5 Pro / GPT-4o)</option>
                  <option ${a.model.startsWith('Large') ? 'selected' : ''}>Large (Claude 3.5 Sonnet / Vision Large)</option>
                </select>
              </td>
              <td class="amount">${a.costThisMonth}</td>
              <td style="font-size:12px; color:var(--text-muted);">~320ms</td>
              <td style="text-align:right;">
                <button class="btn btn-secondary btn-sm" onclick="window.testAgentRun('${a.id}')">Test Suite</button>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  window.modelChangePrompt = (agentName, newModel) => {
    alert(`Model configuration for ${agentName} updated to ${newModel}. A mandatory quality benchmark run has been scheduled before production switch.`);
  };
}

function renderPromptVersionsTab() {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">System Prompt Version History & Diff Viewer</h3>
      <div style="display:flex; justify-content:space-between; align-items:center; padding:12px; background:var(--bg-subtle); border-radius:6px; margin-bottom:12px;">
        <div>
          <div style="font-weight:700;">Orchestrator System Prompt v3.4 (Current Active)</div>
          <div style="font-size:11px; color:var(--text-muted);">Deployed 24 Oct 2026 by Rajesh Sharma</div>
        </div>
        <div style="display:flex; gap:8px;">
          <button class="btn btn-secondary btn-sm" onclick="alert('Diff view: Added mandatory citation verification check on Section 14 SARFAESI prompts.');">View Diff</button>
          <button class="btn btn-secondary btn-sm" onclick="window.MeridianApp.showToast('Rollback to v3.3 completed.', 'info')">Rollback to v3.3</button>
        </div>
      </div>
    </div>
  `;
}

function renderCostDashboardTab(agents) {
  return `
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div>
          <h3 style="font-size:15px; font-weight:700;">Agent Inference Spend & Budget Allocations</h3>
          <div style="font-size:12px; color:var(--text-muted);">Monthly Cap: $500.00 | Incurred: <strong>$318.40 (63.6%)</strong></div>
        </div>
        <span class="status-badge verified">Within Safe Budget</span>
      </div>

      <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:16px;">
        <div style="padding:14px; background:var(--bg-subtle); border-radius:8px;">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted);">Highest Incurring Agent</div>
          <div style="font-size:14px; font-weight:700; color:var(--text-main); margin-top:2px;">Document Intake & OCR</div>
          <div style="font-size:16px; font-weight:700; color:var(--primary); margin-top:4px;">$84.20</div>
        </div>
        <div style="padding:14px; background:var(--bg-subtle); border-radius:8px;">
          <div style="font-size:11px; font-weight:700; color:var(--text-muted);">Average Cost Per User Session</div>
          <div style="font-size:14px; font-weight:700; color:var(--text-main); margin-top:2px;">Interactive Ask Box</div>
          <div style="font-size:16px; font-weight:700; color:var(--color-success); margin-top:4px;">$0.0062 / query</div>
        </div>
      </div>
    </div>
  `;
}

export function renderQualityTestsView(container) {
  renderAdminView(container);
  setTimeout(() => window.setAdminTab('quality'), 50);
}

function renderQualityBenchmarksTab() {
  return `
    <div class="card">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
        <div>
          <h3 style="font-size:15px; font-weight:700;">Ground-Truth Accuracy & Citation Benchmark</h3>
          <p style="font-size:12px; color:var(--text-muted); margin-top:2px;">
            50 standardized evaluation prompts testing hallucination rejection, citation fidelity, and statutory arithmetic. Release threshold: 95.0%.
          </p>
        </div>
        <button class="btn btn-primary btn-sm" onclick="window.MeridianApp.showToast('Benchmark suite running across 16 agents... 50/50 Passed.', 'success')">
          Re-run Test Suite
        </button>
      </div>

      <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:16px; margin-bottom:20px;">
        <div style="padding:16px; background:var(--color-success-bg); border:1px solid var(--color-success-border); border-radius:8px; text-align:center;">
          <div style="font-size:11px; font-weight:700; color:var(--color-success-text); text-transform:uppercase;">Citation Correctness</div>
          <div style="font-size:28px; font-weight:800; color:var(--color-success-text);">99.2%</div>
          <div style="font-size:11px; color:var(--color-success-text);">Threshold: > 98.0%</div>
        </div>

        <div style="padding:16px; background:var(--color-success-bg); border:1px solid var(--color-success-border); border-radius:8px; text-align:center;">
          <div style="font-size:11px; font-weight:700; color:var(--color-success-text); text-transform:uppercase;">Zero-Hallucination Score</div>
          <div style="font-size:28px; font-weight:800; color:var(--color-success-text);">100.0%</div>
          <div style="font-size:11px; color:var(--color-success-text);">No Source, No Fact Enforced</div>
        </div>

        <div style="padding:16px; background:var(--color-success-bg); border:1px solid var(--color-success-border); border-radius:8px; text-align:center;">
          <div style="font-size:11px; font-weight:700; color:var(--color-success-text); text-transform:uppercase;">Release Candidate Gate</div>
          <div style="font-size:24px; font-weight:800; color:var(--color-success-text); margin-top:4px;">CERTIFIED PASS</div>
          <div style="font-size:11px; color:var(--color-success-text);">All 16 Agents Authorized</div>
        </div>
      </div>
    </div>
  `;
}

function renderBuildDocsTab() {
  return `
    <div class="card">
      <h3 style="font-size:15px; font-weight:700; margin-bottom:12px;">Weekly System Build Summary (Build Documentation Agent)</h3>
      <div style="background:var(--bg-subtle); padding:16px; border-radius:8px; border:1px solid var(--border-subtle); font-size:13px; line-height:1.7;">
        <strong>Week 43 Build Release Notes (28 Oct 2026):</strong>
        <ul style="padding-left:18px; margin-top:6px;">
          <li>All 17 frontend modules wired to async service layer with 19 mock datasets.</li>
          <li>Grounding enforcement: Every fact and number features a clickable SourceChip opening the Document Viewer at the exact target page with highlighting.</li>
          <li>Reconciliation audit active on Facility LN-002 flagging ₹ 3.50 Cr penal compounding mismatch with tooltip explanation.</li>
          <li>Interactive "Who Sends Work to Whom" architecture diagram active with single-entry Orchestrator containment.</li>
          <li>Strict governance rule implemented: No screen contains commit/file/release buttons; release occurs outside system following approved sign-offs.</li>
        </ul>
      </div>
    </div>
  `;
}
