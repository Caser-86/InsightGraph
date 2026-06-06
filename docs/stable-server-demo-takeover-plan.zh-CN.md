# InsightGraph 稳定服务器演示版接管审计与执行计划

> 面向目标：把当前项目交付为可稳定上云、可演示、可诊断、可恢复的服务器演示版。

## 0. 审计结论

当前项目已具备核心研究链路、API、内嵌 Dashboard、异步任务、SQLite job 持久化、LLM 路由、搜索提供商、多档报告强度、证据与引用诊断、smoke 脚本和 CI 测试。稳定服务器演示版的主要缺口集中在容器化交付、生产环境模板、云端运行脚本、演示验收脚本、密钥与成本边界、故障诊断操作手册。

本轮验证：

- `python -m pytest -o addopts= -q tests/test_smoke_deployment.py tests/test_api.py tests/test_research_jobs_sqlite_backend.py`
- 结果：`154 passed in 14.57s`
- 备注：直接 `python -m pytest` 在当前本地环境会因默认覆盖率参数需要 `pytest-cov` 而失败，错误为 `unrecognized arguments: --cov=src/insight_graph ...`。

## 1. 产品地图

### 1.1 用户角色

| 角色 | 目标 | 关键行为 | 成功标准 |
| --- | --- | --- | --- |
| 演示操作者 | 在服务器上稳定展示研究报告生成能力 | 打开 Dashboard、选择强度、选择搜索引擎、提交任务、查看进度、导出报告 | 任务能完成；失败时能看到原因；报告能下载 |
| 业务评审者 | 判断报告质量和证据可信度 | 阅读报告、查看 evidence pool、查看 citation support、检查 LLM/tool log | 引用来源明确；质量卡能解释报告可信度 |
| 技术维护者 | 部署和排障 | 配置环境变量、启动服务、查看健康检查、查看日志、重启任务 | 服务重启后任务状态可恢复；日志能定位失败 |
| 成本管理员 | 控制 LLM 与搜索成本 | 关闭 SerpAPI、设置强度、设置 daily/per-run limit | 演示前能开，平时能关；超额前有指标 |

### 1.2 用户目标

- 创建中文研究任务。
- 选择 `concise`、`standard`、`deep`、`deep-plus` 报告强度。
- 手动选择搜索引擎，平时关闭 SerpAPI，演示时开启。
- 使用外部 LLM 做分析和报告生成。
- 查看任务状态、进度、失败原因、工具调用、LLM 调用、证据池、引用校验。
- 下载 Markdown 和 HTML 报告。
- 服务器重启后保留任务记录，运行中任务按规则恢复或重新排队。

### 1.3 核心业务流程

1. 用户打开 `/dashboard`。
2. 用户输入研究查询。
3. 用户选择 preset、报告强度、搜索引擎、网页搜索开关、相关性判断。
4. 前端调用 `POST /research/jobs`。
5. 后端创建 queued job。
6. worker claim job 并写入 running 状态。
7. LangGraph 执行 `planner -> collector -> analyst -> critic -> reporter`。
8. 工具层执行 web search、news、GitHub、SEC、fetch、document reader。
9. LLM 层执行 analyst、reporter、report_review、relevance judge。
10. reporter 生成 Markdown 报告并写入 result。
11. Dashboard 通过轮询和 WebSocket 展示进度、质量卡、证据、报告。
12. 用户下载 `.md` 或 `.html`。

### 1.4 业务规则

- `/health` 公开。
- 设置 `INSIGHT_GRAPH_API_KEY` 后，非健康检查接口要求 Bearer 或 `X-API-Key`。
- `live-research` 是正式 live 产品路径。
- `offline` 只作为 deterministic 测试和 CI fallback。
- SQLite 是服务器演示版推荐 job metadata 后端。
- `deep-plus` 成本最高，必须配合搜索和 LLM 预算边界。
- SerpAPI 必须支持按需启用、per-run limit、daily limit。
- 任务只能在 terminal 状态删除。
- failed/cancelled 任务可以 retry。

### 1.5 边界场景

