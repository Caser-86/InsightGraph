# FastAPI Research API MVP 设计

## 目标

为 InsightGraph 增加第一版 HTTP API，让外部调用方可以通过 REST 请求运行当前研究工作流，并获得与 CLI `--output-json` 对齐的结构化 JSON 响应。

第一版只做同步 REST API，不实现 WebSocket、异步任务队列、鉴权、持久化、任务取消或后台进度流。

## 非目标

- 不实现 WebSocket streaming。
- 不新增数据库、checkpoint、resume 或 long-term memory。
- 不实现用户认证、API key、rate limit 或多租户隔离。
- 不实现后台任务队列或任务状态查询。
- 不改变默认 deterministic/offline 行为。
- 不把 `uvicorn` server command 纳入第一版。
- 不暴露 raw exception、prompt、completion、API key 或 provider response body。

## 依赖

在 `pyproject.toml` runtime dependencies 中新增：

```toml
"fastapi>=0.115.0"
```

不把 `uvicorn` 加入第一版必需依赖。用户可用自己的 ASGI server 运行 app；README 只展示 Python import 方式和可选 `uvicorn` 示例，不要求测试依赖本地启动 server。

## API 模块

新增 `src/insight_graph/api.py`，负责 HTTP 层。

公开对象：

```python
app = FastAPI(title="InsightGraph API")
```

Endpoints：

```text
GET /health
POST /research
```

`GET /health` 返回：

```json
{"status": "ok"}
```

`POST /research` 请求体：

```json
{
  "query": "Compare Cursor, OpenCode, and GitHub Copilot",
  "preset": "offline"
}
```

字段规则：

- `query` 必填，必须是去除首尾空白后非空字符串。
- `preset` 可选，允许 `offline` 或 `live-llm`，默认 `offline`。

`POST /research` 成功响应与 CLI JSON payload 对齐：

```json
{
  "user_request": "Compare Cursor, OpenCode, and GitHub Copilot",
  "report_markdown": "# InsightGraph Research Report\n\n## Key Findings\n\nCursor and GitHub Copilot differ in packaging signals. [1]\n",
  "findings": [],
  "competitive_matrix": [],
  "critique": null,
  "tool_call_log": [],
  "llm_call_log": [],
  "iterations": 0
}
```

实现应复用 CLI 的 JSON payload builder，避免 CLI 和 API 响应结构分叉。

## CLI 复用边界

`src/insight_graph/cli.py` 当前已有：

- `_apply_research_preset(preset)`
- `_build_research_json_payload(state)`

API 第一版可以复用这些函数，但需要保持导入方向清晰：

- `api.py` 可以从 `cli.py` 导入 payload builder 和 preset enum/helper。
- `cli.py` 不能导入 `api.py`。

如果实现时发现 `cli.py` 导入会造成 HTTP 层依赖 CLI 层过重，可以新增 `src/insight_graph/output.py` 存放 shared payload builder；但第一版优先使用最小变更。

## Preset 行为

API preset 行为与 CLI 一致：

- `offline` 不设置 live 环境变量。
- `live-llm` 使用现有 `LIVE_LLM_PRESET_DEFAULTS`，且只补缺失环境变量，不覆盖用户显式配置。

API 请求级别不实现环境隔离。也就是说，`live-llm` preset 通过 process environment 生效，与 CLI 当前行为一致。README 需明确当前 API MVP 是单进程同步 MVP，不保证并发请求之间的环境变量隔离。

## 错误处理

HTTP 错误策略：

- 空 `query` 返回 HTTP 422，由 Pydantic validation 触发。
- 未知 `preset` 返回 HTTP 422，由 enum validation 触发。
- `run_research()` 抛出未预期异常时返回 HTTP 500：

```json
{"detail": "Research workflow failed."}
```

500 响应不得包含 raw exception message，避免泄露 provider details、local paths 或 secrets。

## 测试策略

新增 `tests/test_api.py`，使用 FastAPI `TestClient`，全部离线运行。

覆盖点：

- `GET /health` 返回 `{"status": "ok"}`。
- `POST /research` 默认 offline，返回 JSON payload，包含 `report_markdown`、`findings`、`competitive_matrix`、`critique`、`tool_call_log`、`llm_call_log`、`iterations`。
- `POST /research` 使用 fake `run_research` 时将 `query` 传入 workflow。
- `POST /research` 支持 `preset="live-llm"` 并应用现有 live defaults。
- `POST /research` 不覆盖已存在的 live env 值。
- 空白 query 返回 422。
- 未知 preset 返回 422。
- workflow exception 返回 500 且响应体为安全固定错误，不包含原始 exception 文本。

测试不得访问公网，不得调用真实 LLM。涉及 workflow 的 API 测试优先 monkeypatch `run_research` 返回构造好的 `GraphState`。

## README 更新

README 当前 MVP 输出区新增 API 使用说明：

- API MVP 已实现同步 `POST /research` 和 `GET /health`。
- API 响应与 CLI `--output-json` 对齐，包含 `competitive_matrix`。
- 当前 API MVP 不包含 WebSocket、auth、持久化、后台任务或并发环境隔离。
- 启动示例应说明需要 ASGI server，例如：

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --reload
```

这里 `uvicorn` 是运行示例依赖，不是第一版 package runtime dependency。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_api.py tests/test_cli.py tests/test_graph.py -q
python -m pytest -q
python -m ruff check .
```

Smoke：

```powershell
python -c "from insight_graph.api import app; print(app.title)"
```

期望输出包含：

```text
InsightGraph API
```
