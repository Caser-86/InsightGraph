# Document Reader Tool 设计

## 目标

为 InsightGraph 增加第一版 `document_reader` 工具，补齐 README 蓝图中已经列出的本地文档读取能力。

第一版保持 deterministic/offline，只读取当前工作目录内的本地 text/Markdown 文档，不访问公网、不解析 PDF、不抓取 HTML。它为后续 PDF/HTML/分页/语义检索版 `document_reader` 打基础，同时立即让工具链具备安全的本地文档 evidence 入口。

## 非目标

- 不读取 PDF、HTML、DOCX 或远程 URL。
- 不做分页读取、chunk ranking、embedding、语义检索或全文索引。
- 不引入新依赖。
- 不改变默认 CLI 行为；默认仍使用 `mock_search`。
- 不改变现有 `web_search`、`github_search`、`news_search` 的优先级和行为。

## 工具接口

新增模块：

```python
src/insight_graph/tools/document_reader.py
```

公开函数：

```python
def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]
```

行为：

- `query` 是本地文档路径。
- 支持后缀：`.txt`、`.md`、`.markdown`。
- 路径解析基于当前工作目录：`Path.cwd()`。
- 使用 `Path.resolve()` 计算目标路径，并确认目标路径在当前工作目录内。
- 禁止绝对路径越界、`..` 逃逸、目录路径、缺失文件和不支持后缀。
- 无法读取、解码失败或不合法时返回空列表，不抛出异常给 Executor。
- 合法文件返回 1 条 verified `Evidence`。
- `Evidence.source_type="docs"`。
- `source_url` 使用稳定的 `file://` URI。
- `title` 使用文件名。
- `snippet` 是文件文本归一化空白后的前 500 个字符。

## 路径安全

必须通过以下规则保证工具不会读取工作区外文件：

```python
root = Path.cwd().resolve()
candidate = (root / query).resolve()
if not candidate.is_relative_to(root):
    return []
```

绝对路径也必须经过同一套检查；如果绝对路径不在 `root` 内，返回空列表。

## Evidence ID

Evidence ID 应稳定且可读：

```text
document-<relative-path-with-extension-slug>-<hash8>
```

Slug 规则：相对 `Path.cwd().resolve()` 的完整路径转 POSIX 字符串并保留后缀，小写，路径分隔符和非字母数字字符替换为 `-`，去掉首尾 `-`；空值 fallback 为 `document`。

`hash8` 是 POSIX 相对路径字符串的 SHA-1 digest 前 8 位十六进制字符，用于避免不同路径 slug 相同导致 citation/reference key 冲突。

示例：

```text
docs/Market Report.md -> document-docs-market-report-md-<hash8>
sample.md -> document-sample-md-<hash8>
docs/report.md -> document-docs-report-md-<hash8>
docs/report.txt -> document-docs-report-txt-<hash8>
```

## ToolRegistry 集成

`ToolRegistry` 注册新工具：

```python
"document_reader": document_reader
```

这样 Executor 无需改动即可执行 Planner 产生的 `document_reader` subtask，并继续记录 `ToolCallRecord`。

## Package Export

`insight_graph.tools` 导出 `document_reader`，保持与其他工具类似的可导入体验：

```python
from insight_graph.tools import document_reader
```

## Planner Opt-in

新增环境变量：

```text
INSIGHT_GRAPH_USE_DOCUMENT_READER=1|true|yes
```

Planner 采集工具选择优先级：

1. 如果 `INSIGHT_GRAPH_USE_WEB_SEARCH` 为 truthy，使用 `web_search`。
2. 否则如果 `INSIGHT_GRAPH_USE_GITHUB_SEARCH` 为 truthy，使用 `github_search`。
3. 否则如果 `INSIGHT_GRAPH_USE_NEWS_SEARCH` 为 truthy，使用 `news_search`。
4. 否则如果 `INSIGHT_GRAPH_USE_DOCUMENT_READER` 为 truthy，使用 `document_reader`。
5. 否则使用默认 `mock_search`。

这个优先级保持现有搜索 opt-in 行为不变，并让 document reader 成为单独 opt-in 路径。

## README 更新

在 Search Provider / evidence acquisition 配置附近补充 document reader：

- `INSIGHT_GRAPH_USE_DOCUMENT_READER` 默认未启用。
- 第一版只读取当前工作目录内的 `.txt`、`.md`、`.markdown` 本地文件。
- 不读取工作目录外文件，不读取 URL，不解析 PDF/HTML。
- 如果同时启用搜索工具和 document reader，Planner 使用优先级最高的已启用工具。

## 测试策略

全部测试离线运行，不访问公网。

覆盖点：

- `document_reader()` 读取当前工作目录内 Markdown 文件并返回 1 条 verified docs evidence。
- `document_reader()` 归一化 snippet 空白并限制长度。
- `document_reader()` 对缺失文件、目录、不支持后缀、工作区外路径和 UTF-8 解码失败返回空列表。
- `document_reader()` 使用包含后缀的 POSIX 相对路径 slug 和 SHA-1 hash 后缀生成稳定且 collision-resistant 的 evidence ID。
- `insight_graph.tools` 导出可调用 `document_reader`。
- `ToolRegistry().run("document_reader", "docs/sample.md", "s1")` 执行新工具。
- Planner 默认仍返回 `mock_search`。
- `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` 时 Planner 返回 `document_reader`。
- `INSIGHT_GRAPH_USE_NEWS_SEARCH=1` 和 document reader opt-in 同时存在时 Planner 返回 `news_search`。
- `INSIGHT_GRAPH_USE_GITHUB_SEARCH=1` 和 document reader opt-in 同时存在时 Planner 返回 `github_search`。
- `INSIGHT_GRAPH_USE_WEB_SEARCH=1` 和 document reader opt-in 同时存在时 Planner 返回 `web_search`。

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

Document reader opt-in smoke：

```powershell
$env:INSIGHT_GRAPH_USE_DOCUMENT_READER = "1"
python -m insight_graph.cli research "README.md" --output-json
```

期望：默认 smoke 仍使用 mock evidence；document reader opt-in JSON 的 `tool_call_log[0].tool_name` 为 `document_reader`。
