# ruff: noqa: E501

_DASHBOARD_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>InsightGraph 仪表盘</title>
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

    .language-switch {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      min-height: 34px;
      padding: 5px 8px 5px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(9, 23, 35, 0.76);
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 700;
    }

    .language-switch select {
      width: auto;
      min-height: 26px;
      padding: 4px 28px 4px 8px;
      border-radius: 999px;
      background: rgba(2, 10, 16, 0.72);
      font-size: 0.78rem;
    }

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
    .btn.small { font-size: 0.75rem; padding: 4px 8px; min-height: auto; }

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
          <div class="eyebrow" data-i18n="brandEyebrow">研究指挥中心</div>
          <h1 data-i18n="brandTitle">InsightGraph 仪表盘</h1>
          <p class="subtitle" data-i18n="brandSubtitle">创建任务、观察执行过程并检查报告。</p>
        </div>
      </div>
      <div class="status-row">
        <label class="language-switch"><span data-i18n="languageLabel">语言</span>
          <select id="language-input" aria-label="Language">
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </label>
        <span class="pill"><span class="dot"></span><span id="connection-state">启动中</span></span>
        <button id="auto-refresh" class="pill" type="button">自动刷新开</button>
      </div>
    </header>

    <div class="grid">
      <section class="panel">
        <div class="panel-head">
          <div>
            <div class="eyebrow" data-i18n="launchEyebrow">启动</div>
            <h2 class="panel-title" data-i18n="researchJobTitle">研究任务</h2>
          </div>
        </div>
        <div class="panel-body form-stack">
          <label><span data-i18n="apiKeyLabel">API 密钥</span>
            <input id="api-key" autocomplete="off" placeholder="可选 Bearer 密钥" data-i18n-placeholder="apiKeyPlaceholder">
          </label>
          <label><span data-i18n="presetLabel">预设</span>
            <select id="preset-input">
              <option value="offline">offline</option>
              <option value="live-llm">live-llm</option>
              <option value="live-research" selected>live-research</option>
            </select>
          </label>
          <label><span data-i18n="intensityLabel">报告强度</span>
            <select id="intensity-input">
              <option value="concise" data-i18n="intensityConcise">精简版</option>
              <option value="standard" selected data-i18n="intensityStandard">标准版</option>
              <option value="deep" data-i18n="intensityDeep">高强度版</option>
            </select>
          </label>
          <label><span data-i18n="queryLabel">查询</span>
            <textarea id="query-input" spellcheck="true"></textarea>
          </label>
          <label><span data-i18n="eventTypeLabel">事件类型过滤</span>
            <input id="event-type-filter" autocomplete="off" placeholder="stage_started, tool_call, report_ready" data-i18n-placeholder="eventTypePlaceholder">
          </label>
          <label><span data-i18n="eventStageLabel">事件阶段过滤</span>
            <input id="event-stage-filter" autocomplete="off" placeholder="planner, collector, analyst" data-i18n-placeholder="eventStagePlaceholder">
          </label>
          <label><span data-i18n="traceIdLabel">Trace ID 过滤</span>
            <input id="trace-id-filter" autocomplete="off" placeholder="trace id" data-i18n-placeholder="traceIdPlaceholder">
          </label>
          <div class="actions">
            <button id="submit-job" class="btn primary" type="button" data-i18n="submitJob">提交任务</button>
            <button id="refresh-now" class="btn ghost" type="button" data-i18n="refresh">刷新</button>
          </div>
          <p id="message" class="message"></p>
        </div>
      </section>

      <main>
        <section class="metric-grid" aria-label="任务指标" data-i18n-aria-label="jobMetricsLabel">
          <div class="metric"><span data-i18n="metricTotal">总数</span><strong id="metric-total">0</strong></div>
          <div class="metric"><span data-i18n="metricQueued">排队中</span><strong id="metric-queued">0</strong></div>
          <div class="metric"><span data-i18n="metricRunning">运行中</span><strong id="metric-running">0</strong></div>
          <div class="metric"><span data-i18n="metricSucceeded">已成功</span><strong id="metric-succeeded">0</strong></div>
          <div class="metric"><span data-i18n="metricFailed">失败</span><strong id="metric-failed">0</strong></div>
          <div class="metric"><span data-i18n="metricActive">活跃</span><strong id="metric-active">0/0</strong></div>
        </section>

        <div class="workspace">
          <section class="panel">
            <div class="panel-head">
              <div>
                <div class="eyebrow" data-i18n="progressEyebrow">进度</div>
                <h2 class="panel-title" data-i18n="recentJobs">最近任务</h2>
              </div>
            </div>
            <div class="panel-body">
              <div id="job-list" class="job-list"></div>
            </div>
          </section>

          <section class="panel">
            <nav class="tabs" aria-label="任务详情标签" data-i18n-aria-label="jobTabsLabel">
              <button class="tab active" data-tab="overview" type="button" data-i18n="tabOverview">概览</button>
              <button class="tab" data-tab="report" type="button" data-i18n="tabReport">报告</button>
              <button class="tab" data-tab="findings" type="button" data-i18n="tabFindings">发现</button>
              <button class="tab" data-tab="evidence" type="button" data-i18n="tabEvidence">证据</button>
              <button class="tab" data-tab="citations" type="button" data-i18n="tabCitations">引用</button>
              <button class="tab" data-tab="quality" type="button" data-i18n="tabQuality">质量</button>
              <button class="tab" data-tab="tools" type="button" data-i18n="tabTools">工具调用</button>
              <button class="tab" data-tab="llm" type="button" data-i18n="tabLlm">LLM 日志</button>
              <button class="tab" data-tab="events" type="button" data-i18n="tabEvents">实时事件</button>
              <button class="tab" data-tab="eval" type="button" data-i18n="tabEval">评测</button>
              <button class="tab" data-tab="raw" type="button" data-i18n="tabRaw">原始 JSON</button>
            </nav>
            <div id="report-panel" class="panel-body tab-panel"></div>
          </section>
        </div>
      </main>
    </div>
  </div>

  <script>
    const LANGUAGE_STORAGE_KEY = 'insightgraph.dashboard.language';
    const I18N = {
      zh: {
        pageTitle: 'InsightGraph 仪表盘',
        brandEyebrow: '研究指挥中心',
        brandTitle: 'InsightGraph 仪表盘',
        brandSubtitle: '创建任务、观察执行过程并检查报告。',
        languageLabel: '语言',
        launchEyebrow: '启动',
        researchJobTitle: '研究任务',
        apiKeyLabel: 'API 密钥',
        apiKeyPlaceholder: '可选 Bearer 密钥',
        presetLabel: '预设',
        intensityLabel: '报告强度',
        intensityConcise: '精简版',
        intensityStandard: '标准版',
        intensityDeep: '高强度版',
        queryLabel: '查询',
        eventTypeLabel: '事件类型过滤',
        eventTypePlaceholder: 'stage_started, tool_call, report_ready',
        eventStageLabel: '事件阶段过滤',
        eventStagePlaceholder: 'planner, collector, analyst',
        traceIdLabel: 'Trace ID 过滤',
        traceIdPlaceholder: 'trace id',
        submitJob: '提交任务',
        refresh: '刷新',
        jobMetricsLabel: '任务指标',
        metricTotal: '总数',
        metricQueued: '排队中',
        metricRunning: '运行中',
        metricSucceeded: '已成功',
        metricFailed: '失败',
        metricActive: '活跃',
        progressEyebrow: '进度',
        recentJobs: '最近任务',
        jobTabsLabel: '任务详情标签',
        tabOverview: '概览',
        tabReport: '报告',
        tabFindings: '发现',
        tabEvidence: '证据',
        tabCitations: '引用',
        tabQuality: '质量',
        tabTools: '工具调用',
        tabLlm: 'LLM 日志',
        tabEvents: '实时事件',
        tabEval: '评测',
        tabRaw: '原始 JSON',
        autoRefreshOn: '自动刷新开',
        autoRefreshOff: '自动刷新关',
        statusBooting: '启动中',
        statusConnected: '已连接',
        statusStreaming: '实时流',
        statusLocked: '已锁定',
        statusOffline: '离线',
        noJobs: '暂无任务。提交一个查询开始。',
        queuePosition: '队列 #{position}',
        delete: '删除',
        received: '已接收',
        streamFailed: '事件流失败。',
        streamFallback: '事件流不可用，正在使用轮询回退。',
        selectJob: '选择一个任务查看详情。',
        cancelQueuedJob: '取消排队任务',
        retryJob: '重试失败/已取消任务',
        progressLabel: '任务进度',
        statusLabel: '状态',
        stageLabel: '阶段',
        jobIdLabel: '任务 ID',
        createdLabel: '创建时间',
        startedLabel: '开始时间',
        finishedLabel: '结束时间',
        runtimeLabel: '运行时长',
        toolsLabel: '工具',
        llmCallsLabel: 'LLM 调用',
        iterationsLabel: '迭代',
        criticLabel: '评审',
        evalGateLabel: '评测门禁',
        errorLabel: '错误',
        notStarted: '未开始',
        notFinished: '未完成',
        seconds: '{value} 秒',
        needsReview: '需要复核',
        passedUnknown: '通过/未知',
        none: '无',
        unknown: '未知',
        statusQueued: '排队中',
        statusRunning: '运行中',
        statusSucceeded: '已成功',
        statusFailed: '失败',
        statusCancelled: '已取消',
        stageCompleted: '已完成',
        stageFailed: '失败',
        stageCancelled: '已取消',
        stepPending: '待处理',
        stepActive: '进行中',
        stepCompleted: '已完成',
        stepFailed: '失败',
        stepSkipped: '已跳过',
        planner: '规划',
        collector: '采集',
        analyst: '分析',
        critic: '评审',
        reporter: '报告',
        downloadMarkdown: '下载 Markdown',
        downloadHtml: '下载 HTML',
        reportPending: '任务成功后会在这里显示报告。',
        liveEventsPending: '任务运行时，实时执行事件会显示在这里。',
        findingsTitle: '发现',
        competitiveMatrix: '竞争矩阵',
        noFindings: '暂无发现。',
        evidenceSources: '证据与来源',
        sourceType: '来源类型',
        fetchStatus: '抓取状态',
        sectionId: '章节 ID',
        citationSupport: '引用支撑',
        urlValidation: 'URL 验证',
        noEvidence: '暂无证据或 URL 验证记录。',
        urlValidationTitle: 'URL 验证',
        noUrlValidation: '暂无 URL 验证记录。',
        reachable: '可访问',
        trusted: '可信',
        notFetched: '未抓取',
        citationsTitle: '引用支撑',
        noCitations: '暂无引用支撑记录。',
        evidenceLabel: '证据',
        qualitySignals: '质量信号',
        sectionCoverage: '章节覆盖',
        sourceDiversity: '来源多样性',
        reportQualityScore: '报告质量评分',
        reportIntensity: '报告强度',
        unsupportedClaims: '未支撑声明',
        tokenTotals: 'Token 总计',
        sourceCandidates: '候选来源',
        fetchErrors: '抓取错误',
        supportedCitations: '已支撑引用',
        total: '总计',
        inputOutput: '输入 / 输出',
        qualityCards: '质量卡片',
        tokens: 'tokens',
        runtimeDiagnostics: '运行诊断',
        runtimeDiagnosticsEnglish: 'Runtime Diagnostics',
        searchProvider: '搜索提供方',
        searchLimit: '搜索数量',
        webSearchCalls: '网页搜索调用',
        successfulWebSearchCalls: '成功网页搜索',
        llmConfigured: 'LLM 已配置',
        successfulLlmCalls: '成功 LLM 调用',
        verifiedEvidence: '已验证证据',
        collectionStopReason: '采集停止原因',
        yes: '是',
        no: '否',
        evalOps: '评测运维',
        defaultCaseFile: '默认用例文件',
        ciGate: 'CI 门禁',
        githubActionsArtifact: 'GitHub Actions 产物',
        fullReports: '完整报告',
        summaryReports: '摘要报告',
        historyReports: '历史报告',
        localSummaryCommand: '本地摘要命令',
        localHistoryCommand: '本地历史命令',
        evalOpsNote: 'Dashboard 不会自动拉取 GitHub Actions 产物。请从 CI run 下载 eval-reports 产物查看生成文件。',
        ready: '就绪。',
        refreshing: '正在刷新...',
        submittingJob: '正在提交任务...',
        queryRequired: '查询不能为空。',
        requestFailed: '请求失败',
        apiKeyInvalid: 'API 密钥缺失或无效。',
        queuedJob: '已排队 {jobId}。',
        cancelledJob: '任务已取消。',
        retryQueued: '已排队重试任务 {jobId}。',
        deleteConfirm: '删除这个任务？',
        deletedJob: '已删除任务 {jobId}',
        deleteFailed: '删除失败',
        defaultQuery: '比较 Cursor、OpenCode 和 GitHub Copilot',
      },
      en: {
        pageTitle: 'InsightGraph Dashboard',
        brandEyebrow: 'Research Command Center',
        brandTitle: 'InsightGraph Dashboard',
        brandSubtitle: 'Create jobs, watch execution, and inspect reports.',
        languageLabel: 'Language',
        launchEyebrow: 'Launch',
        researchJobTitle: 'Research job',
        apiKeyLabel: 'API key',
        apiKeyPlaceholder: 'Optional bearer key',
        presetLabel: 'Preset',
        intensityLabel: 'Report intensity',
        intensityConcise: 'Concise',
        intensityStandard: 'Standard',
        intensityDeep: 'Deep',
        queryLabel: 'Query',
        eventTypeLabel: 'Event type filter',
        eventTypePlaceholder: 'stage_started, tool_call, report_ready',
        eventStageLabel: 'Event stage filter',
        eventStagePlaceholder: 'planner, collector, analyst',
        traceIdLabel: 'Trace ID filter',
        traceIdPlaceholder: 'trace id',
        submitJob: 'Submit job',
        refresh: 'Refresh',
        jobMetricsLabel: 'Job metrics',
        metricTotal: 'Total',
        metricQueued: 'Queued',
        metricRunning: 'Running',
        metricSucceeded: 'Succeeded',
        metricFailed: 'Failed',
        metricActive: 'Active',
        progressEyebrow: 'Progress',
        recentJobs: 'Recent jobs',
        jobTabsLabel: 'Job detail tabs',
        tabOverview: 'Overview',
        tabReport: 'Report',
        tabFindings: 'Findings',
        tabEvidence: 'Evidence',
        tabCitations: 'Citations',
        tabQuality: 'Quality',
        tabTools: 'Tool Calls',
        tabLlm: 'LLM Log',
        tabEvents: 'Live Events',
        tabEval: 'Eval',
        tabRaw: 'Raw JSON',
        autoRefreshOn: 'auto refresh on',
        autoRefreshOff: 'auto refresh off',
        statusBooting: 'booting',
        statusConnected: 'connected',
        statusStreaming: 'streaming',
        statusLocked: 'locked',
        statusOffline: 'offline',
        noJobs: 'No jobs yet. Submit a query to start.',
        queuePosition: 'Queue #{position}',
        delete: 'Delete',
        received: 'received',
        streamFailed: 'Stream failed.',
        streamFallback: 'Stream unavailable; using polling fallback.',
        selectJob: 'Select a job to inspect.',
        cancelQueuedJob: 'Cancel queued job',
        retryJob: 'Retry failed/cancelled',
        progressLabel: 'Job progress',
        statusLabel: 'Status',
        stageLabel: 'Stage',
        jobIdLabel: 'Job ID',
        createdLabel: 'Created',
        startedLabel: 'Started',
        finishedLabel: 'Finished',
        runtimeLabel: 'Runtime',
        toolsLabel: 'Tools',
        llmCallsLabel: 'LLM Calls',
        iterationsLabel: 'Iterations',
        criticLabel: 'Critic',
        evalGateLabel: 'Eval Gate',
        errorLabel: 'Error',
        notStarted: 'not started',
        notFinished: 'not finished',
        seconds: '{value}s',
        needsReview: 'needs review',
        passedUnknown: 'passed/unknown',
        none: 'none',
        unknown: 'unknown',
        statusQueued: 'queued',
        statusRunning: 'running',
        statusSucceeded: 'succeeded',
        statusFailed: 'failed',
        statusCancelled: 'cancelled',
        stageCompleted: 'completed',
        stageFailed: 'failed',
        stageCancelled: 'cancelled',
        stepPending: 'pending',
        stepActive: 'active',
        stepCompleted: 'completed',
        stepFailed: 'failed',
        stepSkipped: 'skipped',
        planner: 'Planner',
        collector: 'Collector',
        analyst: 'Analyst',
        critic: 'Critic',
        reporter: 'Reporter',
        downloadMarkdown: 'Download Markdown',
        downloadHtml: 'Download HTML',
        reportPending: 'Report will appear after the job succeeds.',
        liveEventsPending: 'Live execution events will appear here while a job runs.',
        findingsTitle: 'Findings',
        competitiveMatrix: 'Competitive Matrix',
        noFindings: 'No findings yet.',
        evidenceSources: 'Evidence & Sources',
        sourceType: 'Source type',
        fetchStatus: 'Fetch status',
        sectionId: 'Section ID',
        citationSupport: 'Citation support',
        urlValidation: 'URL validation',
        noEvidence: 'No evidence or URL validation yet.',
        urlValidationTitle: 'URL Validation',
        noUrlValidation: 'No URL validation records.',
        reachable: 'reachable',
        trusted: 'trusted',
        notFetched: 'not fetched',
        citationsTitle: 'Citation Support',
        noCitations: 'No citation support records yet.',
        evidenceLabel: 'Evidence',
        qualitySignals: 'Quality Signals',
        sectionCoverage: 'Section coverage',
        sourceDiversity: 'Source diversity',
        reportQualityScore: 'Report quality score',
        reportIntensity: 'Report intensity',
        unsupportedClaims: 'Unsupported claims',
        tokenTotals: 'Token Totals',
        tokenTotalsLegacy: 'Token totals',
        sourceCandidates: 'Source candidates',
        fetchErrors: 'Fetch errors',
        supportedCitations: 'Supported citations',
        total: 'Total',
        inputOutput: 'Input / Output',
        qualityCards: 'Quality Cards',
        tokens: 'tokens',
        runtimeDiagnostics: 'Runtime Diagnostics',
        runtimeDiagnosticsEnglish: 'Runtime Diagnostics',
        searchProvider: 'Search provider',
        searchLimit: 'Search limit',
        webSearchCalls: 'Web search calls',
        successfulWebSearchCalls: 'Successful web searches',
        llmConfigured: 'LLM configured',
        successfulLlmCalls: 'Successful LLM calls',
        verifiedEvidence: 'Verified evidence',
        collectionStopReason: 'Collection stop reason',
        yes: 'yes',
        no: 'no',
        evalOps: 'Eval Ops',
        defaultCaseFile: 'Default case file',
        ciGate: 'CI gate',
        githubActionsArtifact: 'GitHub Actions artifact',
        fullReports: 'Full reports',
        summaryReports: 'Summary reports',
        historyReports: 'History reports',
        localSummaryCommand: 'Local summary command',
        localHistoryCommand: 'Local history command',
        evalOpsNote: 'Dashboard does not fetch GitHub Actions artifacts automatically. Download the eval-reports artifact from the CI run to inspect generated files.',
        ready: 'Ready.',
        refreshing: 'Refreshing...',
        submittingJob: 'Submitting job...',
        queryRequired: 'Query is required.',
        requestFailed: 'Request failed',
        apiKeyInvalid: 'API key required or invalid.',
        queuedJob: 'Queued {jobId}.',
        cancelledJob: 'Job cancelled.',
        retryQueued: 'Retry queued {jobId}.',
        deleteConfirm: 'Delete this job?',
        deletedJob: 'Deleted job {jobId}',
        deleteFailed: 'Delete failed',
        defaultQuery: 'Compare Cursor, OpenCode, and GitHub Copilot',
      },
    };

    function normalizeLanguage(value) {
      return value === 'en' ? 'en' : 'zh';
    }

    function t(key, values = {}) {
      const dictionary = I18N[state.language] || I18N.zh;
      let text = dictionary[key] || I18N.en[key] || key;
      for (const [name, value] of Object.entries(values)) {
        text = text.replaceAll(`{${name}}`, String(value));
      }
      return text;
    }

    function statusText(status) {
      return {
        queued: t('statusQueued'),
        running: t('statusRunning'),
        succeeded: t('statusSucceeded'),
        failed: t('statusFailed'),
        cancelled: t('statusCancelled'),
      }[status] || status || t('unknown');
    }

    function stepStatusText(status) {
      return {
        pending: t('stepPending'),
        active: t('stepActive'),
        completed: t('stepCompleted'),
        failed: t('stepFailed'),
        skipped: t('stepSkipped'),
      }[status] || status || t('unknown');
    }

    function stageText(stage) {
      return {
        planner: t('planner'),
        collector: t('collector'),
        analyst: t('analyst'),
        critic: t('critic'),
        reporter: t('reporter'),
        completed: t('stageCompleted'),
        failed: t('stageFailed'),
        cancelled: t('stageCancelled'),
        queued: t('statusQueued'),
      }[stage] || stage || t('unknown');
    }

    const state = {
      jobs: [],
      detail: null,
      selectedJobId: localStorage.getItem('insightgraph.dashboard.jobId') || '',
      language: normalizeLanguage(localStorage.getItem(LANGUAGE_STORAGE_KEY)),
      connectionStateKey: 'statusBooting',
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
      language: document.getElementById('language-input'),
      apiKey: document.getElementById('api-key'),
      preset: document.getElementById('preset-input'),
      intensity: document.getElementById('intensity-input'),
      query: document.getElementById('query-input'),
      eventTypeFilter: document.getElementById('event-type-filter'),
      eventStageFilter: document.getElementById('event-stage-filter'),
      traceIdFilter: document.getElementById('trace-id-filter'),
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

    els.language.value = state.language;
    const savedQuery = localStorage.getItem('insightgraph.dashboard.query');
    els.apiKey.value = localStorage.getItem('insightgraph.dashboard.apiKey') || '';
    els.query.value = savedQuery || t('defaultQuery');
    els.preset.value = localStorage.getItem('insightgraph.dashboard.preset') || 'offline';
    els.intensity.value = localStorage.getItem('insightgraph.dashboard.intensity') || 'standard';

    function applyLanguage() {
      document.documentElement.lang = state.language === 'zh' ? 'zh-CN' : 'en';
      document.title = t('pageTitle');
      document.querySelectorAll('[data-i18n]').forEach((item) => {
        item.textContent = t(item.dataset.i18n);
      });
      document.querySelectorAll('[data-i18n-placeholder]').forEach((item) => {
        item.setAttribute('placeholder', t(item.dataset.i18nPlaceholder));
      });
      document.querySelectorAll('[data-i18n-aria-label]').forEach((item) => {
        item.setAttribute('aria-label', t(item.dataset.i18nAriaLabel));
      });
      els.autoRefresh.textContent = state.autoRefresh ? t('autoRefreshOn') : t('autoRefreshOff');
      els.connection.textContent = t(state.connectionStateKey);
      if (!els.message.textContent) setMessage(t('ready'), 'ok');
      renderJobList();
      renderDetail();
    }

    function setConnection(key) {
      state.connectionStateKey = key;
      els.connection.textContent = t(key);
    }

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
        const error = new Error(detail || t('requestFailed'));
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

    function deleteJob(jobId) {
      const key = els.apiKey.value.trim();
      const url = '/research/jobs/' + encodeURIComponent(jobId);
      return fetch(url, { method: 'DELETE', headers: headers() }).then((response) => {
        if (!response.ok) return response.json().then((data) => { throw new Error(data.detail || t('deleteFailed')); });
        return response.json();
      });
    }

    function renderJobList() {
      if (!state.jobs.length) {
        els.jobList.innerHTML = `<div class="empty">${escapeHtml(t('noJobs'))}</div>`;
        return;
      }
      els.jobList.innerHTML = state.jobs.map((job) => {
        const active = job.job_id === state.selectedJobId ? ' active' : '';
        const queue = job.queue_position ? t('queuePosition', { position: job.queue_position }) : job.preset;
        const isTerminal = jobIsTerminal(job.status);
        const deleteBtn = isTerminal ? `<button class="btn danger small" data-delete-job-id="${escapeHtml(job.job_id)}" type="button">${escapeHtml(t('delete'))}</button>` : '';
        return `
          <div class="job-card${active}" data-job-id="${escapeHtml(job.job_id)}">
            <span class="${statusClass(job.status)}">${escapeHtml(statusText(job.status))}</span>
            <h3>${escapeHtml(job.query || job.job_id)}</h3>
            <div class="job-meta">
              <span>${escapeHtml(queue)}</span>
              <span>${escapeHtml(job.created_at || '')}</span>
            </div>
            ${deleteBtn}
          </div>`;
      }).join('');
    }

    function renderLiveEvent(event) {
      const stage = event.stage ? ` - ${event.stage}` : '';
      const record = event.record || {};
      const summary = record.tool_name || record.model || record.stage || event.detail || t('received');
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

    function appendEventFilters(url) {
      const eventType = els.eventTypeFilter.value.trim();
      const eventStage = els.eventStageFilter.value.trim();
      const traceId = els.traceIdFilter.value.trim();
      if (eventType) url.searchParams.set('event_type', eventType);
      if (eventStage) url.searchParams.set('event_stage', eventStage);
      if (traceId) url.searchParams.set('trace_id', traceId);
      return url;
    }

    function jobStreamUrl(jobId) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = new URL(`${protocol}//${window.location.host}/research/jobs/${encodeURIComponent(jobId)}/stream`);
      const key = els.apiKey.value.trim();
      if (key) url.searchParams.set('api_key', key);
      return appendEventFilters(url).toString();
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
          setConnection('statusStreaming');
        }
        if (payload.type === 'error') {
          state.streamTerminal = true;
          setMessage(payload.detail || t('streamFailed'), 'error');
        }
        if (!['job_snapshot', 'error'].includes(payload.type)) {
          appendLiveEvent(payload);
        }
      };
      socket.onerror = () => {
        if (!state.streamTerminal) setMessage(t('streamFallback'), 'error');
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
              <span>${escapeHtml(stepStatusText(step.status))}</span>
              <strong>${escapeHtml(stageText(step.id) || step.label)}</strong>
            </div>`).join('')}
        </div>
        <div class="progress-bar" aria-label="${escapeHtml(t('progressLabel'))}">
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
      if (!detail) return `<div class="empty">${escapeHtml(t('selectJob'))}</div>`;
      const result = detail.result || {};
      const critique = result.critique || {};
      return `
        <div class="detail-actions">
          <button id="cancel-job" class="btn danger" type="button">${escapeHtml(t('cancelQueuedJob'))}</button>
          <button id="retry-job" class="btn ghost" type="button">${escapeHtml(t('retryJob'))}</button>
        </div>
        ${renderProgressTimeline(detail)}
        <div class="overview-grid">
          <div class="info-card"><span>${escapeHtml(t('statusLabel'))}</span><strong>${escapeHtml(statusText(detail.status))}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('stageLabel'))}</span><strong>${escapeHtml(stageText(detail.progress_stage))}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('jobIdLabel'))}</span><strong>${escapeHtml(detail.job_id)}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('createdLabel'))}</span><strong>${escapeHtml(detail.created_at)}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('startedLabel'))}</span><strong>${escapeHtml(detail.started_at || t('notStarted'))}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('finishedLabel'))}</span><strong>${escapeHtml(detail.finished_at || t('notFinished'))}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('runtimeLabel'))}</span><strong>${escapeHtml(t('seconds', { value: detail.runtime_seconds || 0 }))}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('toolsLabel'))}</span><strong>${escapeHtml(detail.tool_call_count || 0)}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('llmCallsLabel'))}</span><strong>${escapeHtml(detail.llm_call_count || 0)}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('iterationsLabel'))}</span><strong>${escapeHtml(result.iterations || 0)}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('criticLabel'))}</span><strong>${escapeHtml(critique.passed === false ? t('needsReview') : t('passedUnknown'))}</strong></div>
          <div class="info-card"><span>${escapeHtml(t('evalGateLabel'))}</span><strong>docs/evals/default.json<br>--min-score 85 --fail-on-case-failure<br>CI artifact: eval-reports<br>Reports: reports/eval.json, reports/eval.md</strong></div>
          <div class="info-card"><span>${escapeHtml(t('errorLabel'))}</span><strong>${escapeHtml(detail.error || t('none'))}</strong></div>
        </div>`;
    }

    function renderFindings(result) {
      const findings = result?.findings || [];
      const matrix = result?.competitive_matrix || [];
      if (!findings.length && !matrix.length) return `<div class="empty">${escapeHtml(t('noFindings'))}</div>`;
      return `
        <div class="data-list">
          <h2>${escapeHtml(t('findingsTitle'))}</h2>
          ${findings.map((item) => `<p><strong>${escapeHtml(item.title)}</strong><br>${escapeHtml(item.summary)}<br><span class="subtitle">${escapeHtml((item.evidence_ids || []).join(', '))}</span></p>`).join('')}
          <h2>${escapeHtml(t('competitiveMatrix'))}</h2>
          ${matrix.map((row) => `<p><strong>${escapeHtml(row.product)}</strong><br>${escapeHtml(row.positioning)}<br><span class="subtitle">${escapeHtml((row.strengths || []).join(', '))}</span></p>`).join('')}
        </div>`;
    }

    function renderEvidenceMeta(label, value) {
      return `<span><strong>${escapeHtml(label)}</strong> ${escapeHtml(value ?? 'unknown')}</span>`;
    }

    function renderEvidencePanel(result) {
      const evidence = result?.evidence_pool || result?.global_evidence_pool || [];
      const validation = result?.url_validation || [];
      if (!evidence.length && !validation.length) return `<div class="empty">${escapeHtml(t('noEvidence'))}</div>`;
      return `
        <div class="data-list">
          <h2>${escapeHtml(t('evidenceSources'))}</h2>
          ${evidence.map((item) => `<article class="evidence-card"><h3>${escapeHtml(item.title || item.id)}</h3><p>${escapeHtml(item.source_url || '')}</p><div class="job-meta">${[
            renderEvidenceMeta(t('sourceType'), item.source_type),
            renderEvidenceMeta(t('fetchStatus'), item.fetch_status || t('notFetched')),
            renderEvidenceMeta(t('sectionId'), item.section_id),
            renderEvidenceMeta(t('citationSupport'), item.citation_support_status),
            renderEvidenceMeta(t('urlValidation'), item.url_validation_status),
          ].join('')}</div><p>${escapeHtml(item.snippet || '')}</p></article>`).join('')}
          <h2>${escapeHtml(t('urlValidationTitle'))}</h2>
          ${validation.length ? validation.map((item) => `<p><strong>${escapeHtml(item.url || item.source_url || 'url')}</strong><br><span class="subtitle">${escapeHtml(t('reachable'))}: ${escapeHtml(item.reachable)} ${escapeHtml(t('trusted'))}: ${escapeHtml(item.source_trusted)}</span></p>`).join('') : `<p class="subtitle">${escapeHtml(t('noUrlValidation'))}</p>`}
        </div>`;
    }

    function renderCitationPanel(result) {
      const citations = result?.citation_support || [];
      if (!citations.length) return `<div class="empty">${escapeHtml(t('noCitations'))}</div>`;
      return `
        <div class="data-list">
          <h2>${escapeHtml(t('citationsTitle'))}</h2>
          ${citations.map((item) => `<p><strong>${escapeHtml(item.support_status || item.status || t('unknown'))}</strong><br>${escapeHtml(item.claim || item.text || '')}<br><span class="subtitle">${escapeHtml(t('evidenceLabel'))}: ${escapeHtml((item.evidence_ids || []).join(', '))}</span></p>`).join('')}
        </div>`;
    }

    function renderQualityCards(result, detail) {
      const cards = result?.quality_cards || {};
      const review = result?.report_quality_review || {};
      const runtime = cards.runtime_seconds ?? detail?.runtime_seconds ?? 0;
      const items = [
        [t('sectionCoverage'), `${cards.section_coverage_score ?? 0}%`],
        [t('citationSupport'), `${cards.citation_support_score ?? 0}%`],
        [t('sourceDiversity'), `${cards.source_diversity_score ?? 0}%`],
        [t('reportQualityScore'), `${review.score ?? 0}/100`],
        [t('reportIntensity'), review.intensity_label || review.intensity || 'standard'],
        [t('unsupportedClaims'), cards.unsupported_claim_count ?? 0],
        [t('urlValidation'), `${cards.url_validation_rate ?? 0}%`],
        [t('tokenTotals'), cards.total_tokens ?? 0],
        [t('runtimeLabel'), t('seconds', { value: runtime })],
      ];
      return `<div class="overview-grid">${items.map(([label, value]) => `<div class="info-card"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join('')}</div>`;
    }

    function renderRuntimeDiagnostics(result) {
      const diagnostics = result?.runtime_diagnostics || {};
      const items = [
        [t('searchProvider'), diagnostics.search_provider || t('unknown')],
        [t('searchLimit'), diagnostics.search_limit ?? t('unknown')],
        [t('webSearchCalls'), diagnostics.web_search_call_count ?? 0],
        [t('successfulWebSearchCalls'), diagnostics.successful_web_search_call_count ?? 0],
        [t('llmConfigured'), diagnostics.llm_configured ? t('yes') : t('no')],
        [t('llmCallsLabel'), diagnostics.llm_call_count ?? 0],
        [t('successfulLlmCalls'), diagnostics.successful_llm_call_count ?? 0],
        [t('verifiedEvidence'), `${diagnostics.verified_evidence_count ?? 0} / ${diagnostics.evidence_count ?? 0}`],
        [t('collectionStopReason'), diagnostics.collection_stop_reason || t('unknown')],
        [t('reportIntensity'), diagnostics.report_intensity || t('unknown')],
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
          <h2>${escapeHtml(t('qualitySignals'))}</h2>
          ${renderQualityCards(result, detail)}
          <p><strong>${escapeHtml(t('sourceCandidates'))}</strong><br>${escapeHtml((result?.evidence_pool || []).length)}</p>
          <p><strong>${escapeHtml(t('fetchErrors'))}</strong><br>${escapeHtml((result?.evidence_pool || []).filter((item) => item.fetch_error).length)}</p>
          <p><strong>${escapeHtml(t('supportedCitations'))}</strong><br>${escapeHtml((result?.citation_support || []).filter((item) => item.support_status === 'supported').length)}</p>
          <h2>${escapeHtml(t('tokenTotals'))}</h2>
          <p><strong>${escapeHtml(t('total'))}</strong><br>${escapeHtml(totalTokens)} ${escapeHtml(t('tokens'))}</p>
          <p><strong>${escapeHtml(t('inputOutput'))}</strong><br>${escapeHtml(inputTokens)} / ${escapeHtml(outputTokens)}</p>
          <h2>${escapeHtml(t('runtimeDiagnostics'))}</h2>
          <span class="subtitle">${escapeHtml(t('runtimeDiagnosticsEnglish'))}</span>
          ${renderRuntimeDiagnostics(result)}
          <h2>${escapeHtml(t('qualityCards'))}</h2>
          ${jsonBlock(quality)}
        </div>`;
    }

    function renderEvalOps() {
      return `
        <div class="data-list">
          <h2>${escapeHtml(t('evalOps'))}</h2>
          <p><strong>${escapeHtml(t('defaultCaseFile'))}</strong><br>docs/evals/default.json</p>
          <p><strong>${escapeHtml(t('ciGate'))}</strong><br>insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure</p>
          <p><strong>${escapeHtml(t('githubActionsArtifact'))}</strong><br>eval-reports</p>
          <p><strong>${escapeHtml(t('fullReports'))}</strong><br>reports/eval.json<br>reports/eval.md</p>
          <p><strong>${escapeHtml(t('summaryReports'))}</strong><br>reports/eval-summary.json<br>reports/eval-summary.md</p>
          <p><strong>${escapeHtml(t('historyReports'))}</strong><br>reports/eval-history.json<br>reports/eval-history.md</p>
          <p><strong>${escapeHtml(t('localSummaryCommand'))}</strong><br>python scripts/summarize_eval_report.py reports/eval.json --markdown</p>
          <p><strong>${escapeHtml(t('localHistoryCommand'))}</strong><br>python scripts/append_eval_history.py --summary reports/eval-summary.json --history reports/eval-history.json --markdown reports/eval-history.md --run-id local --head-sha local --created-at 2026-04-29T00:00:00Z</p>
          <p class="subtitle">${escapeHtml(t('evalOpsNote'))}</p>
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
              <button id="download-md" class="btn ghost" type="button" ${canDownload}>${escapeHtml(t('downloadMarkdown'))}</button>
              <button id="download-html" class="btn ghost" type="button" ${canDownload}>${escapeHtml(t('downloadHtml'))}</button>
            </div>
            <article class="markdown">${renderMarkdown(result.report_markdown)}</article>`
          : `<div class="empty">${escapeHtml(t('reportPending'))}</div>`;
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
          : `<div id="live-events" class="empty">${escapeHtml(t('liveEventsPending'))}</div>`;
      }
      if (state.activeTab === 'eval') els.reportPanel.innerHTML = renderEvalOps();
      if (state.activeTab === 'raw') els.reportPanel.innerHTML = jsonBlock(detail || {});
    }

    async function refresh() {
      try {
        localStorage.setItem('insightgraph.dashboard.apiKey', els.apiKey.value.trim());
        localStorage.setItem('insightgraph.dashboard.preset', els.preset.value);
        localStorage.setItem('insightgraph.dashboard.intensity', els.intensity.value);
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
        setConnection('statusConnected');
        if (!els.message.textContent) setMessage(t('ready'), 'ok');
      } catch (error) {
        setConnection(error.status === 401 ? 'statusLocked' : 'statusOffline');
        setMessage(error.status === 401 ? t('apiKeyInvalid') : error.message, 'error');
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
      if (!query) { setMessage(t('queryRequired'), 'error'); return; }
      els.submit.disabled = true;
      setMessage(t('submittingJob'));
      try {
        const payload = await apiFetch('/research/jobs', {
          method: 'POST',
          headers: headers(true),
          body: JSON.stringify({
            query,
            preset: els.preset.value,
            report_intensity: els.intensity.value,
          }),
        });
        state.selectedJobId = payload.job_id;
        closeJobStream();
        state.liveEvents = [];
        setMessage(t('queuedJob', { jobId: payload.job_id }), 'ok');
        await refresh();
      } catch (error) {
        setMessage(error.status === 401 ? t('apiKeyInvalid') : error.message, 'error');
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
      setMessage(t('cancelledJob'), 'ok');
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
      setMessage(t('retryQueued', { jobId: payload.job_id }), 'ok');
      await refresh();
    }

    els.submit.addEventListener('click', submitJob);
    els.refresh.addEventListener('click', () => { setMessage(t('refreshing')); refresh(); });
    els.autoRefresh.addEventListener('click', () => {
      state.autoRefresh = !state.autoRefresh;
      els.autoRefresh.textContent = state.autoRefresh ? t('autoRefreshOn') : t('autoRefreshOff');
      if (!state.autoRefresh) closeJobStream();
      if (state.autoRefresh && state.selectedJobId) connectJobStream(state.selectedJobId);
      scheduleRefresh();
    });
    els.language.addEventListener('change', () => {
      state.language = normalizeLanguage(els.language.value);
      localStorage.setItem(LANGUAGE_STORAGE_KEY, state.language);
      applyLanguage();
    });
    els.jobList.addEventListener('click', async (event) => {
      const deleteBtn = event.target.closest('[data-delete-job-id]');
      if (deleteBtn) {
        event.stopPropagation();
        const jobId = deleteBtn.dataset.deleteJobId;
        if (confirm(t('deleteConfirm'))) {
          try {
            await deleteJob(jobId);
            if (state.selectedJobId === jobId) {
              state.selectedJobId = null;
              state.detail = null;
            }
            setMessage(t('deletedJob', { jobId }), 'ok');
            await refresh();
          } catch (error) {
            setMessage(error.message, 'error');
          }
        }
        return;
      }
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

    applyLanguage();
    refresh();
  </script>
</body>
</html>
"""


def dashboard_html() -> str:
    return _DASHBOARD_HTML
