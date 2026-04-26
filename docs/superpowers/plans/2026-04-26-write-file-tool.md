# Write File Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a conservative create-only `write_file` tool for safe cwd-contained text file creation.

**Architecture:** Extend the existing `file_tools.py` module so read/list/write share path containment, snippet normalization, and slug+hash evidence IDs. Register/export the new tool through existing boundaries, then add a low-priority Planner opt-in after read/list to avoid accidental writes when safer collection tools are enabled.

**Tech Stack:** Python 3.13, pathlib, hashlib, json, Pydantic `Evidence`, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/tools/file_tools.py`: add `write_file` and write-specific JSON parsing/suffix validation.
- Modify `src/insight_graph/tools/registry.py`: register `write_file`.
- Modify `src/insight_graph/tools/__init__.py`: export `write_file`.
- Modify `src/insight_graph/agents/planner.py`: add `INSIGHT_GRAPH_USE_WRITE_FILE` opt-in after read/list.
- Modify `tests/test_tools.py`: cover `write_file` behavior, safety cases, registry, package export.
- Modify `tests/test_agents.py`: cover Planner opt-in priority and env isolation.
- Modify `tests/test_graph.py`: clear `INSIGHT_GRAPH_USE_WRITE_FILE` in graph default env cleanup.
- Modify `README.md`: document create-only `write_file` and remove roadmap-only wording for this tool.

---

### Task 1: Add Create-only write_file Tool And Registry Integration

**Files:**
- Modify: `src/insight_graph/tools/file_tools.py`
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing tool tests**

In `tests/test_tools.py`, add `json` near the existing imports:

```python
import hashlib
import importlib
import json
import re
```

Update the tools import to include `write_file`:

```python
from insight_graph.tools import (
    SearchResult,
    ToolRegistry,
    document_reader,
    fetch_url,
    github_search,
    list_directory,
    news_search,
    read_file,
    web_search,
    write_file,
)
```

Update `test_tools_package_exports_readonly_file_tool_callables()`:

```python
def test_tools_package_exports_readonly_file_tool_callables() -> None:
    assert callable(read_file)
    assert callable(list_directory)
    assert callable(write_file)
```

Add these tests after the existing `list_directory` tests:

```python
def test_write_file_creates_verified_docs_evidence(tmp_path, monkeypatch) -> None:
    target_dir = tmp_path / "notes"
    target_dir.mkdir()
    target = target_dir / "Output.md"
    monkeypatch.chdir(tmp_path)

    evidence = write_file(
        json.dumps({"path": "notes/Output.md", "content": "# Output\n\nAlpha   beta."}),
        "s1",
    )

    assert target.read_text(encoding="utf-8") == "# Output\n\nAlpha   beta."
    assert len(evidence) == 1
    assert evidence[0].id == tool_id("write-file", "notes/Output.md")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Output.md"
    assert evidence[0].source_url == target.resolve().as_uri()
    assert evidence[0].snippet == "# Output Alpha beta."
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True
```

```python
def test_write_file_normalizes_newlines_to_lf(tmp_path, monkeypatch) -> None:
    target = tmp_path / "notes.md"
    monkeypatch.chdir(tmp_path)

    evidence = write_file(
        json.dumps({"path": "notes.md", "content": "Line 1\r\nLine 2"}),
        "s1",
    )

    assert len(evidence) == 1
    assert target.read_bytes() == b"Line 1\nLine 2"
