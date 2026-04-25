# Read-only File Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe offline `read_file` and `list_directory` tools for current-working-directory local file browsing.

**Architecture:** Implement both tools in one focused `file_tools.py` module that shares path containment, slug/hash ID generation, and text normalization helpers. Register/export the tools through existing `ToolRegistry` boundaries, then add Planner opt-ins after `document_reader` so current search/document behavior stays stable.

**Tech Stack:** Python 3.13, pathlib, hashlib, regex via stdlib `re`, Pydantic `Evidence`, pytest, ruff.

---

## File Structure

- Create `src/insight_graph/tools/file_tools.py`: read-only local file and directory listing tools.
- Modify `src/insight_graph/tools/registry.py`: register `read_file` and `list_directory`.
- Modify `src/insight_graph/tools/__init__.py`: export `read_file` and `list_directory`.
- Modify `src/insight_graph/agents/planner.py`: add `INSIGHT_GRAPH_USE_READ_FILE` and `INSIGHT_GRAPH_USE_LIST_DIRECTORY` opt-ins.
- Modify `tests/test_tools.py`: cover file tools behavior, safety cases, registry, package exports.
- Modify `tests/test_agents.py`: cover Planner opt-in priority.
- Modify `tests/test_graph.py`: isolate the new Planner env flags in graph default tests.
- Modify `README.md`: document read-only file tool opt-ins and current scope.

---

### Task 1: Add Read-only File Tools And Registry Integration

**Files:**
- Create: `src/insight_graph/tools/file_tools.py`
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing tool tests**

In `tests/test_tools.py`, add imports for `hashlib` and `re` near the top:

```python
import hashlib
import importlib
import re
```

Update the tools import to include `list_directory` and `read_file`:

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
)
```

Add this test helper after imports:

```python
def tool_id(prefix: str, relative_path: str, slug_input: str | None = None) -> str:
    digest = hashlib.sha1(relative_path.encode("utf-8")).hexdigest()[:8]
    value = slug_input if slug_input is not None else relative_path
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "root"
    return f"{prefix}-{slug}-{digest}"
```

Add this test after `test_tools_package_exports_document_reader_callable()`:

```python
def test_tools_package_exports_readonly_file_tool_callables() -> None:
    assert callable(read_file)
    assert callable(list_directory)
