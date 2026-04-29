# InsightGraph

基于 LangGraph 的多智能体商业情报研究引擎，面向竞品分析、技术趋势、市场机会识别与产业洞察等场景的深度报告自动生成。支持任务分解、工具调用、Critic 闭环纠错、证据溯源与引用校验，产出带可验证来源的结构化研究报告。

> 当前仓库处于 MVP 架构落地阶段：优先实现可测试的 LangGraph 多智能体研究流骨架，再逐步接入真实搜索、持久化、向量记忆与 Web API。

## 当前 MVP 已实现

| 能力 | 状态 |
|------|------|
| LangGraph 工作流 | 已实现 Planner → Collector → Analyst → Critic → Reporter 的可运行状态图 |
| CLI | 已实现 `insight-graph research "..."` / `python -m insight_graph.cli research "..."` / `insight-graph-eval` |
| API | 已实现 `GET /health`、同步 `POST /research`、异步 research jobs、`GET /dashboard`、手动 retry、可选 JSON/SQLite job metadata storage |
| 证据链 | 已实现 deterministic `mock_search`、direct URL `fetch_url`、默认 mock `web_search -> pre_fetch -> fetch_url`，并支持 opt-in DuckDuckGo provider |
| GitHub evidence | 默认 deterministic/offline；可 opt-in live GitHub repository search provider |
| 文档 evidence | 支持 cwd 内 TXT/Markdown/HTML/PDF、本地 chunking、JSON lexical query ranking |
| 文件工具 | 支持 cwd 内只读 `read_file` / `list_directory` 和 create-only `write_file` |
| Analyst / Reporter | 默认 deterministic/offline；可 opt-in OpenAI-compatible LLM |
| Critic | 已实现证据数量、分析结果、citation support 检查 |
| 可观测性 | 已记录 tool call log、LLM metadata log、token usage 和 LLM router decision metadata |
| Eval Bench | 已实现 deterministic offline eval scoring，用于结构质量和回归检查 |
| 测试 | 已实现 pytest 覆盖 state、agents、tools、graph、CLI、API、scripts |

MVP 默认使用 deterministic/offline 行为，适合本地开发、测试和 CI。真实搜索、真实 LLM、GitHub API 等能力都必须显式 opt-in。

## 文档入口

- [配置说明](docs/configuration.md)：搜索 provider、GitHub provider、document reader、LLM preset、observability、后续配置项。
- [架构蓝图](docs/architecture.md)：目标项目结构、核心特性、技术架构、执行流程、agent 协作、工具和证据链。
- [脚本说明](docs/scripts.md)：run、benchmark、validator、LLM metadata log 脚本用法。
- [MVP Demo](docs/demo.md)：展示报告、offline/live LLM demo 命令和 observability 演示。
- [部署说明](docs/deployment.md)：本地/API demo server、SQLite jobs、live LLM 和 systemd 部署边界。
- [Research jobs API](docs/research-jobs-api.md)：异步 research jobs 端点、状态、限制、取消和持久化行为。
- [Research job repository contract](docs/research-job-repository-contract.md)：research jobs 稳定契约、内存实现细节和未来存储后端要求。
- [Roadmap](docs/roadmap.md)：近期工程优先级和延后事项。
- [Caveman project skills](docs/skills/caveman-applied-skills.md)：当前项目已应用的本地 OpenCode/Caveman 规则。
- [Changelog](CHANGELOG.md)：版本变更记录。

## 快速开始（当前 MVP）

### 环境要求

- Python 3.11+
- pip

### 启动步骤

```bash
# 1. 克隆并配置
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph

# 2. 安装依赖
python -m pip install -e ".[dev]"

# 3. 运行测试
python -m pytest -v

# 4. 执行一次 MVP 研究流
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

### 常用命令

```bash
# Markdown report
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"

# CLI/API aligned JSON
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json

# Run script wrapper
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"

# Offline benchmark
python scripts/benchmark_research.py --markdown

# Offline eval bench with the default case set
insight-graph-eval --case-file docs/evals/default.json --markdown --output reports/eval.md

# CI-ready eval gate
insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure

# CI uploads eval-reports with reports/eval.json and reports/eval.md.