- LLM key 缺失。
- LLM 超时。
- 搜索引擎限额耗尽。
- SerpAPI 关闭但用户选择 SerpAPI。
- DuckDuckGo 超时或返回空。
- fetch URL 失败。
- 任务运行中服务器重启。
- SQLite 被锁。
- WebSocket 断开。
- 报告为空或过短。
- 引用校验全部 unsupported。
- 用户提交超长 query。

### 1.6 异常场景

- `POST /research/jobs` 返回 `429`：active job 达上限。
- `GET /research/jobs/{id}` 返回 `404`：job id 不存在或已被 retention 删除。
- `DELETE /research/jobs/{id}` 返回 `409`：job 仍在 queued/running。
- `report.md` 返回 `409`：报告尚未生成。
- LLM call 记录为失败：需要展示 stage、model、duration、token、safe error。
- search provider diagnostic 有限额或 key 问题：需要 Dashboard 明确显示。

## 2. 系统地图

### 2.1 前端系统

- 文件：[dashboard.py](/D:/Files/opencode.files/src/insight_graph/dashboard.py)
- 形态：FastAPI 返回内嵌 HTML/CSS/JS，无独立构建。
- 页面：`GET /dashboard`
- 功能：提交任务、查看任务摘要、查看最近任务、任务详情、质量卡、证据、引用、LLM/tool log、下载报告。
- 风险：前端代码集中在单个 Python 字符串中，维护成本较高；服务器演示版可以保留，但需要浏览器验收脚本。

### 2.2 后端系统

- 文件：[api.py](/D:/Files/opencode.files/src/insight_graph/api.py)
- 框架：FastAPI
- 核心接口：`/health`、`/research`、`/research/jobs`、`/memory`、`/dashboard`、WebSocket stream。
- 风险：API 与 worker 逻辑集中，演示版可用；生产化前应拆分 app factory、job routes、memory routes、worker runner。

### 2.3 数据库

- 当前支持：memory、JSON、SQLite。
- 服务器演示推荐：SQLite。
- 文件：[research_jobs_sqlite_backend.py](/D:/Files/opencode.files/src/insight_graph/research_jobs_sqlite_backend.py)
- 可选：PostgreSQL checkpoint、pgvector memory、pgvector document retrieval。
- 风险：本地 `data/research_jobs.db-journal` 表明 SQLite journal 文件会存在；部署必须挂载数据卷。

### 2.4 缓存

- fetch cache 文件：[fetch_cache.py](/D:/Files/opencode.files/src/insight_graph/tools/fetch_cache.py)
- 默认需通过环境变量启用或控制。
- 风险：演示服务器如果启用缓存，需要设置容量和清理策略。

### 2.5 消息队列

- 当前没有外部消息队列。
- 当前异步方式：进程内队列、SQLite worker lease、heartbeat。
- 服务器演示版可接受。
- 多实例生产环境需要 Redis/RQ/Celery 或数据库队列隔离设计。

### 2.6 Agent 系统

- 编排：[graph.py](/D:/Files/opencode.files/src/insight_graph/graph.py)
- 节点：planner、collector、analyst、critic、reporter。
- 关键文件：[planner.py](/D:/Files/opencode.files/src/insight_graph/agents/planner.py)、[executor.py](/D:/Files/opencode.files/src/insight_graph/agents/executor.py)、[analyst.py](/D:/Files/opencode.files/src/insight_graph/agents/analyst.py)、[critic.py](/D:/Files/opencode.files/src/insight_graph/agents/critic.py)、[reporter.py](/D:/Files/opencode.files/src/insight_graph/agents/reporter.py)
- 风险：LLM 输出 JSON 校验严格，失败会触发 fallback 或 job failure；演示版需要稳定模型配置和失败可视化。

### 2.7 LLM 调用

- 配置：[config.py](/D:/Files/opencode.files/src/insight_graph/llm/config.py)
- 路由：[router.py](/D:/Files/opencode.files/src/insight_graph/llm/router.py)
- 观测：[observability.py](/D:/Files/opencode.files/src/insight_graph/llm/observability.py)、[trace_writer.py](/D:/Files/opencode.files/src/insight_graph/llm/trace_writer.py)
- 能力：OpenAI-compatible、chat_completions、responses、fast/default/strong tier。
- 风险：没有 `.env.example`，服务器演示容易配错模型名、base_url、wire_api、output tokens。

