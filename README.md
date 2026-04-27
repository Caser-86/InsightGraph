# InsightGraph

基于 LangGraph 的多智能体商业情报研究引擎，面向竞品分析、技术趋势、市场机会识别与产业洞察等场景的深度报告自动生成。支持任务分解、工具调用、Critic 闭环纠错、证据溯源与引用校验，产出带可验证来源的结构化研究报告。

> 当前仓库处于 MVP 架构落地阶段：优先实现可测试的 LangGraph 多智能体研究流骨架，再逐步接入真实搜索、持久化、向量记忆与 Web API。

## 当前 MVP 已实现

| 能力 | 状态 |
|------|------|
| LangGraph 工作流 | 已实现 Planner → Collector → Analyst → Critic → Reporter 的可运行状态图 |
| CLI | 已实现 `insight-graph research "..."` / `python -m insight_graph.cli research "..."` |
| API | 已实现 `GET /health`、同步 `POST /research`、单进程内存异步 jobs |
| 证据链 | 已实现 deterministic `mock_search`、direct URL `fetch_url`、默认 mock `web_search -> pre_fetch -> fetch_url`，并支持 opt-in DuckDuckGo provider |
| GitHub evidence | 默认 deterministic/offline；可 opt-in live GitHub repository search provider |
| 文档 evidence | 支持 cwd 内 TXT/Markdown/HTML/PDF、本地 chunking、JSON lexical query ranking |
| 文件工具 | 支持 cwd 内只读 `read_file` / `list_directory` 和 create-only `write_file` |
| Analyst / Reporter | 默认 deterministic/offline；可 opt-in OpenAI-compatible LLM |
| Critic | 已实现证据数量、分析结果、citation support 检查 |
| 可观测性 | 已记录 tool call log、LLM metadata log、token usage metadata |
| 测试 | 已实现 pytest 覆盖 state、agents、tools、graph、CLI、API、scripts |

MVP 默认使用 deterministic/offline 行为，适合本地开发、测试和 CI。真实搜索、真实 LLM、GitHub API 等能力都必须显式 opt-in。

## 文档入口

- [配置说明](docs/configuration.md)：搜索 provider、GitHub provider、document reader、LLM preset、observability、后续配置项。
- [架构蓝图](docs/architecture.md)：目标项目结构、核心特性、技术架构、执行流程、agent 协作、工具和证据链。
- [脚本说明](docs/scripts.md)：run、benchmark、validator、LLM metadata log 脚本用法。
- [Caveman project skills](docs/skills/caveman-applied-skills.md)：当前项目已应用的本地 OpenCode/Caveman 规则。

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

# Offline validators
python scripts/validate_sources.py report.md
python scripts/validate_document_reader.py --markdown
python scripts/validate_github_search.py --markdown
```

## API MVP

当前 API 是单进程 MVP，不包含 WebSocket、auth、持久化或并行 workflow execution。`/research` 会在应用 runtime preset 环境后同步串行执行 workflow。需要避免 HTTP 长请求阻塞时，可使用内存 jobs：`POST /research/jobs` 创建后台任务，`GET /research/jobs` 列出当前任务摘要，`GET /research/jobs/{job_id}` 轮询状态，`POST /research/jobs/{job_id}/cancel` 取消尚未执行的 queued job。jobs 存在进程内存中，服务重启后会丢失；后台执行仍通过单 worker 和 runtime preset lock 串行保护环境变量。内存 store 只保留最近 100 个 `succeeded` / `failed` / `cancelled` jobs；`queued` / `running` jobs 不会被裁剪。

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --reload
```

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

curl http://127.0.0.1:8000/research/jobs/<job_id>

curl -X POST http://127.0.0.1:8000/research/jobs/<job_id>/cancel
```

Job 状态包括 `queued`、`running`、`succeeded`、`failed` 和 `cancelled`。列表只返回摘要，不包含 `result` 或错误细节；`succeeded` 详情响应包含 `result`，结构与同步 `/research` 一致；`failed` 详情只返回安全错误 `Research workflow failed.`，不暴露底层 provider payload、路径或异常细节。取消接口只接受 `queued` jobs；`running` / `succeeded` / `failed` jobs 返回 `409`，不尝试强杀正在运行的 workflow。

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