```

```python
@pytest.mark.parametrize(
    "query",
    [
        "not-json",
        json.dumps(["path", "content"]),
        json.dumps({"content": "Missing path."}),
        json.dumps({"path": "missing-content.md"}),
        json.dumps({"path": 123, "content": "Bad path."}),
        json.dumps({"path": "bad-content.md", "content": 123}),
        json.dumps({"path": "overwrite.md", "content": "x", "overwrite": True}),
        json.dumps({"path": "append.md", "content": "x", "append": True}),
        json.dumps({"path": "mode.md", "content": "x", "mode": "overwrite"}),
    ],
)
def test_write_file_rejects_invalid_query_shapes(query, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert write_file(query, "s1") == []
```

```python
def test_write_file_rejects_unsafe_or_invalid_targets(tmp_path, monkeypatch) -> None:
    existing = tmp_path / "existing.md"
    existing.write_text("existing", encoding="utf-8")
    (tmp_path / "folder").mkdir()
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert write_file(json.dumps({"path": "existing.md", "content": "new"}), "s1") == []
    assert existing.read_text(encoding="utf-8") == "existing"
    assert write_file(json.dumps({"path": "folder", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "missing/out.md", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "../outside.md", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "unsupported.pdf", "content": "new"}), "s1") == []
    assert write_file(json.dumps({"path": "script.py", "content": "print('no')"}), "s1") == []
    assert write_file(json.dumps({"path": "empty.md", "content": "\n\t   \n"}), "s1") == []
    assert write_file(json.dumps({"path": "large.md", "content": "a" * (64 * 1024 + 1)}), "s1") == []
```

```python
def test_write_file_rejects_malformed_query(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    assert write_file(None, "s1") == []  # type: ignore[arg-type]
```

```python
def test_write_file_hash_prevents_slug_collisions(tmp_path, monkeypatch) -> None:
    nested_dir = tmp_path / "docs" / "foo"
    nested_dir.mkdir(parents=True)
    first = tmp_path / "docs" / "foo-bar.md"
    second = nested_dir / "bar.md"
    monkeypatch.chdir(tmp_path)

    first_evidence = write_file(json.dumps({"path": "docs/foo-bar.md", "content": "First."}), "s1")
    second_evidence = write_file(json.dumps({"path": "docs/foo/bar.md", "content": "Second."}), "s1")

    assert first_evidence[0].id == tool_id("write-file", "docs/foo-bar.md")
    assert second_evidence[0].id == tool_id("write-file", "docs/foo/bar.md")
    assert first_evidence[0].id != second_evidence[0].id
```

Add this test after `test_registry_runs_list_directory_tool()`:

```python
def test_registry_runs_write_file_tool(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run(
        "write_file",
        json.dumps({"path": "sample.md", "content": "Local file evidence."}),
        "s1",
    )

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("write-file", "sample.md")
    assert evidence[0].source_type == "docs"
    assert (tmp_path / "sample.md").read_text(encoding="utf-8") == "Local file evidence."
```

- [ ] **Step 2: Run tool tests and verify RED**

Run:

```powershell
python -m pytest tests/test_tools.py::test_tools_package_exports_readonly_file_tool_callables tests/test_tools.py::test_write_file_creates_verified_docs_evidence tests/test_tools.py::test_write_file_normalizes_newlines_to_lf tests/test_tools.py::test_write_file_rejects_invalid_query_shapes tests/test_tools.py::test_write_file_rejects_unsafe_or_invalid_targets tests/test_tools.py::test_write_file_rejects_malformed_query tests/test_tools.py::test_write_file_hash_prevents_slug_collisions tests/test_tools.py::test_registry_runs_write_file_tool -q
```

Expected: FAIL during import because `write_file` is not exported yet.

- [ ] **Step 3: Implement write_file**

In `src/insight_graph/tools/file_tools.py`, add import:

```python
import json
```

Add constants after `SUPPORTED_READ_SUFFIXES`:

```python
SUPPORTED_WRITE_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}
WRITE_MODE_KEYS = {"overwrite", "append", "mode"}
```

Add `write_file` after `list_directory`:

```python
def write_file(query: str, subtask_id: str = "collect") -> list[Evidence]:
    payload = _parse_write_file_query(query)
    if payload is None:
        return []

    path_text, content = payload
    content_to_write = _normalize_newlines(content)
    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, path_text)
    if path is None or path.exists() or path.is_dir():
        return []
    if path.suffix.lower() not in SUPPORTED_WRITE_SUFFIXES:
        return []
    if not path.parent.is_dir():
        return []

    snippet = _normalize_snippet(content_to_write)
    if not snippet:
        return []

    try:
        if len(content_to_write.encode("utf-8")) > MAX_FILE_BYTES:
            return []
        with path.open("x", encoding="utf-8", newline="\n") as output_file:
            output_file.write(content_to_write)
    except (OSError, UnicodeEncodeError, ValueError):
        return []

    return [
        Evidence(
            id=_evidence_id("write-file", root, path),
            subtask_id=subtask_id,
            title=path.name,
            source_url=path.as_uri(),
            snippet=snippet,
            source_type="docs",
            verified=True,
        )
    ]
```

Add helper before `_resolve_inside_root`:

```python
def _parse_write_file_query(query: str) -> tuple[str, str] | None:
    query_text = _coerce_query(query)
    if query_text is None:
        return None
    try:
        payload = json.loads(query_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    if WRITE_MODE_KEYS.intersection(payload):
        return None
    path = payload.get("path")
    content = payload.get("content")
    if not isinstance(path, str) or not isinstance(content, str):
        return None
    return path, content


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")
```

- [ ] **Step 4: Register and export write_file**

In `src/insight_graph/tools/registry.py`, update the file tools import:

```python
from insight_graph.tools.file_tools import list_directory, read_file, write_file
```

Add registry entry:

```python
            "write_file": write_file,
```

In `src/insight_graph/tools/__init__.py`, update the file tools import:

```python
from insight_graph.tools.file_tools import list_directory, read_file, write_file
```

Update `__all__` to include:

```python
    "write_file",
```

- [ ] **Step 5: Run tool tests and lint**

Run:

```powershell
python -m pytest tests/test_tools.py -q
python -m ruff check src/insight_graph/tools/file_tools.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src/insight_graph/tools/file_tools.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
git commit -m "feat: add create-only write file tool"
```

---

### Task 2: Add Planner Opt-in And Env Isolation

**Files:**
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write failing Planner tests**

In `tests/test_agents.py`, update `clear_llm_env()` and default planner env cleanup to clear:

```python
        "INSIGHT_GRAPH_USE_WRITE_FILE",
```

Add these tests after `test_planner_uses_list_directory_when_enabled()`:

```python
def test_planner_uses_write_file_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request='{"path":"notes.md","content":"Notes."}')

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["write_file"]
```

```python
def test_planner_prefers_read_file_over_write_file(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["read_file"]
```

```python
def test_planner_prefers_list_directory_over_write_file(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request=".")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["list_directory"]
```

Add this focused priority test for document reader over write_file:

```python
def test_planner_prefers_document_reader_over_write_file(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["document_reader"]
```

In `tests/test_graph.py`, update planner env cleanup helper to clear `INSIGHT_GRAPH_USE_WRITE_FILE`.

- [ ] **Step 2: Run agent tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_write_file_when_enabled tests/test_agents.py::test_planner_prefers_read_file_over_write_file tests/test_agents.py::test_planner_prefers_list_directory_over_write_file tests/test_agents.py::test_planner_prefers_document_reader_over_write_file -q
```

Expected: at least write_file opt-in test fails because Planner does not yet select `write_file`.

- [ ] **Step 3: Implement Planner opt-in**

Update `_collection_tool_name()` in `src/insight_graph/agents/planner.py`:

```python
def _collection_tool_name() -> str:
    if _is_truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"):
        return "web_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"):
        return "github_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_NEWS_SEARCH"):
        return "news_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_DOCUMENT_READER"):
        return "document_reader"
    if _is_truthy_env("INSIGHT_GRAPH_USE_READ_FILE"):
        return "read_file"
    if _is_truthy_env("INSIGHT_GRAPH_USE_LIST_DIRECTORY"):
        return "list_directory"
    if _is_truthy_env("INSIGHT_GRAPH_USE_WRITE_FILE"):
        return "write_file"
    return "mock_search"
```

- [ ] **Step 4: Run agent/graph tests and lint**

Run:

```powershell
python -m pytest tests/test_agents.py tests/test_graph.py -q
python -m ruff check src/insight_graph/agents/planner.py tests/test_agents.py tests/test_graph.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add src/insight_graph/agents/planner.py tests/test_agents.py tests/test_graph.py
git commit -m "feat: let planner opt into write file"
```

---

### Task 3: Document write_file Opt-in And Current Scope

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update opt-in documentation**

Near the existing local file tool opt-in paragraph, extend the wording to include:

```markdown
`INSIGHT_GRAPH_USE_WRITE_FILE=1` 将用户请求作为 JSON 写入请求处理，格式为 `{"path":"notes.md","content":"Notes."}`。第一版 `write_file` 只会在 cwd 内创建新的安全文本文件，不覆盖已有文件、不自动创建父目录、不执行代码；若同时启用 read/list 工具，Planner 优先选择只读工具。
```

Add a config table row after `INSIGHT_GRAPH_USE_LIST_DIRECTORY`:

```markdown
| `INSIGHT_GRAPH_USE_WRITE_FILE` | `1` / `true` / `yes` 时 Planner collect subtask 使用 create-only `write_file`；搜索工具、`document_reader`、`read_file` 和 `list_directory` 优先 | 未启用 |
```

- [ ] **Step 2: Update tools and flow references**

Update the Tool Registry diagram to list `write_file` after `list_directory`.

Update the built-in tools row to:

```markdown
| `read_file` / `list_directory` / `write_file` | 当前支持 cwd 内只读安全文本读取、一层目录列表，以及 create-only 安全文本写入 |
```

Keep this standalone sentence:

```markdown
`code_execute` 计划用于沙箱 Python 代码执行和表格计算，当前尚未实现，将单独设计。
```

Update the Collector multi-source bullet to include `write_file`, while preserving the wording that Planner currently selects one primary collection tool by opt-in priority.

- [ ] **Step 3: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_write_file_when_enabled tests/test_tools.py::test_registry_runs_write_file_tool -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document write file opt in"
```

---

### Task 4: Final Verification And CLI Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_tools.py tests/test_agents.py tests/test_graph.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full tests and lint**

Run:

```powershell
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 3: Reinstall editable checkout for CLI smoke**

Run:

```powershell
python -m pip install -e .
```

Expected: command succeeds and installs the current checkout.

- [ ] **Step 4: Run default CLI smoke**

Run and parse JSON tool name:

```powershell
Remove-Item Env:\INSIGHT_GRAPH_USE_WRITE_FILE -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_READ_FILE -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_LIST_DIRECTORY -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_DOCUMENT_READER -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json | python -c "import sys,json; data=json.load(sys.stdin); print(data['tool_call_log'][0]['tool_name'])"
```

Expected output: `mock_search`.

- [ ] **Step 5: Run write_file opt-in CLI smoke**

Run and parse JSON tool name:

```powershell
$env:INSIGHT_GRAPH_USE_WRITE_FILE = "1"; Remove-Item Env:\INSIGHT_GRAPH_USE_READ_FILE -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_LIST_DIRECTORY -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_DOCUMENT_READER -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; Remove-Item "write-file-smoke.md" -ErrorAction SilentlyContinue; python -m insight_graph.cli research '{"path":"write-file-smoke.md","content":"Write file smoke."}' --output-json | python -c "import sys,json; data=json.load(sys.stdin); print(data['tool_call_log'][0]['tool_name'])"
```

Expected output: `write_file`.

- [ ] **Step 6: Verify smoke output file and cleanup**

Run:

```powershell
Get-Content "write-file-smoke.md"; Remove-Item "write-file-smoke.md"; Remove-Item Env:\INSIGHT_GRAPH_USE_WRITE_FILE -ErrorAction SilentlyContinue
```

Expected output includes `Write file smoke.` and the file is removed.

- [ ] **Step 7: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