# Offline validators
python scripts/validate_sources.py report.md
python scripts/validate_document_reader.py --markdown
python scripts/validate_github_search.py --markdown
```

### MVP Demo

查看已生成的技术评审展示报告：

```text
reports/ai-coding-agents-technical-review.md
```

复现 demo、live LLM 运行和 LLM metadata observability：

```text
docs/demo.md
```

## API MVP

当前 API 是本地 MVP，不包含 WebSocket 或强杀 running job。`/research` 会在应用 runtime preset 环境后同步串行执行 workflow。需要避免 HTTP 长请求阻塞时，可使用 research jobs：`POST /research/jobs` 创建后台任务，`GET /research/jobs/summary` 获取状态数量和 queued/running 概览，`GET /research/jobs` 列出当前任务摘要，`GET /research/jobs/{job_id}` 轮询状态，`POST /research/jobs/{job_id}/cancel` 取消尚未执行的 queued job，`POST /research/jobs/{job_id}/retry` 从 failed/cancelled source 创建新的 queued job。默认 jobs 存在进程内存中；可用 `INSIGHT_GRAPH_RESEARCH_JOBS_PATH` 启用 JSON metadata persistence，或用 `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite` 和 `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH` 启用 SQLite storage。SQLite backend 会使用内部 worker lease 协调多进程 claim/heartbeat/requeue，但不改变公开 API 响应形状。job 响应包含 UTC 时间 metadata：`created_at` 总是存在，`started_at` 在进入 `running` 后出现，`finished_at` 在 `succeeded` / `failed` / `cancelled` 后出现；`queued` jobs 还包含 1-based `queue_position`，该值按当前 queued jobs 动态计算，`running` / terminal jobs 不返回。store 只保留最近 100 个 `succeeded` / `failed` / `cancelled` jobs；`queued` / `running` jobs 不会被裁剪，但 `queued + running` 达到 active cap 后，新建 job 返回 `429 Too many active research jobs.`。summary 返回 `active_count` 和 `active_limit` 便于客户端显示当前负载。设置 `INSIGHT_GRAPH_API_KEY` 后，除 `/health` 外的 API endpoint 会要求 `Authorization: Bearer <key>` 或 `X-API-Key: <key>`。

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --reload
```

Dashboard:

```text
http://127.0.0.1:8000/dashboard
```

Dashboard 是一个静态本地 UI，用于创建、流式跟踪和查看 research jobs，包含执行进度
timeline、Live Events、report、tool calls、LLM metadata 和 Markdown/HTML 下载。Dashboard 会优先连接
`/research/jobs/<job_id>/stream` WebSocket 接收 stage/tool/LLM/report 事件；不可用时回退到 REST polling。如果配置了
`INSIGHT_GRAPH_API_KEY`，请先在 dashboard 的 API key 输入框填入同一个 key。

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot"}'
```

```bash
curl -X POST http://127.0.0.1:8000/research/jobs \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot"}'

curl http://127.0.0.1:8000/research/jobs

curl http://127.0.0.1:8000/research/jobs/summary

curl http://127.0.0.1:8000/research/jobs/<job_id>

# WebSocket stream: ws://127.0.0.1:8000/research/jobs/<job_id>/stream

curl http://127.0.0.1:8000/research/jobs/<job_id>/report.md

curl http://127.0.0.1:8000/research/jobs/<job_id>/report.html

curl -X POST http://127.0.0.1:8000/research/jobs/<job_id>/cancel

curl -X POST http://127.0.0.1:8000/research/jobs/<job_id>/retry
```

Job 状态包括 `queued`、`running`、`succeeded`、`failed` 和 `cancelled`。列表和 summary 只返回摘要，不包含 `result` 或错误细节；summary 额外返回各状态数量以及 queued/running 活跃任务概览。`succeeded` 详情响应包含 `result`，结构与同步 `/research` 一致；`failed` 详情只返回安全错误 `Research workflow failed.`，不暴露底层 provider payload、路径或异常细节。取消接口只接受 `queued` jobs；`running` / `succeeded` / `failed` jobs 返回 `409`，不尝试强杀正在运行的 workflow。retry 接口只接受 `failed` / `cancelled` source，并创建新的 queued job，不修改 source job。

### Research job repository helpers

`src/insight_graph/research_jobs.py` owns research job state, persistence orchestration, lifecycle transitions, and API response shaping. Tests and maintenance code should use the public helper surface instead of mutating private module state such as `_JOBS`, `_NEXT_JOB_SEQUENCE`, `_RESEARCH_JOBS_PATH`, or `_MAX_*` directly.

Maintenance helpers include `reset_research_jobs_state()`, `seed_research_job()`, `seed_research_jobs()`, `set_research_jobs_store_path()`, `set_research_job_limits()`, `get_research_job_record()`, `get_next_research_job_sequence()`, and `update_research_job_record()`. `get_research_job_record()` returns a copy, so mutating the returned object does not change internal state; use `update_research_job_record()` for explicit state updates.

`uvicorn` 是运行示例依赖，不是当前 package runtime dependency。

## 当前输出

- **CLI 报告**：Markdown 格式，包含 `Key Findings`、有可引用矩阵行时的 `Competitive Matrix`、`Critic Assessment`、`References`。
- **结构化输出**：`--output-json` 包含 `competitive_matrix`，便于当前 API、benchmark 和后续前端复用。
- **数据源**：默认固定 mock evidence，不进行真实联网搜索。
- **前端 / WebSocket**：尚未实现，属于后续路线图。

## 示例任务

```text
请分析 AI Coding Agent 市场的主要玩家，包括 Cursor、OpenCode、Claude Code、GitHub Copilot 和 Codeium。
请比较它们的产品定位、核心功能、定价策略、生态集成、技术路线和潜在风险，并给出未来 12 个月的市场趋势判断。
要求所有关键事实附带可验证引用。
```

预期输出：Executive Summary、市场格局概览、竞品功能矩阵、定价与商业模式对比、技术趋势分析、风险与不确定性、未来 12 个月判断、References。

## License

MIT