### 2.8 第三方服务

- DuckDuckGo：默认 live search。
- SerpAPI：可选搜索，需 key 和限额。
- Google CSE：可选搜索。
- GitHub REST：可选，需 token 提升额度。
- SEC：可选，适合上市公司。
- LLM provider：OpenAI-compatible。

### 2.9 部署架构

- 当前文档推荐：Python 3.11、uvicorn、SQLite、可选 PostgreSQL/pgvector、反向代理或 VPN。
- 缺口：无 `Dockerfile`、无 `compose.yaml`、无 `.env.example`、无 Nginx 示例、无云端 systemd 文件、无容器健康检查。

## 3. 代码地图

### 3.1 目录结构

| 目录 | 文件数 | 行数 | 责任 |
| --- | ---: | ---: | --- |
| `src/` | 69 | 17753 | 产品代码 |
| `tests/` | 54 | 20474 | 单元、API、任务、质量、搜索、部署 smoke 测试 |
| `docs/` | 27 | 2378 | 架构、API、部署、配置、路线文档 |
| `scripts/` | 15 | 2222 | 本地启动、smoke、benchmark、eval 辅助脚本 |

### 3.2 核心模块

- API：`src/insight_graph/api.py`
- Dashboard：`src/insight_graph/dashboard.py`
- LangGraph：`src/insight_graph/graph.py`
- State：`src/insight_graph/state.py`
- Jobs：`src/insight_graph/research_jobs.py`
- SQLite jobs：`src/insight_graph/research_jobs_sqlite_backend.py`
- LLM：`src/insight_graph/llm/*`
- Tools：`src/insight_graph/tools/*`
- Report quality：`src/insight_graph/report_quality/*`
- Memory：`src/insight_graph/memory/*`
- Persistence：`src/insight_graph/persistence/*`

### 3.3 核心数据结构

- `GraphState`
- `Evidence`
- `Finding`
- `CompetitiveMatrixRow`
- `Critique`
- `ToolCallRecord`
- `LLMCallRecord`
- `ResearchJob`
- `ReportIntensityConfig`
- `LLMConfig`

### 3.4 已存在设计模式

- FastAPI app factory：`create_app()`
- LangGraph state machine：`StateGraph(GraphState)`
- Provider pattern：search provider、LLM provider、memory backend、jobs backend。
- Environment-driven configuration。
- Backend interface + SQLite implementation。
- Deterministic fallback for tests。
- Quality gate and diagnostics aggregation。

## 4. 完成度审计

| 模块名称 | 完成度 | 风险等级 | 缺失内容 |
| --- | ---: | --- | --- |
| 核心研究图 | 85% | 中 | 云端失败恢复验收、长任务超时边界 |
| API | 85% | 中 | 生产错误码清单、限流、请求体大小限制 |
| Dashboard | 80% | 中 | 自动化 UI smoke、部署环境 API key 测试 |
| SQLite jobs | 90% | 中 | 云端数据卷脚本、备份脚本 |
| LLM 路由 | 80% | 高 | `.env.example`、模型连通性脚本、强模型配置验收 |
| 搜索提供商 | 80% | 高 | SerpAPI 演示开关流程、限额可视化验收 |
| 报告质量 | 75% | 高 | 最小成功标准演示脚本、失败报告样例 |
| 可观测性 | 75% | 中 | 结构化日志落盘、trace retention |
| 安全 | 60% | 高 | HTTPS、反代配置、限流、安全 header、secret 检查 |
| DevOps | 45% | 高 | Docker、compose、Nginx、云端部署脚本、发布检查表 |
| 文档 | 70% | 中 | 服务器演示 Runbook、故障排查、环境模板 |
| 测试 | 85% | 中 | 容器内 smoke、真实 provider opt-in 测试 |

### 4.1 已完成

- 核心 Agent 编排。
- 异步 job API。
- Dashboard。
- SQLite job 后端。
- LLM 调用记录。
- 搜索 provider 多选能力。
- 报告强度档位。
- 引用支持校验。
- 目标测试通过。

### 4.2 部分完成

