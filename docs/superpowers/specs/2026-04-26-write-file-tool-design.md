# Write File Tool 设计

## 目标

为 InsightGraph 增加第一版安全本地写文件工具：`write_file`。

第一版只支持在当前工作目录内创建新的安全文本文件，不覆盖已有文件、不自动创建父目录、不执行代码。它用于保存研究产物、临时 notes 或后续工具可读取的本地文本素材，而不是编辑用户已有文件。

## 非目标

- 不覆盖已有文件。
- 不追加、patch 或删除文件。
- 不自动创建父目录。
- 不写入工作目录外路径。
- 不写入二进制内容。
- 不解析或生成 PDF/HTML/DOCX。
- 不执行写入后的文件。
- 不改变默认 CLI 行为；默认仍使用 `mock_search`。

## 工具接口

复用现有 `src/insight_graph/tools/file_tools.py`，新增公开函数：

```python
def write_file(query: str, subtask_id: str = "collect") -> list[Evidence]
```

`query` 是 JSON 字符串，第一版仅接受：

```json
{
  "path": "notes/output.md",
  "content": "Research notes for a local study."
}
```

无效 JSON、非 object JSON、缺失字段、非字符串字段，或包含 `overwrite`、`append`、`mode` 等写入模式字段时，都返回 `[]`。

## 路径安全

`write_file` 使用当前工作目录作为根，沿用只读文件工具的 containment 规则：

```python
root = Path.cwd().resolve()
candidate = Path(path)
if not candidate.is_absolute():
    candidate = root / candidate
candidate = candidate.resolve()
if not candidate.is_relative_to(root):
    return []
```

绝对路径也必须位于 root 内。路径解析失败、越界路径、目标路径是目录、目标路径已存在、父目录不存在或父目录解析后不在 root 内都返回 `[]`。

## 写入限制

`write_file(query, subtask_id)`：

- 只支持以下后缀：`.txt`、`.md`、`.markdown`、`.json`、`.toml`、`.yaml`、`.yml`。
- 不支持 `.py`，避免把该工具变成代码生成/执行链路的一部分。
- `content` 必须是字符串。
- `content.encode("utf-8")` 后不得超过 64 KiB。
- whitespace-normalized content 为空时返回 `[]`。
- 使用 `path.open("x", encoding="utf-8", newline="\n")` 创建文件，确保已有文件不会被覆盖。
- 捕获 `OSError`、`UnicodeEncodeError`、`ValueError` 并返回 `[]`。
- 写入成功返回 1 条 verified `Evidence`。

## Evidence 行为

写入成功后的 `Evidence` 字段：

- `id="write-file-<relative-path-with-extension-slug>-<hash8>"`
- `hash8` 是 POSIX 相对路径字符串的 SHA-1 前 8 位。
- `subtask_id` 使用传入值。
- `title` 使用文件名。
- `source_url` 使用 `file://` URI。
- `snippet` 是写入内容 whitespace-normalized 后的前 500 字符。
- `source_type="docs"`
- `verified=True`

`write_file` 不读取写回文件内容来生成 evidence；Evidence 直接来自 validated input content。

## ToolRegistry 集成

`ToolRegistry` 注册新工具：

```python
"write_file": write_file
```

这样 Executor 无需改动即可执行显式工具调用，并继续记录 `ToolCallRecord`。

## Package Export

`insight_graph.tools` 导出：

```python
from insight_graph.tools import write_file
```

## Planner Opt-in

新增环境变量：

```text
INSIGHT_GRAPH_USE_WRITE_FILE=1|true|yes
```

Planner 采集工具选择优先级：

1. `INSIGHT_GRAPH_USE_WEB_SEARCH` -> `web_search`
2. `INSIGHT_GRAPH_USE_GITHUB_SEARCH` -> `github_search`
3. `INSIGHT_GRAPH_USE_NEWS_SEARCH` -> `news_search`
4. `INSIGHT_GRAPH_USE_DOCUMENT_READER` -> `document_reader`
5. `INSIGHT_GRAPH_USE_READ_FILE` -> `read_file`
6. `INSIGHT_GRAPH_USE_LIST_DIRECTORY` -> `list_directory`
7. `INSIGHT_GRAPH_USE_WRITE_FILE` -> `write_file`
8. 默认 `mock_search`

`write_file` 排在只读工具之后，避免用户同时启用读取/列目录时意外写入。默认行为保持不变。

## README 更新

README 更新当前工具表和 opt-in 说明：

- `INSIGHT_GRAPH_USE_WRITE_FILE` 只创建 cwd 内新安全文本文件。
- 默认不覆盖已有文件，不自动创建父目录，不执行代码。
- `code_execute` 仍是后续单独设计。
- `read_file` / `list_directory` / `write_file` 都属于本地文件工具；其中 `write_file` 是 create-only MVP。

## 测试策略

全部测试离线运行。

覆盖点：

- `write_file()` 使用合法 JSON 在 cwd 内创建新 Markdown 文件并返回 1 条 verified docs evidence。
- 文件实际写入 UTF-8 内容，使用 LF newline。
- `write_file()` 拒绝无效 JSON、非 object JSON、缺失 `path`、缺失 `content`、非字符串字段。
- `write_file()` 拒绝已有文件、目录路径、缺失父目录、工作区外路径、不支持后缀、`.py` 后缀、超大内容、空 normalized content。
- `write_file()` evidence ID 对相同 slug 不同路径不碰撞。
- `write_file()` 对 malformed non-string query 返回 `[]`。
- `insight_graph.tools` 导出可调用 `write_file`。
- `ToolRegistry().run("write_file", json.dumps({"path": "notes.md", "content": "Local notes."}), "s1")` 执行新工具。
- Planner 默认仍返回 `mock_search`。
- `INSIGHT_GRAPH_USE_WRITE_FILE=1` 时 Planner 返回 `write_file`。
- read/list opt-in 与 write opt-in 同时存在时，Planner 仍返回 `read_file` 或 `list_directory`。
- 更高优先级搜索、GitHub、news、document reader 仍优先。
- Graph 默认测试清理 `INSIGHT_GRAPH_USE_WRITE_FILE`，避免 ambient env 影响。

## 验证

实现完成后运行：

```powershell
python -m pytest tests/test_tools.py tests/test_agents.py tests/test_graph.py -q
python -m pytest -q
python -m ruff check .
```

默认 CLI smoke：

```powershell
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Write file opt-in smoke：

```powershell
$env:INSIGHT_GRAPH_USE_WRITE_FILE = "1"
Remove-Item "write-file-smoke.md" -ErrorAction SilentlyContinue
python -m insight_graph.cli research '{"path":"write-file-smoke.md","content":"Write file smoke."}' --output-json
```

期望：默认 smoke 使用 `mock_search`；write opt-in JSON 的 `tool_call_log[0].tool_name` 为 `write_file`，并在 cwd 内创建目标文件。