```

Add these tests after the existing document reader tests:

```python
def test_read_file_returns_verified_docs_evidence(tmp_path, monkeypatch) -> None:
    document = tmp_path / "docs" / "Notes.md"
    document.parent.mkdir()
    document.write_text("# Notes\n\nAlpha   beta.\nGamma", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = read_file("docs/Notes.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("read-file", "docs/Notes.md")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Notes.md"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == "# Notes Alpha beta. Gamma"
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True
```

```python
def test_read_file_rejects_unsafe_or_invalid_files(tmp_path, monkeypatch) -> None:
    (tmp_path / "unsupported.bin").write_bytes(b"data")
    (tmp_path / "bad.md").write_bytes(b"\xff\xfe\xfa")
    (tmp_path / "empty.md").write_text("\n\t   \n", encoding="utf-8")
    (tmp_path / "large.md").write_text("a" * (64 * 1024 + 1), encoding="utf-8")
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert read_file("missing.md", "s1") == []
    assert read_file(".", "s1") == []
    assert read_file("unsupported.bin", "s1") == []
    assert read_file("bad.md", "s1") == []
    assert read_file("empty.md", "s1") == []
    assert read_file("large.md", "s1") == []
    assert read_file("../outside.md", "s1") == []
```

```python
def test_read_file_hash_prevents_slug_collisions(tmp_path, monkeypatch) -> None:
    nested_dir = tmp_path / "docs" / "foo"
    nested_dir.mkdir(parents=True)
    first = tmp_path / "docs" / "foo-bar.md"
    second = nested_dir / "bar.md"
    first.write_text("First.", encoding="utf-8")
    second.write_text("Second.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    first_evidence = read_file("docs/foo-bar.md", "s1")
    second_evidence = read_file("docs/foo/bar.md", "s1")

    assert first_evidence[0].id == tool_id("read-file", "docs/foo-bar.md")
    assert second_evidence[0].id == tool_id("read-file", "docs/foo/bar.md")
    assert first_evidence[0].id != second_evidence[0].id
```

```python
def test_list_directory_returns_one_level_listing(tmp_path, monkeypatch) -> None:
    target = tmp_path / "docs"
    target.mkdir()
    (target / "b.md").write_text("b", encoding="utf-8")
    (target / "A.txt").write_text("a", encoding="utf-8")
    (target / "nested").mkdir()
    monkeypatch.chdir(tmp_path)

    evidence = list_directory("docs", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("list-directory", "docs")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Directory listing: docs"
    assert evidence[0].source_url == target.resolve().as_uri()
    assert evidence[0].snippet == "A.txt\nb.md\nnested/"
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True
```

```python
def test_list_directory_handles_root_and_empty_directory(tmp_path, monkeypatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(tmp_path)

    root_evidence = list_directory(".", "s1")
    empty_evidence = list_directory("empty", "s1")

    assert root_evidence[0].id == tool_id("list-directory", ".", "root")
    assert root_evidence[0].title == "Directory listing: ."
    assert empty_evidence[0].snippet == "(empty directory)"
```

```python
def test_list_directory_rejects_invalid_paths(tmp_path, monkeypatch) -> None:
    (tmp_path / "file.md").write_text("file", encoding="utf-8")
    (tmp_path.parent / "outside").mkdir(exist_ok=True)
    monkeypatch.chdir(tmp_path)

    assert list_directory("missing", "s1") == []
    assert list_directory("file.md", "s1") == []
    assert list_directory("../outside", "s1") == []
```

Add these tests after `test_registry_runs_document_reader_tool()`:

```python
def test_registry_runs_read_file_tool(tmp_path, monkeypatch) -> None:
    document = tmp_path / "sample.md"
    document.write_text("Local file evidence.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run("read_file", "sample.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == tool_id("read-file", "sample.md")
    assert evidence[0].source_type == "docs"
```

```python
def test_registry_runs_list_directory_tool(tmp_path, monkeypatch) -> None:
    (tmp_path / "sample.md").write_text("Local file evidence.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run("list_directory", ".", "s1")

    assert len(evidence) == 1
    assert "sample.md" in evidence[0].snippet
    assert evidence[0].source_type == "docs"
```

- [ ] **Step 2: Run tool tests and verify RED**

Run:

```powershell
python -m pytest tests/test_tools.py::test_tools_package_exports_readonly_file_tool_callables tests/test_tools.py::test_read_file_returns_verified_docs_evidence tests/test_tools.py::test_read_file_rejects_unsafe_or_invalid_files tests/test_tools.py::test_read_file_hash_prevents_slug_collisions tests/test_tools.py::test_list_directory_returns_one_level_listing tests/test_tools.py::test_list_directory_handles_root_and_empty_directory tests/test_tools.py::test_list_directory_rejects_invalid_paths tests/test_tools.py::test_registry_runs_read_file_tool tests/test_tools.py::test_registry_runs_list_directory_tool -q
```

Expected: FAIL during import because `read_file` and `list_directory` are not exported yet.

- [ ] **Step 3: Implement file tools**

Create `src/insight_graph/tools/file_tools.py`:

```python
import hashlib
import re
from pathlib import Path

from insight_graph.state import Evidence

SUPPORTED_READ_SUFFIXES = {
    ".txt",
    ".md",
    ".markdown",
    ".py",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
}
MAX_FILE_BYTES = 64 * 1024
MAX_SNIPPET_CHARS = 500
MAX_DIRECTORY_ENTRIES = 50


def read_file(query: str, subtask_id: str = "collect") -> list[Evidence]:
    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, query)
    if path is None or not path.is_file() or path.suffix.lower() not in SUPPORTED_READ_SUFFIXES:
        return []
    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            return []
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    snippet = _normalize_snippet(text)
    if not snippet:
        return []

    return [
        Evidence(
            id=_evidence_id("read-file", root, path),
            subtask_id=subtask_id,
            title=path.name,
            source_url=path.as_uri(),
            snippet=snippet,
            source_type="docs",
            verified=True,
        )
    ]


def list_directory(query: str, subtask_id: str = "collect") -> list[Evidence]:
    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, query or ".")
    if path is None or not path.is_dir():
        return []
    try:
        entries = sorted(path.iterdir(), key=lambda item: item.name.lower())
    except OSError:
        return []

    entry_names = [f"{entry.name}/" if entry.is_dir() else entry.name for entry in entries[:MAX_DIRECTORY_ENTRIES]]
    snippet = "\n".join(entry_names)[:MAX_SNIPPET_CHARS] if entry_names else "(empty directory)"
    relative_title = _relative_path_text(root, path, root_text=".")

    return [
        Evidence(
            id=_evidence_id("list-directory", root, path, root_slug="root", root_text="."),
            subtask_id=subtask_id,
            title=f"Directory listing: {relative_title}",
            source_url=path.as_uri(),
            snippet=snippet,
            source_type="docs",
            verified=True,
        )
    ]


def _resolve_inside_root(root: Path, query: str) -> Path | None:
    try:
        candidate = Path(query)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
    except OSError:
        return None
    if not candidate.is_relative_to(root):
        return None
    return candidate


def _evidence_id(
    prefix: str,
    root: Path,
    path: Path,
    root_slug: str | None = None,
    root_text: str | None = None,
) -> str:
    relative_path_text = _relative_path_text(root, path, root_text=root_text)
    digest = hashlib.sha1(relative_path_text.encode("utf-8")).hexdigest()[:8]
    slug_input = root_slug if relative_path_text == (root_text or "") and root_slug else relative_path_text
    return f"{prefix}-{_slugify(slug_input)}-{digest}"


def _relative_path_text(root: Path, path: Path, root_text: str | None = None) -> str:
    relative_path = path.relative_to(root)
    relative_path_text = relative_path.as_posix()
    if relative_path_text == "." and root_text is not None:
        return root_text
    return relative_path_text


def _normalize_snippet(text: str) -> str:
    return " ".join(text.split())[:MAX_SNIPPET_CHARS]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "root"
```

- [ ] **Step 4: Register and export tools**

In `src/insight_graph/tools/registry.py`, import:

```python
from insight_graph.tools.file_tools import list_directory, read_file
```

Add entries:

```python
            "list_directory": list_directory,
            "read_file": read_file,
```

In `src/insight_graph/tools/__init__.py`, import:

```python
from insight_graph.tools.file_tools import list_directory, read_file
```

Update `__all__` to include both names:

```python
__all__ = [
    "SearchResult",
    "ToolRegistry",
    "document_reader",
    "fetch_url",
    "github_search",
    "list_directory",
    "news_search",
    "read_file",
    "web_search",
]
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
git commit -m "feat: add readonly file tools"
```

---

### Task 2: Add Planner Opt-ins And Env Isolation

**Files:**
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_graph.py`

- [ ] **Step 1: Write failing Planner tests**

In `tests/test_agents.py`, update `clear_llm_env()` to clear:

```python
        "INSIGHT_GRAPH_USE_READ_FILE",
        "INSIGHT_GRAPH_USE_LIST_DIRECTORY",
```

Update `test_planner_creates_core_research_subtasks()`, `test_collector_adds_verified_mock_evidence()`, and any existing default/mock planner tests to clear both new env vars.

Add these tests after the document reader planner tests:

```python
def test_planner_uses_read_file_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["read_file"]
```

```python
def test_planner_uses_list_directory_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request=".")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["list_directory"]
```

```python
def test_planner_prefers_document_reader_over_readonly_file_tools(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["document_reader"]
```

```python
def test_planner_prefers_read_file_over_list_directory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["read_file"]
```

Update `tests/test_graph.py` planner env cleanup helper to clear both new env vars.

- [ ] **Step 2: Run agent tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_read_file_when_enabled tests/test_agents.py::test_planner_uses_list_directory_when_enabled tests/test_agents.py::test_planner_prefers_document_reader_over_readonly_file_tools tests/test_agents.py::test_planner_prefers_read_file_over_list_directory -q
```

Expected: at least read/list opt-in tests fail because Planner does not yet select the new tools.

- [ ] **Step 3: Implement Planner opt-ins**

Update `_collection_tool_name()` in `src/insight_graph/agents/planner.py` to:

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
git commit -m "feat: let planner opt into readonly file tools"
```

---

### Task 3: Document Read-only File Tool Opt-ins

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update Search Provider configuration table**

Add rows after `INSIGHT_GRAPH_USE_DOCUMENT_READER`:

```markdown
| `INSIGHT_GRAPH_USE_READ_FILE` | `1` / `true` / `yes` 时 Planner collect subtask 使用本地只读 `read_file`；搜索工具和 `document_reader` 优先 | 未启用 |
| `INSIGHT_GRAPH_USE_LIST_DIRECTORY` | `1` / `true` / `yes` 时 Planner collect subtask 使用本地只读 `list_directory`；搜索工具、`document_reader` 和 `read_file` 优先 | 未启用 |
```

- [ ] **Step 2: Add explanatory paragraph**

After the document reader paragraph, add:

```markdown
需要安全浏览本地项目素材时，可使用只读文件工具：`INSIGHT_GRAPH_USE_READ_FILE=1` 将用户请求作为 cwd 内安全文本文件路径读取，`INSIGHT_GRAPH_USE_LIST_DIRECTORY=1` 将用户请求作为 cwd 内目录路径列出一层内容。第一版只读文件工具不会写文件、不会递归扫描、不会读取工作目录外路径，也不会执行代码；`write_file` 和 `code_execute` 将单独设计。
```

Update the built-in tools table row for `read_file` / `write_file` / `list_directory` to clarify current scope:

```markdown
| `read_file` / `list_directory` | 当前支持 cwd 内只读安全文本读取与一层目录列表；`write_file` 属于后续路线图 |
```

- [ ] **Step 3: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_read_file_when_enabled tests/test_agents.py::test_planner_uses_list_directory_when_enabled tests/test_tools.py::test_registry_runs_read_file_tool tests/test_tools.py::test_registry_runs_list_directory_tool -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document readonly file tool opt ins"
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
Remove-Item Env:\INSIGHT_GRAPH_USE_READ_FILE -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_LIST_DIRECTORY -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_DOCUMENT_READER -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json | python -c "import sys,json; data=json.load(sys.stdin); print(data['tool_call_log'][0]['tool_name'])"
```

Expected output: `mock_search`.

- [ ] **Step 5: Run read_file opt-in CLI smoke**

Run and parse JSON tool name:

```powershell
$env:INSIGHT_GRAPH_USE_READ_FILE = "1"; Remove-Item Env:\INSIGHT_GRAPH_USE_LIST_DIRECTORY -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_DOCUMENT_READER -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "README.md" --output-json | python -c "import sys,json; data=json.load(sys.stdin); print(data['tool_call_log'][0]['tool_name'])"
```

Expected output: `read_file`.

- [ ] **Step 6: Run list_directory opt-in CLI smoke**

Run and parse JSON tool name:

```powershell
Remove-Item Env:\INSIGHT_GRAPH_USE_READ_FILE -ErrorAction SilentlyContinue; $env:INSIGHT_GRAPH_USE_LIST_DIRECTORY = "1"; Remove-Item Env:\INSIGHT_GRAPH_USE_DOCUMENT_READER -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "." --output-json | python -c "import sys,json; data=json.load(sys.stdin); print(data['tool_call_log'][0]['tool_name'])"
```

Expected output: `list_directory`.

- [ ] **Step 7: Clear env and inspect git status**

Run:

```powershell
Remove-Item Env:\INSIGHT_GRAPH_USE_READ_FILE -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_LIST_DIRECTORY -ErrorAction SilentlyContinue; git status --short --branch
```

Expected: clean working tree on the implementation branch.