- 云部署文档已有，但缺容器化资产。
- 质量诊断已有，但演示失败 Runbook 不足。
- 成本控制变量已有，但演示操作流程不足。
- trace 支持已有，但云端安全留存策略不足。

### 4.3 未开始

- Dockerfile。
- compose.yaml。
- `.env.example`。
- Nginx 反代示例。
- 容器健康检查。
- 云端一键 smoke。
- 备份恢复脚本。
- 演示前检查脚本。

### 4.4 高风险模块

- LLM 配置。
- SerpAPI 成本和限额。
- 长任务稳定性。
- 报告质量 gate。
- 云端数据持久化。
- API 暴露安全。

### 4.5 技术债务模块

- Dashboard 单文件 HTML 字符串。
- API 文件包含路由、worker、event stream、质量 gate，多责任集中。
- 部署资产缺失。
- 当前本地测试依赖覆盖率插件，裸环境容易失败。

## 5. 主动发现遗漏

### 5.1 产品遗漏

- 新增演示模式说明卡。
- 新增搜索成本提示。
- 新增 SerpAPI 关闭状态提示。
- 新增任务失败原因解释区。
- 新增演示前检查结果区。
- 新增报告质量不达标的可读建议区。

### 5.2 技术遗漏

- 新增 API 请求大小限制。
- 新增 active job 配置文档和默认值说明。
- 新增 provider 连接检测命令。
- 新增 LLM 连通性检测命令。
- 新增容器内 healthcheck。
- 新增容器启动前数据目录创建逻辑。

### 5.3 AI 系统遗漏

- 新增模型连通性 smoke。
- 新增 analyst/reporter/report_review 分阶段模型检查。
- 新增 token 预算显示。
- 新增每次任务预估成本字段。
- 新增 tool failure retry policy 文档。
- 新增 prompt injection 风险说明。
- 新增高强度模式演示成本确认。

### 5.4 安全遗漏

- 新增 Nginx HTTPS 示例。
- 新增安全 header。
- 新增 API key 强制配置的服务器示例。
- 新增 `.env` 权限检查。
- 新增 trace full payload 禁用示例。
- 新增 prompt/completion trace 脱敏说明。

### 5.5 运维遗漏

- 新增 Dockerfile。
- 新增 compose.yaml。
- 新增日志目录。
- 新增数据卷。
- 新增备份脚本。
- 新增恢复脚本。
- 新增服务重启 Runbook。
- 新增云端 smoke checklist。

## 6. 稳定服务器演示版 WBS

### 6.1 项目：稳定服务器演示版

#### 6.1.1 系统：部署系统

##### 6.1.1.1 模块：Docker 镜像

- [ ] 创建 `Dockerfile`。
- [ ] 设置基础镜像为 `python:3.11-slim`。
- [ ] 设置工作目录为 `/app`。
- [ ] 复制 `pyproject.toml`。
- [ ] 安装运行依赖 `python -m pip install -e .`。
- [ ] 复制 `src/`、`scripts/`、`docs/`、`README.md`。
- [ ] 创建 `/data`、`/reports`、`/logs` 目录。
- [ ] 设置 `PYTHONPATH=/app/src`。
- [ ] 设置默认启动命令 `uvicorn insight_graph.api:app --host 0.0.0.0 --port 8000`。
- [ ] 新增 Dockerfile 测试：构建镜像成功。
- [ ] 新增 Dockerfile 测试：容器启动后 `/health` 返回 200。

##### 6.1.1.2 模块：Docker Compose

- [ ] 创建 `compose.yaml`。
- [ ] 新增 `insightgraph` 服务。
- [ ] 映射端口 `8000:8000`。
- [ ] 挂载 `./data:/data`。
- [ ] 挂载 `./reports:/reports`。
- [ ] 挂载 `./logs:/logs`。
- [ ] 配置 `env_file: .env`。
- [ ] 配置 healthcheck 请求 `/health`。
- [ ] 配置 restart policy 为 `unless-stopped`。
- [ ] 新增 compose smoke 命令文档。

##### 6.1.1.3 模块：Nginx

