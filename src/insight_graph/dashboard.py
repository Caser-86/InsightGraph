# ruff: noqa: E501

_DASHBOARD_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InsightGraph Dashboard</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #061018;
      --panel: rgba(11, 27, 40, 0.82);
      --panel-strong: rgba(13, 37, 52, 0.94);
      --line: rgba(96, 219, 220, 0.22);
      --line-hot: rgba(96, 219, 220, 0.66);
      --text: #eefcff;
      --muted: #87a6b3;
      --cyan: #63f2e3;
      --cyan-soft: rgba(99, 242, 227, 0.14);
      --green: #74f6a7;
      --amber: #ffc857;
      --red: #ff6b82;
      --blue: #7eb6ff;
      --shadow: 0 24px 70px rgba(0, 0, 0, 0.42);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      background:
        radial-gradient(circle at 12% 8%, rgba(60, 242, 222, 0.16), transparent 30%),
        radial-gradient(circle at 88% 12%, rgba(80, 124, 255, 0.18), transparent 28%),
        linear-gradient(135deg, #03080d 0%, #07131d 44%, #0b1722 100%);
      color: var(--text);
      font-family:
        Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI",
        sans-serif;
    }

    button, input, select, textarea { font: inherit; }

    button {
      border: 0;
      color: var(--text);
      cursor: pointer;
    }

    button:disabled { cursor: not-allowed; opacity: 0.48; }

    .shell {
      width: min(1480px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 24px 0 36px;
    }

    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .logo {
      display: grid;
      width: 44px;
      height: 44px;
      place-items: center;
      border: 1px solid var(--line-hot);
      border-radius: 14px;
      background: linear-gradient(145deg, rgba(99, 242, 227, 0.22), rgba(126, 182, 255, 0.08));
      box-shadow: 0 0 28px rgba(99, 242, 227, 0.2);
      color: var(--cyan);
      font-weight: 800;
      letter-spacing: -0.06em;
    }

    h1, h2, h3, p { margin: 0; }

    h1 {
      font-size: clamp(1.35rem, 2.4vw, 2.2rem);
      letter-spacing: -0.04em;
    }

    .eyebrow {
      color: var(--cyan);
      font-size: 0.72rem;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }

    .subtitle { color: var(--muted); font-size: 0.92rem; }

    .status-row { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      padding: 7px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(9, 23, 35, 0.76);
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 700;
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--cyan);
      box-shadow: 0 0 16px var(--cyan);
    }

    .grid {
      display: grid;
      grid-template-columns: minmax(320px, 420px) 1fr;
      gap: 18px;
      align-items: start;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: linear-gradient(180deg, var(--panel-strong), var(--panel));
      box-shadow: var(--shadow), inset 0 1px 0 rgba(255, 255, 255, 0.04);
      overflow: hidden;
    }

    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 18px 18px 0;
    }

    .panel-title { font-size: 1rem; letter-spacing: -0.02em; }

    .panel-body { padding: 18px; }

    .form-stack { display: grid; gap: 14px; }

    label {
      display: grid;
      gap: 7px;
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 800;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }

    input, select, textarea {
      width: 100%;
      border: 1px solid rgba(117, 229, 232, 0.2);
      border-radius: 14px;
      outline: 0;
      background: rgba(2, 10, 16, 0.58);
      color: var(--text);
      padding: 12px 13px;
    }

    textarea { min-height: 128px; resize: vertical; line-height: 1.5; }

    input:focus, select:focus, textarea:focus {
      border-color: var(--line-hot);
      box-shadow: 0 0 0 4px var(--cyan-soft);
    }

    .actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

    .btn {
      min-height: 44px;
      border-radius: 14px;
      background: rgba(99, 242, 227, 0.11);
      border: 1px solid var(--line);
      font-weight: 800;
    }

    .btn.primary {
      background: linear-gradient(135deg, #30d8cf, #497cff);
      color: #021017;
      box-shadow: 0 16px 38px rgba(48, 216, 207, 0.18);
    }

    .btn.danger { border-color: rgba(255, 107, 130, 0.44); color: var(--red); }

    .btn.ghost { color: var(--cyan); }

    .message {
      min-height: 24px;
      color: var(--muted);
      font-size: 0.86rem;
      line-height: 1.45;
    }

    .message.error { color: var(--red); }
    .message.ok { color: var(--green); }

    .metric-grid {
      display: grid;
      grid-template-columns: repeat(6, minmax(112px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(8, 24, 36, 0.68);
      padding: 15px;
      min-height: 104px;
    }

    .metric span {
      display: block;
      color: var(--muted);
      font-size: 0.7rem;
      font-weight: 800;
      letter-spacing: 0.14em;
      text-transform: uppercase;
    }

    .metric strong {
      display: block;
      margin-top: 10px;
      color: var(--text);
      font-size: clamp(1.55rem, 3vw, 2.3rem);
      letter-spacing: -0.05em;
    }

    .workspace {
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      gap: 18px;
    }

    .job-list { display: grid; gap: 10px; max-height: 640px; overflow: auto; }

    .job-card {
      width: 100%;
      border: 1px solid rgba(117, 229, 232, 0.15);
      border-radius: 18px;
      background: rgba(4, 16, 25, 0.72);
      padding: 13px;
      text-align: left;
    }

    .job-card.active {
      border-color: var(--line-hot);
      box-shadow: inset 0 0 0 1px rgba(99, 242, 227, 0.15), 0 0 28px rgba(99, 242, 227, 0.08);
    }

    .job-card h3 {
      margin: 9px 0 8px;
      font-size: 0.94rem;
      line-height: 1.35;
    }

    .job-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      color: var(--muted);
      font-size: 0.75rem;
    }

    .status-chip {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 8px;
      background: rgba(126, 182, 255, 0.12);
      color: var(--blue);
      font-size: 0.7rem;
      font-weight: 900;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .status-chip.queued { color: var(--amber); background: rgba(255, 200, 87, 0.12); }
    .status-chip.running { color: var(--cyan); background: rgba(99, 242, 227, 0.12); }
    .status-chip.succeeded { color: var(--green); background: rgba(116, 246, 167, 0.12); }
    .status-chip.failed, .status-chip.cancelled { color: var(--red); background: rgba(255, 107, 130, 0.12); }

    .tabs {
      display: flex;
      gap: 8px;
      padding: 12px;
      border-bottom: 1px solid var(--line);
      overflow-x: auto;
    }

    .tab {
      flex: 0 0 auto;
      border: 1px solid transparent;
      border-radius: 999px;
      background: transparent;
      color: var(--muted);
      padding: 8px 12px;
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0.07em;
      text-transform: uppercase;
    }

    .tab.active { border-color: var(--line-hot); color: var(--cyan); background: var(--cyan-soft); }

    .tab-panel { min-height: 640px; }

    .detail-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 14px; }

    .progress-timeline {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 10px;
      margin: 0 0 14px;
    }

    .progress-step {
      border: 1px solid rgba(117, 229, 232, 0.14);
      border-radius: 16px;
      background: rgba(2, 10, 16, 0.42);
      padding: 12px;
      min-height: 86px;
    }

    .progress-step.completed { border-color: rgba(116, 246, 167, 0.45); }
    .progress-step.active { border-color: var(--line-hot); box-shadow: 0 0 24px rgba(99, 242, 227, 0.1); }
    .progress-step.failed { border-color: rgba(255, 107, 130, 0.54); }
    .progress-step.skipped { opacity: 0.62; }

    .progress-step span {
      color: var(--muted);
      font-size: 0.66rem;
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .progress-step strong { display: block; margin-top: 8px; }

    .progress-bar {
      height: 8px;
      border: 1px solid rgba(117, 229, 232, 0.14);
      border-radius: 999px;
      background: rgba(2, 10, 16, 0.58);
      margin: 0 0 14px;
      overflow: hidden;
    }

    .progress-bar-fill {
      height: 100%;
      width: 0;
      background: linear-gradient(90deg, var(--cyan), var(--green));
      box-shadow: 0 0 22px rgba(99, 242, 227, 0.3);
    }

    .overview-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .info-card {
      border: 1px solid rgba(117, 229, 232, 0.14);
      border-radius: 18px;
      background: rgba(2, 10, 16, 0.42);
      padding: 14px;
      min-height: 86px;
    }

    .info-card span {
      display: block;
      color: var(--muted);
      font-size: 0.69rem;
      font-weight: 900;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }

    .info-card strong { display: block; margin-top: 8px; overflow-wrap: anywhere; }

    .markdown, .data-list, pre { color: #dff8fb; line-height: 1.62; }

    .live-events { display: grid; gap: 10px; }

    .live-event {
      border: 1px solid rgba(117, 229, 232, 0.14);
      border-radius: 16px;
      background: rgba(2, 10, 16, 0.42);
      padding: 12px;
    }

    .live-event span {
      color: var(--cyan);
      font-size: 0.7rem;
      font-weight: 900;
      letter-spacing: 0.1em;
      text-transform: uppercase;
    }

    .live-event p { color: var(--muted); margin-top: 6px; }

    .markdown h1, .markdown h2, .markdown h3 { margin: 0.9em 0 0.45em; }
    .markdown p, .markdown ul, .markdown pre { margin: 0.7em 0; }
    .markdown a { color: var(--cyan); }
    .markdown code, pre {
      border: 1px solid rgba(117, 229, 232, 0.14);
      border-radius: 12px;
      background: rgba(2, 10, 16, 0.64);
      padding: 2px 5px;
    }
    pre { overflow: auto; padding: 14px; white-space: pre-wrap; }

    .empty {
      display: grid;
      min-height: 260px;
      place-items: center;
      border: 1px dashed rgba(117, 229, 232, 0.18);
      border-radius: 18px;
      color: var(--muted);
      text-align: center;
      padding: 24px;
    }

    @media (max-width: 1120px) {
      .grid, .workspace { grid-template-columns: 1fr; }
      .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
      .progress-timeline { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .job-list { max-height: none; }
    }

    @media (max-width: 680px) {
      .shell { width: min(100% - 18px, 1480px); padding-top: 12px; }
      .topbar { align-items: flex-start; flex-direction: column; }
      .status-row { justify-content: flex-start; }
      .metric-grid, .overview-grid, .actions { grid-template-columns: 1fr; }
      .progress-timeline { grid-template-columns: 1fr; }
      .panel { border-radius: 18px; }
    }
  </style>
</head>
<body data-insightgraph-dashboard>
  <div id="dashboard-root" class="shell">
    <header class="topbar">
      <div class="brand">
        <div class="logo">IG</div>
        <div>
          <div class="eyebrow">Research Command Center</div>
          <h1>InsightGraph Dashboard</h1>
          <p class="subtitle">Create jobs, watch execution, and inspect reports.</p>
        </div>
      </div>
      <div class="status-row">
        <span class="pill"><span class="dot"></span><span id="connection-state">booting</span></span>
        <button id="auto-refresh" class="pill" type="button">auto refresh on</button>
      </div>
    </header>

    <div class="grid">
      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="eyebrow">Launch</div>
            <h2 class="panel-title">Research job</h2>
          </div>
        </div>
        <div class="panel-body form-stack">
          <label>API key
            <input id="api-key" autocomplete="off" placeholder="Optional bearer key">
          </label>
          <label>Preset
            <select id="preset-input">
              <option value="offline">offline</option>
              <option value="live-llm">live-llm</option>
            </select>
          </label>
          <label>Query
            <textarea id="query-input" spellcheck="true"></textarea>
          </label>
          <div class="actions">
            <button id="submit-job" class="btn primary" type="button">Submit job</button>
            <button id="refresh-now" class="btn ghost" type="button">Refresh</button>
          </div>
          <p id="message" class="message"></p>
        </div>
      </section>

      <main>
        <section class="metric-grid" aria-label="Job metrics">
          <div class="metric"><span>Total</span><strong id="metric-total">0</strong></div>
          <div class="metric"><span>Queued</span><strong id="metric-queued">0</strong></div>
          <div class="metric"><span>Running</span><strong id="metric-running">0</strong></div>
          <div class="metric"><span>Succeeded</span><strong id="metric-succeeded">0</strong></div>
          <div class="metric"><span>Failed</span><strong id="metric-failed">0</strong></div>
          <div class="metric"><span>Active</span><strong id="metric-active">0/0</strong></div>
        </section>

        <div class="workspace">
          <section class="panel">
            <div class="panel-head">
              <div>
                <div class="eyebrow">Progress</div>
                <h2 class="panel-title">Recent jobs</h2>
              </div>
            </div>
            <div class="panel-body">
              <div id="job-list" class="job-list"></div>
            </div>
          </section>

          <section class="panel">
            <nav class="tabs" aria-label="Job detail tabs">
              <button class="tab active" data-tab="overview" type="button">Overview</button>
              <button class="tab" data-tab="report" type="button">Report</button>
              <button class="tab" data-tab="findings" type="button">Findings</button>
              <button class="tab" data-tab="evidence" type="button">Evidence</button>
              <button class="tab" data-tab="citations" type="button">Citations</button>
              <button class="tab" data-tab="quality" type="button">Quality</button>
              <button class="tab" data-tab="tools" type="button">Tool Calls</button>
              <button class="tab" data-tab="llm" type="button">LLM Log</button>
              <button class="tab" data-tab="events" type="button">Live Events</button>
              <button class="tab" data-tab="eval" type="button">Eval</button>
              <button class="tab" data-tab="raw" type="button">Raw JSON</button>
            </nav>
            <div id="report-panel" class="panel-body tab-panel"></div>
          </section>
        </div>
      </main>
    </div>
  </div>

  <script>
    const state = {
      jobs: [],
      detail: null,
      selectedJobId: localStorage.getItem('insightgraph.dashboard.jobId') || '',
      activeTab: 'overview',
      autoRefresh: true,
      timer: null,
      streamSocket: null,
      streamJobId: '',
      streamApiKey: '',
      streamTerminal: false,
      liveEvents: [],
    };

    const els = {
      apiKey: document.getElementById('api-key'),
      preset: document.getElementById('preset-input'),
      query: document.getElementById('query-input'),
      submit: document.getElementById('submit-job'),
      refresh: document.getElementById('refresh-now'),
      message: document.getElementById('message'),
      connection: document.getElementById('connection-state'),
      autoRefresh: document.getElementById('auto-refresh'),
      jobList: document.getElementById('job-list'),
      reportPanel: document.getElementById('report-panel'),
      metrics: {
        total: document.getElementById('metric-total'),
        queued: document.getElementById('metric-queued'),
        running: document.getElementById('metric-running'),
        succeeded: document.getElementById('metric-succeeded'),
        failed: document.getElementById('metric-failed'),
        active: document.getElementById('metric-active'),
      },
    };

    const defaultQuery = 'Compare Cursor, OpenCode, and GitHub Copilot';
    els.apiKey.value = localStorage.getItem('insightgraph.dashboard.apiKey') || '';
    els.query.value = localStorage.getItem('insightgraph.dashboard.query') || defaultQuery;
    els.preset.value = localStorage.getItem('insightgraph.dashboard.preset') || 'offline';

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function headers(json = false) {
      const result = {};
      const key = els.apiKey.value.trim();
      if (json) result['Content-Type'] = 'application/json';
      if (key) result.Authorization = `Bearer ${key}`;
      return result;
    }

    async function apiFetch(path, options = {}) {
      const response = await fetch(path, options);
      let payload = null;
      try { payload = await response.json(); } catch (_) { payload = null; }
      if (!response.ok) {
        const detail = payload && payload.detail ? payload.detail : response.statusText;
        const error = new Error(detail || 'Request failed');
        error.status = response.status;
        throw error;
      }
      return payload;
    }

    function setMessage(text, kind = '') {
      els.message.textContent = text;
      els.message.className = `message ${kind}`.trim();
    }

    function statusClass(status) {
      return `status-chip ${escapeHtml(status || 'unknown')}`;
    }

    function renderMetrics(summary) {
      const counts = summary?.counts || {};
      els.metrics.total.textContent = counts.total || 0;
      els.metrics.queued.textContent = counts.queued || 0;
      els.metrics.running.textContent = counts.running || 0;
      els.metrics.succeeded.textContent = counts.succeeded || 0;
      els.metrics.failed.textContent = counts.failed || 0;
      els.metrics.active.textContent = `${summary?.active_count || 0}/${summary?.active_limit || 0}`;
    }

    function renderJobList() {
      if (!state.jobs.length) {
        els.jobList.innerHTML = '<div class="empty">No jobs yet. Submit a query to start.</div>';
        return;
      }
      els.jobList.innerHTML = state.jobs.map((job) => {
        const active = job.job_id === state.selectedJobId ? ' active' : '';
        const queue = job.queue_position ? `Queue #${job.queue_position}` : job.preset;
        return `
          <button class="job-card${active}" data-job-id="${escapeHtml(job.job_id)}" type="button">
            <span class="${statusClass(job.status)}">${escapeHtml(job.status)}</span>
            <h3>${escapeHtml(job.query || job.job_id)}</h3>
            <div class="job-meta">
              <span>${escapeHtml(queue)}</span>
              <span>${escapeHtml(job.created_at || '')}</span>
            </div>
          </button>`;
      }).join('');
    }

    function renderLiveEvent(event) {
      const stage = event.stage ? ` - ${event.stage}` : '';
      const record = event.record || {};
      const summary = record.tool_name || record.model || record.stage || event.detail || 'received';
      return `
        <div class="live-event">
          <span>${escapeHtml(event.type)}${escapeHtml(stage)}</span>
          <p>${escapeHtml(summary)}</p>
        </div>`;
    }

    function appendLiveEvent(event) {
      state.liveEvents = [...state.liveEvents, event].slice(-80);
      if (state.activeTab === 'events') renderDetail();
    }

    function jobIsTerminal(status) {
      return ['succeeded', 'failed', 'cancelled'].includes(status);
    }

    function streamIsOpen() {
      return state.streamSocket && state.streamSocket.readyState === WebSocket.OPEN;
    }

    function closeJobStream() {
      if (!state.streamSocket) return;
      state.streamSocket.onclose = null;
      state.streamSocket.onerror = null;
      state.streamSocket.onmessage = null;
      state.streamSocket.close();
      state.streamSocket = null;
      state.streamJobId = '';
      state.streamApiKey = '';
      state.streamTerminal = false;
    }

    function jobStreamUrl(jobId) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = new URL(`${protocol}//${window.location.host}/research/jobs/${encodeURIComponent(jobId)}/stream`);
      const key = els.apiKey.value.trim();
      if (key) url.searchParams.set('api_key', key);
      return url.toString();
    }

    function mergeSnapshotJob(job) {
      state.jobs = state.jobs.map((item) => (
        item.job_id === job.job_id
          ? { ...item, status: job.status, started_at: job.started_at, finished_at: job.finished_at }
          : item
      ));
      renderJobList();
    }

    function connectJobStream(jobId) {
      const key = els.apiKey.value.trim();
      if (!state.autoRefresh || !jobId || !('WebSocket' in window)) return;
      const sameStream = state.streamJobId === jobId && state.streamApiKey === key;
      if (sameStream && state.streamSocket && state.streamSocket.readyState <= WebSocket.OPEN) return;

      closeJobStream();
      const socket = new WebSocket(jobStreamUrl(jobId));
      state.streamSocket = socket;
      state.streamJobId = jobId;
      state.streamApiKey = key;
      state.streamTerminal = false;

      socket.onmessage = (event) => {
        const payload = JSON.parse(event.data);
        if (payload.type === 'job_snapshot') {
          state.detail = payload.job;
          state.streamTerminal = jobIsTerminal(payload.job.status);
          mergeSnapshotJob(payload.job);
          renderDetail();
          els.connection.textContent = 'streaming';
        }
        if (payload.type === 'error') {
          state.streamTerminal = true;
          setMessage(payload.detail || 'Stream failed.', 'error');
        }
        if (!['job_snapshot', 'error'].includes(payload.type)) {
          appendLiveEvent(payload);
        }
      };
      socket.onerror = () => {
        if (!state.streamTerminal) setMessage('Stream unavailable; using polling fallback.', 'error');
      };
      socket.onclose = () => {
        const wasCurrent = state.streamSocket === socket;
        if (wasCurrent) {
          state.streamSocket = null;
          state.streamJobId = '';
          state.streamApiKey = '';
        }
        if (!state.streamTerminal && state.autoRefresh) scheduleRefresh();
      };
    }

    function renderMarkdown(markdown) {
      const lines = escapeHtml(markdown || '').split('\n');
      let inList = false;
      let inCode = false;
      const html = [];
      for (const line of lines) {
        if (line.trim().startsWith('```')) {
          if (inCode) { html.push('</code></pre>'); inCode = false; }
          else { html.push('<pre><code>'); inCode = true; }
          continue;
        }
        if (inCode) { html.push(`${line}\n`); continue; }
        if (/^###\s+/.test(line)) { if (inList) { html.push('</ul>'); inList = false; } html.push(`<h3>${line.replace(/^###\s+/, '')}</h3>`); continue; }
        if (/^##\s+/.test(line)) { if (inList) { html.push('</ul>'); inList = false; } html.push(`<h2>${line.replace(/^##\s+/, '')}</h2>`); continue; }
        if (/^#\s+/.test(line)) { if (inList) { html.push('</ul>'); inList = false; } html.push(`<h1>${line.replace(/^#\s+/, '')}</h1>`); continue; }
        if (/^-\s+/.test(line)) {
          if (!inList) { html.push('<ul>'); inList = true; }
          html.push(`<li>${line.replace(/^-\s+/, '')}</li>`);
          continue;
        }
        if (inList) { html.push('</ul>'); inList = false; }
        if (!line.trim()) { continue; }
        html.push(`<p>${line}</p>`);
      }
      if (inList) html.push('</ul>');
      if (inCode) html.push('</code></pre>');
      return html.join('');
    }

    function jsonBlock(value) {
      return `<pre>${escapeHtml(JSON.stringify(value ?? {}, null, 2))}</pre>`;
    }

    function renderProgressTimeline(detail) {
      const percent = Number(detail?.progress_percent || 0);
      const steps = detail?.progress_steps || [];
      if (!steps.length) return '';
      return `
        <div id="progress-timeline" class="progress-timeline">
          ${steps.map((step) => `
            <div class="progress-step ${escapeHtml(step.status)}">
              <span>${escapeHtml(step.status)}</span>
              <strong>${escapeHtml(step.label)}</strong>
            </div>`).join('')}
        </div>
        <div class="progress-bar" aria-label="Job progress">
          <div class="progress-bar-fill" style="width: ${Math.max(0, Math.min(100, percent))}%"></div>
        </div>`;
    }

    async function downloadReport(format) {
      if (!state.selectedJobId) return;
      const extension = format === 'html' ? 'html' : 'md';
      const response = await fetch(
        `/research/jobs/${encodeURIComponent(state.selectedJobId)}/report.${extension}`,
        { headers: headers() },
      );
      if (!response.ok) {
        let detail = response.statusText;
        try {
          const payload = await response.json();
          detail = payload.detail || detail;
        } catch (_) {}
        throw new Error(detail);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${state.selectedJobId}.${extension}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }

    function renderOverview(detail) {
      if (!detail) return '<div class="empty">Select a job to inspect.</div>';
      const result = detail.result || {};
      const critique = result.critique || {};
      return `
        <div class="detail-actions">
          <button id="cancel-job" class="btn danger" type="button">Cancel queued job</button>
          <button id="retry-job" class="btn ghost" type="button">Retry failed/cancelled</button>
        </div>
        ${renderProgressTimeline(detail)}
        <div class="overview-grid">
          <div class="info-card"><span>Status</span><strong>${escapeHtml(detail.status)}</strong></div>
          <div class="info-card"><span>Stage</span><strong>${escapeHtml(detail.progress_stage || 'unknown')}</strong></div>
          <div class="info-card"><span>Job ID</span><strong>${escapeHtml(detail.job_id)}</strong></div>
          <div class="info-card"><span>Created</span><strong>${escapeHtml(detail.created_at)}</strong></div>
          <div class="info-card"><span>Started</span><strong>${escapeHtml(detail.started_at || 'not started')}</strong></div>
          <div class="info-card"><span>Finished</span><strong>${escapeHtml(detail.finished_at || 'not finished')}</strong></div>
          <div class="info-card"><span>Runtime</span><strong>${escapeHtml(detail.runtime_seconds || 0)}s</strong></div>
          <div class="info-card"><span>Tools</span><strong>${escapeHtml(detail.tool_call_count || 0)}</strong></div>
          <div class="info-card"><span>LLM Calls</span><strong>${escapeHtml(detail.llm_call_count || 0)}</strong></div>
          <div class="info-card"><span>Iterations</span><strong>${escapeHtml(result.iterations || 0)}</strong></div>
          <div class="info-card"><span>Critic</span><strong>${escapeHtml(critique.passed === false ? 'needs review' : 'passed/unknown')}</strong></div>
          <div class="info-card"><span>Eval Gate</span><strong>docs/evals/default.json<br>--min-score 85 --fail-on-case-failure<br>CI artifact: eval-reports<br>Reports: reports/eval.json, reports/eval.md</strong></div>
          <div class="info-card"><span>Error</span><strong>${escapeHtml(detail.error || 'none')}</strong></div>
        </div>`;
    }

    function renderFindings(result) {
      const findings = result?.findings || [];
      const matrix = result?.competitive_matrix || [];
      if (!findings.length && !matrix.length) return '<div class="empty">No findings yet.</div>';
      return `
        <div class="data-list">
          <h2>Findings</h2>
          ${findings.map((item) => `<p><strong>${escapeHtml(item.title)}</strong><br>${escapeHtml(item.summary)}<br><span class="subtitle">${escapeHtml((item.evidence_ids || []).join(', '))}</span></p>`).join('')}
          <h2>Competitive Matrix</h2>
          ${matrix.map((row) => `<p><strong>${escapeHtml(row.product)}</strong><br>${escapeHtml(row.positioning)}<br><span class="subtitle">${escapeHtml((row.strengths || []).join(', '))}</span></p>`).join('')}
        </div>`;
    }

    function renderEvidenceMeta(label, value) {
      return `<span><strong>${escapeHtml(label)}</strong> ${escapeHtml(value ?? 'unknown')}</span>`;
    }

    function renderEvidencePanel(result) {
      const evidence = result?.evidence_pool || result?.global_evidence_pool || [];
      const validation = result?.url_validation || [];
      if (!evidence.length && !validation.length) return '<div class="empty">No evidence or URL validation yet.</div>';
      return `
        <div class="data-list">
          <h2>Evidence & Sources</h2>
          ${evidence.map((item) => `<article class="evidence-card"><h3>${escapeHtml(item.title || item.id)}</h3><p>${escapeHtml(item.source_url || '')}</p><div class="job-meta">${[
            renderEvidenceMeta('Source type', item.source_type),
            renderEvidenceMeta('Fetch status', item.fetch_status || 'not fetched'),
            renderEvidenceMeta('Section ID', item.section_id),
            renderEvidenceMeta('Citation support', item.citation_support_status),
            renderEvidenceMeta('URL validation', item.url_validation_status),
          ].join('')}</div><p>${escapeHtml(item.snippet || '')}</p></article>`).join('')}
          <h2>URL Validation</h2>
          ${validation.length ? validation.map((item) => `<p><strong>${escapeHtml(item.url || item.source_url || 'url')}</strong><br><span class="subtitle">reachable: ${escapeHtml(item.reachable)} trusted: ${escapeHtml(item.source_trusted)}</span></p>`).join('') : '<p class="subtitle">No URL validation records.</p>'}
        </div>`;
    }

    function renderCitationPanel(result) {
      const citations = result?.citation_support || [];
      if (!citations.length) return '<div class="empty">No citation support records yet.</div>';
      return `
        <div class="data-list">
          <h2>Citation Support</h2>
          ${citations.map((item) => `<p><strong>${escapeHtml(item.support_status || item.status || 'unknown')}</strong><br>${escapeHtml(item.claim || item.text || '')}<br><span class="subtitle">Evidence: ${escapeHtml((item.evidence_ids || []).join(', '))}</span></p>`).join('')}
        </div>`;
    }

    function renderQualityCards(result, detail) {
      const cards = result?.quality_cards || {};
      const runtime = cards.runtime_seconds ?? detail?.runtime_seconds ?? 0;
      const items = [
        ['Section coverage', `${cards.section_coverage_score ?? 0}%`],
        ['Citation support', `${cards.citation_support_score ?? 0}%`],
        ['Source diversity', `${cards.source_diversity_score ?? 0}%`],
        ['Unsupported claims', cards.unsupported_claim_count ?? 0],
        ['URL validation', `${cards.url_validation_rate ?? 0}%`],
        ['Token totals', cards.total_tokens ?? 0],
        ['Runtime', `${runtime}s`],
      ];
      return `<div class="overview-grid">${items.map(([label, value]) => `<div class="info-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}</div>`;
    }

    function renderQualityPanel(result) {
      const detail = state.detail || {};
      const llm = result?.llm_call_log || [];
      const quality = result?.quality || result?.report_quality || {};
      const inputTokens = llm.reduce((total, item) => total + Number(item.input_tokens || 0), 0);
      const outputTokens = llm.reduce((total, item) => total + Number(item.output_tokens || 0), 0);
      const totalTokens = llm.reduce((total, item) => total + Number(item.total_tokens || 0), 0);
      return `
        <div class="data-list">
          <h2>Quality Signals</h2>
          ${renderQualityCards(result, detail)}
          <p><strong>Source candidates</strong><br>${escapeHtml((result?.evidence_pool || []).length)}</p>
          <p><strong>Fetch errors</strong><br>${escapeHtml((result?.evidence_pool || []).filter((item) => item.fetch_error).length)}</p>
          <p><strong>Supported citations</strong><br>${escapeHtml((result?.citation_support || []).filter((item) => item.support_status === 'supported').length)}</p>
          <h2>Token Totals</h2>
          <p><strong>Total</strong><br>${escapeHtml(totalTokens)} tokens</p>
          <p><strong>Input / Output</strong><br>${escapeHtml(inputTokens)} / ${escapeHtml(outputTokens)}</p>
          <h2>Quality Cards</h2>
          ${jsonBlock(quality)}
        </div>`;
    }

    function renderEvalOps() {
      return `
        <div class="data-list">
          <h2>Eval Ops</h2>
          <p><strong>Default case file</strong><br>docs/evals/default.json</p>
          <p><strong>CI gate</strong><br>insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure</p>
          <p><strong>GitHub Actions artifact</strong><br>eval-reports</p>
          <p><strong>Full reports</strong><br>reports/eval.json<br>reports/eval.md</p>
          <p><strong>Summary reports</strong><br>reports/eval-summary.json<br>reports/eval-summary.md</p>
          <p><strong>History reports</strong><br>reports/eval-history.json<br>reports/eval-history.md</p>
          <p><strong>Local summary command</strong><br>python scripts/summarize_eval_report.py reports/eval.json --markdown</p>
          <p><strong>Local history command</strong><br>python scripts/append_eval_history.py --summary reports/eval-summary.json --history reports/eval-history.json --markdown reports/eval-history.md --run-id local --head-sha local --created-at 2026-04-29T00:00:00Z</p>
          <p class="subtitle">Dashboard does not fetch GitHub Actions artifacts automatically. Download the eval-reports artifact from the CI run to inspect generated files.</p>
        </div>`;
    }

    function renderDetail() {
      const detail = state.detail;
      const result = detail?.result || {};
      if (state.activeTab === 'overview') els.reportPanel.innerHTML = renderOverview(detail);
      if (state.activeTab === 'report') {
        const canDownload = result.report_markdown ? '' : 'disabled';
        els.reportPanel.innerHTML = result.report_markdown
          ? `<div class="detail-actions">
              <button id="download-md" class="btn ghost" type="button" ${canDownload}>Download Markdown</button>
              <button id="download-html" class="btn ghost" type="button" ${canDownload}>Download HTML</button>
            </div>
            <article class="markdown">${renderMarkdown(result.report_markdown)}</article>`
          : '<div class="empty">Report will appear after the job succeeds.</div>';
      }
      if (state.activeTab === 'findings') els.reportPanel.innerHTML = renderFindings(result);
      if (state.activeTab === 'evidence') els.reportPanel.innerHTML = renderEvidencePanel(result);
      if (state.activeTab === 'citations') els.reportPanel.innerHTML = renderCitationPanel(result);
      if (state.activeTab === 'quality') els.reportPanel.innerHTML = renderQualityPanel(result);
      if (state.activeTab === 'tools') els.reportPanel.innerHTML = jsonBlock(result.tool_call_log || []);
      if (state.activeTab === 'llm') els.reportPanel.innerHTML = jsonBlock(result.llm_call_log || []);
      if (state.activeTab === 'events') {
        els.reportPanel.innerHTML = state.liveEvents.length
          ? `<div id="live-events" class="live-events">${state.liveEvents.map(renderLiveEvent).join('')}</div>`
          : '<div id="live-events" class="empty">Live execution events will appear here while a job runs.</div>';
      }
      if (state.activeTab === 'eval') els.reportPanel.innerHTML = renderEvalOps();
      if (state.activeTab === 'raw') els.reportPanel.innerHTML = jsonBlock(detail || {});
    }

    async function refresh() {
      try {
        localStorage.setItem('insightgraph.dashboard.apiKey', els.apiKey.value.trim());
        localStorage.setItem('insightgraph.dashboard.preset', els.preset.value);
        localStorage.setItem('insightgraph.dashboard.query', els.query.value);
        const summary = await apiFetch('/research/jobs/summary', { headers: headers() });
        const list = await apiFetch('/research/jobs?limit=20', { headers: headers() });
        renderMetrics(summary);
        state.jobs = list.jobs || [];
        if (!state.selectedJobId && state.jobs[0]) state.selectedJobId = state.jobs[0].job_id;
        renderJobList();
        if (state.selectedJobId) {
          state.detail = await apiFetch(`/research/jobs/${encodeURIComponent(state.selectedJobId)}`, { headers: headers() });
          localStorage.setItem('insightgraph.dashboard.jobId', state.selectedJobId);
          connectJobStream(state.selectedJobId);
        }
        renderDetail();
        els.connection.textContent = 'connected';
        if (!els.message.textContent) setMessage('Ready.', 'ok');
      } catch (error) {
        els.connection.textContent = error.status === 401 ? 'locked' : 'offline';
        setMessage(error.status === 401 ? 'API key required or invalid.' : error.message, 'error');
      } finally {
        scheduleRefresh();
      }
    }

    function scheduleRefresh() {
      clearTimeout(state.timer);
      if (!state.autoRefresh) return;
      const active = ['queued', 'running'].includes(state.detail?.status);
      state.timer = setTimeout(refresh, active && !streamIsOpen() ? 2000 : 8000);
    }

    async function submitJob() {
      const query = els.query.value.trim();
      if (!query) { setMessage('Query is required.', 'error'); return; }
      els.submit.disabled = true;
      setMessage('Submitting job...');
      try {
        const payload = await apiFetch('/research/jobs', {
          method: 'POST',
          headers: headers(true),
          body: JSON.stringify({ query, preset: els.preset.value }),
        });
        state.selectedJobId = payload.job_id;
        closeJobStream();
        state.liveEvents = [];
        setMessage(`Queued ${payload.job_id}.`, 'ok');
        await refresh();
      } catch (error) {
        setMessage(error.status === 401 ? 'API key required or invalid.' : error.message, 'error');
      } finally {
        els.submit.disabled = false;
      }
    }

    async function cancelSelected() {
      if (!state.selectedJobId) return;
      await apiFetch(`/research/jobs/${encodeURIComponent(state.selectedJobId)}/cancel`, {
        method: 'POST',
        headers: headers(),
      });
      setMessage('Job cancelled.', 'ok');
      await refresh();
    }

    async function retrySelected() {
      if (!state.selectedJobId) return;
      const payload = await apiFetch(`/research/jobs/${encodeURIComponent(state.selectedJobId)}/retry`, {
        method: 'POST',
        headers: headers(),
      });
      state.selectedJobId = payload.job_id;
      closeJobStream();
      state.liveEvents = [];
      setMessage(`Retry queued ${payload.job_id}.`, 'ok');
      await refresh();
    }

    els.submit.addEventListener('click', submitJob);
    els.refresh.addEventListener('click', () => { setMessage('Refreshing...'); refresh(); });
    els.autoRefresh.addEventListener('click', () => {
      state.autoRefresh = !state.autoRefresh;
      els.autoRefresh.textContent = state.autoRefresh ? 'auto refresh on' : 'auto refresh off';
      if (!state.autoRefresh) closeJobStream();
      if (state.autoRefresh && state.selectedJobId) connectJobStream(state.selectedJobId);
      scheduleRefresh();
    });
    els.jobList.addEventListener('click', (event) => {
      const card = event.target.closest('[data-job-id]');
      if (!card) return;
      state.selectedJobId = card.dataset.jobId;
      closeJobStream();
      state.liveEvents = [];
      state.detail = null;
      renderJobList();
      renderDetail();
      refresh();
    });
    document.querySelector('.tabs').addEventListener('click', (event) => {
      const tab = event.target.closest('[data-tab]');
      if (!tab) return;
      state.activeTab = tab.dataset.tab;
      document.querySelectorAll('.tab').forEach((item) => item.classList.remove('active'));
      tab.classList.add('active');
      renderDetail();
    });
    els.reportPanel.addEventListener('click', (event) => {
      if (event.target.id === 'cancel-job') cancelSelected().catch((error) => setMessage(error.message, 'error'));
      if (event.target.id === 'retry-job') retrySelected().catch((error) => setMessage(error.message, 'error'));
      if (event.target.id === 'download-md') downloadReport('md').catch((error) => setMessage(error.message, 'error'));
      if (event.target.id === 'download-html') downloadReport('html').catch((error) => setMessage(error.message, 'error'));
    });

    refresh();
  </script>
</body>
</html>
"""


def dashboard_html() -> str:
    return _DASHBOARD_HTML
