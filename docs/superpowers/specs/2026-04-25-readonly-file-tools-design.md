# Read-only File Tools 设计

## 目标

为 InsightGraph 增加第一版只读本地文件工具：`read_file` 和 `list_directory`，补齐 README 蓝图中的本地文件浏览能力。

第一版保持 deterministic/offline，只允许读取当前工作目录内的安全文本文件和列出当前工作目录内的一层目录内容。不写文件、不递归扫描、不执行代码。

## 非目标

- 不实现 `write_file`。
- 不实现递归目录遍历、全文检索或 glob 搜索。
- 不读取工作目录外路径。
- 不读取二进制文件或超大文件。
- 不解析 PDF/HTML/DOCX。
- 不引入新依赖。
- 不改变默认 CLI 行为；默认仍使用 `mock_search`。

## 工具接口

新增模块：

```python
src/insight_graph/tools/file_tools.py
```

公开函数：

```python
def read_file(query: str, subtask_id: str = "collect") -> list[Evidence]
def list_directory(query: str, subtask_id: str = "collect") -> list[Evidence]
```

两个函数都返回 `list[Evidence]`，以便直接接入现有 `ToolRegistry` 和 Executor。

## 路径安全

两个工具都使用当前工作目录作为根：

```python
root = Path.cwd().resolve()
candidate = Path(query)
if not candidate.is_absolute():
    candidate = root / candidate
candidate = candidate.resolve()
if not candidate.is_relative_to(root):
    return []
```

绝对路径也必须通过同一 containment 检查；如果不在 root 内，返回空列表。

## read_file 行为

`read_file(query, subtask_id)`：

- `query` 是本地文件路径。
- 只支持以下后缀：`.txt`、`.md`、`.markdown`、`.py`、`.json`、`.toml`、`.yaml`、`.yml`。
- 缺失路径、目录路径、工作区外路径、不支持后缀、读取错误、UTF-8 解码错误、空归一化内容都返回 `[]`。
- 文件大小上限为 64 KiB；超过上限返回 `[]`。
- 合法文件返回 1 条 verified `Evidence`。
- `source_type="docs"`。
- `source_url` 使用 `file://` URI。
- `title` 使用文件名。
- `snippet` 是归一化空白后的前 500 个字符。
- Evidence ID 使用：`read-file-<relative-path-with-extension-slug>-<hash8>`。
- `hash8` 是 POSIX 相对路径字符串的 SHA-1 前 8 位。

## list_directory 行为

`list_directory(query, subtask_id)`：

- `query` 是本地目录路径。
- 空字符串或 `.` 表示当前工作目录。
- 缺失路径、文件路径、工作区外路径、读取错误返回 `[]`。
- 只列出一层目录内容，不递归。
- 最多输出 50 个条目；按名称小写排序。
- 每个条目格式为：`name/` 表示目录，`name` 表示文件。
- 合法目录返回 1 条 verified `Evidence`。
- `source_type="docs"`。
- `source_url` 使用目录 `file://` URI。
- `title` 为 `Directory listing: <relative path>`；根目录使用 `Directory listing: .`。
- `snippet` 是条目用 `\n` 拼接后的前 500 个字符。
- 空目录返回 1 条 evidence，snippet 为 `(empty directory)`。
- Evidence ID 使用：`list-directory-<relative-path-slug>-<hash8>`；根目录 slug 为 `root`，`hash8` 是 POSIX 相对路径字符串的 SHA-1 前 8 位，根目录使用 `.` 作为 hash 输入。

## ToolRegistry 集成

`ToolRegistry` 注册新工具：

```python
"read_file": read_file
"list_directory": list_directory
```

这样 Executor 无需改动即可执行 Planner 或手动创建的工具调用，并继续记录 `ToolCallRecord`。

## Package Export

`insight_graph.tools` 导出：

```python
from insight_graph.tools import read_file, list_directory
```

## Planner Opt-in

新增环境变量：

```text
INSIGHT_GRAPH_USE_READ_FILE=1|true|yes
INSIGHT_GRAPH_USE_LIST_DIRECTORY=1|true|yes
```

Planner 采集工具选择优先级：

1. `INSIGHT_GRAPH_USE_WEB_SEARCH` -> `web_search`
2. `INSIGHT_GRAPH_USE_GITHUB_SEARCH` -> `github_search`
3. `INSIGHT_GRAPH_USE_NEWS_SEARCH` -> `news_search`
4. `INSIGHT_GRAPH_USE_DOCUMENT_READER` -> `document_reader`
5. `INSIGHT_GRAPH_USE_READ_FILE` -> `read_file`
6. `INSIGHT_GRAPH_USE_LIST_DIRECTORY` -> `list_directory`
7. 默认 `mock_search`

这个优先级保持现有搜索与文档 reader opt-in 行为不变，并让更通用的文件工具排在专用文档 reader 之后。

## README 更新

在 Search Provider / evidence acquisition 配置附近补充只读文件工具：

- `INSIGHT_GRAPH_USE_READ_FILE` 读取 cwd 内安全文本文件。
- `INSIGHT_GRAPH_USE_LIST_DIRECTORY` 列出 cwd 内目录的一层内容。
- 明确第一版不写文件、不递归、不读取工作区外路径。
- `write_file` 和 `code_execute` 留作后续单独设计。

## 测试策略

全部测试离线运行。

覆盖点：

- `read_file()` 读取 cwd 内 Markdown 或 Python 文件并返回 1 条 verified docs evidence。
- `read_file()` 拒绝缺失路径、目录、不支持后缀、工作区外路径、超大文件、无效 UTF-8、空内容。
- `read_file()` evidence ID 对相同 slug 不同路径不碰撞。
- `list_directory()` 列出 cwd 内目录的一层内容，目录带 `/`，文件不带 `/`。
- `list_directory()` 对空目录返回 `(empty directory)`。
- `list_directory()` 拒绝缺失路径、文件路径、工作区外路径。
- `insight_graph.tools` 导出可调用 `read_file` 和 `list_directory`。
- `ToolRegistry().run("read_file", "README.md", "s1")` 执行新工具。
- `ToolRegistry().run("list_directory", ".", "s1")` 执行新工具。
- Planner 默认仍返回 `mock_search`。
- `INSIGHT_GRAPH_USE_READ_FILE=1` 时 Planner 返回 `read_file`。
- `INSIGHT_GRAPH_USE_LIST_DIRECTORY=1` 时 Planner 返回 `list_directory`。
- `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` 与 read/list opt-in 同时存在时 Planner 返回 `document_reader`。
- 更高优先级搜索工具仍优先。

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

Read file opt-in smoke：

```powershell
$env:INSIGHT_GRAPH_USE_READ_FILE = "1"
python -m insight_graph.cli research "README.md" --output-json
```

List directory opt-in smoke：

```powershell
$env:INSIGHT_GRAPH_USE_LIST_DIRECTORY = "1"
python -m insight_graph.cli research "." --output-json
```

期望：默认 smoke 使用 `mock_search`；read/list opt-in JSON 的 `tool_call_log[0].tool_name` 分别为 `read_file` 和 `list_directory`。