- [ ] 创建 `docs/nginx-insightgraph.conf`。
- [ ] 配置 `server_name` 占位域名。
- [ ] 配置 `/` 反代到 `127.0.0.1:8000`。
- [ ] 配置 WebSocket upgrade header。
- [ ] 配置 `client_max_body_size 2m`。
- [ ] 配置安全 header。
- [ ] 配置 HTTPS 证书路径示例。
- [ ] 写入 reload 命令。

#### 6.1.2 系统：环境配置系统

##### 6.1.2.1 模块：环境变量模板

- [ ] 创建 `.env.example`。
- [ ] 写入 `INSIGHT_GRAPH_API_KEY=replace-me`。
- [ ] 写入 SQLite job 后端变量。
- [ ] 写入 checkpoint resume 变量。
- [ ] 写入 LLM base_url/key/model 变量。
- [ ] 写入 fast/default/strong 模型变量。
- [ ] 写入搜索开关变量。
- [ ] 写入 SerpAPI key 空值示例。
- [ ] 写入 SerpAPI daily limit 示例。
- [ ] 写入 DuckDuckGo daily limit 示例。
- [ ] 写入 trace metadata-only 示例。
- [ ] 写入 `INSIGHT_GRAPH_LLM_TRACE_FULL=0`。

##### 6.1.2.2 模块：配置校验脚本

- [ ] 创建 `scripts/validate_demo_env.py`。
- [ ] 读取 `.env` 或当前环境。
- [ ] 检查 `INSIGHT_GRAPH_API_KEY` 非空。
- [ ] 检查 `INSIGHT_GRAPH_LLM_BASE_URL` 非空。
- [ ] 检查 `INSIGHT_GRAPH_LLM_API_KEY` 非空。
- [ ] 检查 `INSIGHT_GRAPH_LLM_MODEL` 非空。
- [ ] 检查 SQLite path 所在目录可写。
- [ ] 检查 SerpAPI 未启用时允许 key 为空。
- [ ] 检查 SerpAPI 启用时 key 非空。
- [ ] 输出 JSON 结果。
- [ ] 新增测试 `tests/test_validate_demo_env.py`。

#### 6.1.3 系统：后端稳定性

##### 6.1.3.1 模块：健康检查

- [ ] 扩展 `/health` 响应字段。
- [ ] 增加 `jobs_backend` 字段。
- [ ] 增加 `sqlite_path_configured` 字段。
- [ ] 增加 `startup_worker_enabled` 字段。
- [ ] 增加 `checkpoint_resume_enabled` 字段。
- [ ] 不返回任何密钥。
- [ ] 新增测试：未配置 key 时 `/health` 仍公开。
- [ ] 新增测试：health 不包含 secret 字段。

##### 6.1.3.2 模块：演示成功门槛

- [ ] 确认 `INSIGHT_GRAPH_MIN_SUCCESS_EVIDENCE` 默认值。
- [ ] 确认 `INSIGHT_GRAPH_MIN_SUCCESS_VERIFIED_EVIDENCE` 默认值。
- [ ] 确认 `INSIGHT_GRAPH_MIN_SUCCESSFUL_LLM_CALLS` 默认值。
- [ ] 确认 `INSIGHT_GRAPH_MIN_SUCCESS_REPORT_CHARS` 默认值。
- [ ] 创建 `docs/demo-success-criteria.zh-CN.md`。
- [ ] 写入 concise 成功门槛。
- [ ] 写入 standard 成功门槛。
- [ ] 写入 deep 成功门槛。
- [ ] 写入 deep-plus 成功门槛。

##### 6.1.3.3 模块：任务恢复

- [ ] 创建 SQLite data volume 操作文档。
- [ ] 创建重启前 job 状态检查命令。
- [ ] 创建重启后 queued job 检查命令。
- [ ] 创建 expired running job requeue 验收步骤。
- [ ] 创建 report 下载验收步骤。
- [ ] 新增文档链接到 `docs/deployment.zh-CN.md`。

#### 6.1.4 系统：AI 与搜索演示系统

##### 6.1.4.1 模块：LLM 连通性

