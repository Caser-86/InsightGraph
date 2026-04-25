# News Search Tool 设计

## 目标

为 InsightGraph 增加第一版 `news_search` 工具，补齐 README 蓝图中已经列出的新闻与公告检索能力。

第一版保持 deterministic/offline，不访问新闻网站、搜索引擎或第三方 API。它用于验证工具注册、Planner opt-in、Executor 执行、tool call log、relevance filtering 和报告引用链路，为后续 live news provider 打基础。

## 非目标

- 不调用新闻 API、RSS feed、DuckDuckGo news 或真实网页搜索。
- 不引入新闻 provider 配置、API key、rate limit、分页、排序或 live error handling。
- 不改变默认 CLI 行为；默认仍使用 `mock_search`。
- 不改变 `web_search` 或 `github_search` 的现有优先级和行为。
- 不新增强类型枚举；继续使用 `Evidence.source_type` 的字符串能力。

## 工具接口

新增模块：

```python
src/insight_graph/tools/news_search.py
```

公开函数：

```python
def news_search(query: str, subtask_id: str = "collect") -> list[Evidence]
```

行为：

- 返回 deterministic `Evidence` 列表。
- 所有 evidence `verified=True`。
- `subtask_id` 使用调用方传入值。
- 不使用 `query` 过滤结果；第一版只保证稳定新闻/公告 evidence。
- `source_type` 使用可读字符串，例如 `news` 和 `official_announcement`。

## 默认证据

第一版返回 3 条新闻/公告类 evidence：

- `news-github-copilot-changelog`：GitHub Copilot product changelog，`https://github.blog/changelog/`，`source_type="news"`
- `news-openai-codex-update`：OpenAI Codex product update，`https://openai.com/index/introducing-codex/`，`source_type="official_announcement"`
- `news-cursor-changelog`：Cursor product changelog，`https://www.cursor.com/changelog`，`source_type="news"`

每条 evidence 的 `id` 必须稳定、可读，避免测试和报告引用漂移。

## ToolRegistry 集成

`ToolRegistry` 注册新工具：

```python
"news_search": news_search
```

这样 Executor 无需改动即可执行 Planner 产生的 `news_search` subtask，并继续记录 `ToolCallRecord`。

## Package Export

`insight_graph.tools` 导出 `news_search`，保持与 `fetch_url`、`github_search`、`web_search` 类似的可导入体验：

```python
from insight_graph.tools import news_search
```

## Planner Opt-in

新增环境变量：

```text
INSIGHT_GRAPH_USE_NEWS_SEARCH=1|true|yes
```

Planner 采集工具选择优先级：

1. 如果 `INSIGHT_GRAPH_USE_WEB_SEARCH` 为 truthy，使用 `web_search`。
2. 否则如果 `INSIGHT_GRAPH_USE_GITHUB_SEARCH` 为 truthy，使用 `github_search`。
3. 否则如果 `INSIGHT_GRAPH_USE_NEWS_SEARCH` 为 truthy，使用 `news_search`。
4. 否则使用默认 `mock_search`。

这个优先级保持现有 live web search 和 GitHub opt-in 行为不变，并让 news search 成为单独 opt-in 路径。

## README 更新

在 Search Provider / evidence acquisition 配置附近补充 news search：

- `INSIGHT_GRAPH_USE_NEWS_SEARCH` 默认未启用。
- 第一版 deterministic/offline，不访问新闻 API 或公网。
- 如果同时启用 `INSIGHT_GRAPH_USE_WEB_SEARCH`、`INSIGHT_GRAPH_USE_GITHUB_SEARCH` 和 `INSIGHT_GRAPH_USE_NEWS_SEARCH`，Planner 使用优先级最高的已启用工具。
- 后续 live news provider 会单独设计。

## 测试策略

全部测试离线运行，不访问公网。

覆盖点：

- `news_search()` 返回 3 条 verified 新闻/公告 evidence。
- `news_search()` 尊重传入 `subtask_id`。
- `insight_graph.tools` 导出可调用 `news_search`。
- `ToolRegistry().run("news_search", "AI coding agent funding", "s1")` 执行新工具。
- Planner 默认仍返回 `mock_search`。
- `INSIGHT_GRAPH_USE_NEWS_SEARCH=1` 时 Planner 返回 `news_search`。
- `INSIGHT_GRAPH_USE_GITHUB_SEARCH=1` 和 news opt-in 同时存在时 Planner 返回 `github_search`。
- `INSIGHT_GRAPH_USE_WEB_SEARCH=1` 和 news opt-in 同时存在时 Planner 返回 `web_search`。
- Collector 能通过 Planner 生成的 `news_search` 收集 evidence，并记录 `tool_call_log[0].tool_name == "news_search"`。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_tools.py tests/test_agents.py -q
python -m pytest -q
python -m ruff check .
```

默认 CLI smoke：

```powershell
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

News opt-in smoke：

```powershell
$env:INSIGHT_GRAPH_USE_NEWS_SEARCH = "1"
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

期望：默认 smoke 仍使用 mock evidence；news opt-in JSON 的 `tool_call_log[0].tool_name` 为 `news_search`。