- [ ] 创建 `scripts/check_llm_provider.py`。
- [ ] 读取默认 LLM 配置。
- [ ] 发送 1 次最小 JSON completion。
- [ ] 验证返回内容为 JSON。
- [ ] 打印 stage、model、wire_api、duration_ms。
- [ ] 对 fast model 执行检查。
- [ ] 对 default model 执行检查。
- [ ] 对 strong model 执行检查。
- [ ] 不打印 API key。
- [ ] 新增测试：缺 key 时返回非零退出码。

##### 6.1.4.2 模块：搜索连通性

- [ ] 创建 `scripts/check_search_provider.py`。
- [ ] 支持 `--provider duckduckgo`。
- [ ] 支持 `--provider serpapi`。
- [ ] 支持 `--provider google`。
- [ ] 支持 `--limit 3`。
- [ ] 输出 provider、result_count、first_url。
- [ ] SerpAPI 未配置 key 时输出明确错误。
- [ ] 新增测试：mock provider 返回成功。
- [ ] 新增测试：serpapi 缺 key 返回失败且不泄露密钥。

##### 6.1.4.3 模块：成本边界

- [ ] 在 `.env.example` 写入 `INSIGHT_GRAPH_SERPAPI_DAILY_CALL_LIMIT=20`。
- [ ] 在 `.env.example` 写入 `INSIGHT_GRAPH_SERPAPI_PER_RUN_LIMIT=5`。
- [ ] 在 `.env.example` 写入 `INSIGHT_GRAPH_DUCKDUCKGO_DAILY_CALL_LIMIT=200`。
- [ ] 在 Dashboard 显示 search quota snapshot。
- [ ] 在 job detail 显示 provider diagnostic。
- [ ] 新增测试：quota snapshot 不包含 secret。

#### 6.1.5 系统：前端 Dashboard

##### 6.1.5.1 页面：任务创建页

- [ ] 保留查询框在首屏核心位置。
- [ ] 显示 API key 状态为“已保护/未保护”。
- [ ] 显示当前搜索引擎选择。
- [ ] 显示 SerpAPI 是否启用。
- [ ] 显示报告强度预计成本提示。
- [ ] 提交前检查 query 非空。
- [ ] 提交失败时显示后端 detail。

##### 6.1.5.2 页面：任务详情页

- [ ] 显示 job id。
- [ ] 显示 status。
- [ ] 显示 progress stage。
- [ ] 显示 runtime seconds。
- [ ] 显示 tool_call_count。
- [ ] 显示 llm_call_count。
- [ ] 显示 evidence_pool 数量。
- [ ] 显示 citation_support supported 数量。
- [ ] 显示 report download 按钮。
- [ ] 失败时显示 failure hints。

##### 6.1.5.3 组件：演示状态条

- [ ] 创建演示状态条 DOM 区域。
- [ ] 显示 API protected。
- [ ] 显示 SQLite enabled。
- [ ] 显示 startup worker enabled。
- [ ] 显示 selected model tier。
- [ ] 显示 selected search providers。
- [ ] 任何状态不可用时使用黄色提示。

#### 6.1.6 系统：测试与验收

##### 6.1.6.1 模块：本地测试

- [ ] 运行 `python -m pytest -o addopts= -q tests/test_smoke_deployment.py`。
- [ ] 运行 `python -m pytest -o addopts= -q tests/test_api.py`。
- [ ] 运行 `python -m pytest -o addopts= -q tests/test_research_jobs_sqlite_backend.py`。
- [ ] 运行 `python -m ruff check src tests scripts`。

##### 6.1.6.2 模块：容器测试

- [ ] 构建镜像。
- [ ] 启动 compose。
- [ ] 请求 `/health`。
- [ ] 请求 `/dashboard`。
- [ ] 创建 offline job。
- [ ] 等待 job succeeded。
- [ ] 下载 report.md。
- [ ] 停止 compose。
- [ ] 重新启动 compose。
- [ ] 确认历史 job 仍可查询。

##### 6.1.6.3 模块：演示测试

- [ ] 使用 `concise` 跑 1 个短查询。
- [ ] 使用 `standard` 跑 1 个公司分析查询。
- [ ] SerpAPI 关闭时提交任务。
- [ ] SerpAPI 开启时提交任务。
- [ ] LLM key 错误时提交任务。
- [ ] 验证失败原因可读。
- [ ] 验证报告下载可用。
- [ ] 验证 trace 不泄露 key。

#### 6.1.7 系统：运维 Runbook

##### 6.1.7.1 模块：部署文档

- [ ] 更新 `docs/deployment.zh-CN.md`。
- [ ] 写入服务器规格：2C4G 演示、4C8G 推荐、8C16G 高强度。
- [ ] 写入 Docker 安装步骤。
- [ ] 写入 compose 启动步骤。
- [ ] 写入 Nginx 配置步骤。
- [ ] 写入 HTTPS 配置步骤。
- [ ] 写入 smoke 验收步骤。

##### 6.1.7.2 模块：故障排查

- [ ] 创建 `docs/demo-troubleshooting.zh-CN.md`。
- [ ] 写入无法访问 Dashboard 的检查步骤。
- [ ] 写入 job not found 的检查步骤。
- [ ] 写入 LLM call failed 的检查步骤。
- [ ] 写入 SerpAPI quota 用完的检查步骤。
- [ ] 写入报告过短的检查步骤。
- [ ] 写入 SQLite locked 的检查步骤。
- [ ] 写入 WebSocket 断开的检查步骤。

##### 6.1.7.3 模块：备份恢复

- [ ] 创建 `scripts/backup_demo_data.ps1`。
- [ ] 复制 `data/research_jobs.db` 到 `backups/`。
- [ ] 复制 `data/research_jobs.json` 到 `backups/`。
- [ ] 文件名包含 UTC 时间。
- [ ] 创建 `scripts/restore_demo_data.ps1`。
- [ ] 恢复前停止服务。
- [ ] 恢复后启动服务。
- [ ] 恢复后请求 `/health`。

## 7. 优先级

### P0：服务器演示必须完成

- Dockerfile。
- compose.yaml。
- `.env.example`。
- `/health` 服务器字段。
- LLM 连通性脚本。
- 搜索连通性脚本。
- 容器 smoke。
- 部署中文文档。
- 故障排查中文文档。

### P1：演示稳定性增强

- Nginx 示例。
- 备份恢复脚本。
- Dashboard 演示状态条。
- search quota 展示。
- demo success criteria 文档。

### P2：生产化前置

- API 文件拆分。
- Dashboard 从 Python 字符串拆出静态资源。
- Redis/Celery 或外部队列设计。
- Postgres job backend。
- 结构化日志系统。
- 告警系统。

## 8. 开发批次建议

### Batch 1：容器交付

- 创建 `Dockerfile`。
- 创建 `compose.yaml`。
- 创建 `.env.example`。
- 跑容器 `/health`。
- 跑 offline job。

### Batch 2：演示前检查

- 创建 `scripts/validate_demo_env.py`。
- 创建 `scripts/check_llm_provider.py`。
- 创建 `scripts/check_search_provider.py`。
- 新增对应测试。

### Batch 3：运维文档

- 更新 `docs/deployment.zh-CN.md`。
- 创建 `docs/demo-troubleshooting.zh-CN.md`。
- 创建 `docs/demo-success-criteria.zh-CN.md`。

### Batch 4：Dashboard 演示状态

- 在 Dashboard 增加演示状态条。
- 在 job detail 增加 quota/provider diagnostic。
- 新增 API 测试。
- 运行浏览器验收。

### Batch 5：备份恢复

- 创建备份脚本。
- 创建恢复脚本。
- 新增文档。
- 手动验证停止、备份、恢复、启动。

## 9. 验收标准

- `python -m ruff check src tests scripts` 通过。
- `python -m pytest -o addopts=` 通过。
- `docker build` 通过。
- `docker compose up -d` 后 `/health` 返回 200。
- `/dashboard` 可打开。
- offline job 能 succeeded。
- live-research concise job 能启动并给出可读失败或成功报告。
- SQLite 数据卷重启后 job 仍存在。
- 错误 LLM key 不会导致服务崩溃。
- SerpAPI 关闭时不会消耗 SerpAPI 额度。
- SerpAPI 开启时 quota 信息可见。
- 报告可下载 Markdown 和 HTML。
- 日志不输出 API key。

