# Document Reader Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a safe offline `document_reader` tool that turns local text/Markdown files inside the working directory into verified docs evidence.

**Architecture:** Implement `document_reader()` as a focused local-file tool with explicit path containment checks, suffix allow-listing, snippet normalization, and stable evidence IDs. Register and export it through existing tool boundaries, then let Planner select it via `INSIGHT_GRAPH_USE_DOCUMENT_READER` after higher-priority search opt-ins.

**Tech Stack:** Python 3.13, pathlib, regex via stdlib `re`, Pydantic `Evidence`, existing `ToolRegistry`, pytest, ruff.

---

## File Structure

- Create `src/insight_graph/tools/document_reader.py`: safe local text/Markdown reader.
- Modify `src/insight_graph/tools/registry.py`: register `document_reader`.
- Modify `src/insight_graph/tools/__init__.py`: export `document_reader`.
- Modify `src/insight_graph/agents/planner.py`: add `INSIGHT_GRAPH_USE_DOCUMENT_READER` opt-in selection.
- Modify `tests/test_tools.py`: cover package export, direct tool output, safety cases, registry execution.
- Modify `tests/test_agents.py`: cover Planner opt-in priority.
- Modify `README.md`: document deterministic local document reader opt-in.

---

### Task 1: Add Document Reader Tool And Registry Integration

**Files:**
- Create: `src/insight_graph/tools/document_reader.py`
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing tool tests**

In `tests/test_tools.py`, update the tools import from:

```python
from insight_graph.tools import (
    SearchResult,
    ToolRegistry,
    fetch_url,
    github_search,
    news_search,
    web_search,
)
```

to:

```python
from insight_graph.tools import (
    SearchResult,
    ToolRegistry,
    document_reader,
    fetch_url,
    github_search,
    news_search,
    web_search,
)
```

Add this test after `test_tools_package_exports_news_search_callable()`:

```python
def test_tools_package_exports_document_reader_callable() -> None:
    assert callable(document_reader)
```

Add these tests after `test_news_search_returns_deterministic_verified_news_evidence()`:

```python
def test_document_reader_returns_verified_docs_evidence(tmp_path, monkeypatch) -> None:
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    document = docs_dir / "Market Report.md"
    document.write_text(
        "# Market Report\n\nCursor   launches features.\nGitHub Copilot updates docs.",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("docs/Market Report.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == "document-market-report"
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "Market Report.md"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == (
        "# Market Report Cursor launches features. GitHub Copilot updates docs."
    )
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True
```

```python
def test_document_reader_limits_snippet_length(tmp_path, monkeypatch) -> None:
    document = tmp_path / "long.md"
    document.write_text("a" * 600, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("long.md", "s1")

    assert len(evidence[0].snippet) == 500
```

```python
@pytest.mark.parametrize(
    "query",
    [
        "missing.md",
        ".",
        "unsupported.pdf",
        "../outside.md",
    ],
)
def test_document_reader_rejects_invalid_paths(query, tmp_path, monkeypatch) -> None:
    (tmp_path / "unsupported.pdf").write_text("pdf text", encoding="utf-8")
    (tmp_path.parent / "outside.md").write_text("outside", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert document_reader(query, "s1") == []
```

Add this test after `test_registry_runs_news_search_tool()`:

```python
def test_registry_runs_document_reader_tool(tmp_path, monkeypatch) -> None:
    document = tmp_path / "sample.md"
    document.write_text("Local document evidence.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = ToolRegistry().run("document_reader", "sample.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == "document-sample"
    assert evidence[0].source_type == "docs"
```

- [ ] **Step 2: Run tool tests and verify RED**

Run:

```powershell
python -m pytest tests/test_tools.py::test_tools_package_exports_document_reader_callable tests/test_tools.py::test_document_reader_returns_verified_docs_evidence tests/test_tools.py::test_document_reader_limits_snippet_length tests/test_tools.py::test_document_reader_rejects_invalid_paths tests/test_tools.py::test_registry_runs_document_reader_tool -q
```

Expected: FAIL during import because `document_reader` is not exported yet, or FAIL because the registry does not know `document_reader`.

- [ ] **Step 3: Implement safe document reader tool**

Create `src/insight_graph/tools/document_reader.py`:

```python
import re
from pathlib import Path

from insight_graph.state import Evidence

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown"}
MAX_SNIPPET_CHARS = 500


def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]:
    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, query)
    if path is None or not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []

    snippet = _normalize_snippet(text)
    if not snippet:
        return []

    return [
        Evidence(
            id=f"document-{_slugify(path.stem)}",
            subtask_id=subtask_id,
            title=path.name,
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


def _normalize_snippet(text: str) -> str:
    return " ".join(text.split())[:MAX_SNIPPET_CHARS]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "document"
```

- [ ] **Step 4: Register and export the tool**

In `src/insight_graph/tools/registry.py`, add the import:

```python
from insight_graph.tools.document_reader import document_reader
```

Add the registry entry before `fetch_url`:

```python
            "document_reader": document_reader,
```

In `src/insight_graph/tools/__init__.py`, add the import:

```python
from insight_graph.tools.document_reader import document_reader
```

Update `__all__` to:

```python
__all__ = [
    "SearchResult",
    "ToolRegistry",
    "document_reader",
    "fetch_url",
    "github_search",
    "news_search",
    "web_search",
]
```

- [ ] **Step 5: Run tool tests and lint**

Run:

```powershell
python -m pytest tests/test_tools.py -q
python -m ruff check src/insight_graph/tools/document_reader.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src/insight_graph/tools/document_reader.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
git commit -m "feat: add local document reader tool"
```

---

### Task 2: Add Planner Opt-in Coverage

**Files:**
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing Planner tests**

In `tests/test_agents.py`, update `clear_llm_env()` to also clear the document reader flag by adding this string to the list:

```python
        "INSIGHT_GRAPH_USE_DOCUMENT_READER",
```

Update `test_planner_creates_core_research_subtasks()` to clear the document reader flag:

```python
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
```

Add this test after `test_planner_uses_news_search_when_enabled()`:

```python
def test_planner_uses_document_reader_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["document_reader"]
```

Add this test after `test_planner_prefers_web_search_over_news_search()`:

```python
def test_planner_prefers_news_search_over_document_reader(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["news_search"]
```

Add this test after it:

```python
def test_planner_prefers_github_search_over_document_reader(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["github_search"]
```

Add this test after it:

```python
def test_planner_prefers_web_search_over_document_reader(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]
```

Update `test_planner_ignores_non_truthy_web_search_flag()` to also set non-truthy document reader:

```python
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "0")
```

- [ ] **Step 2: Run agent tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_document_reader_when_enabled tests/test_agents.py::test_planner_prefers_news_search_over_document_reader tests/test_agents.py::test_planner_prefers_github_search_over_document_reader tests/test_agents.py::test_planner_prefers_web_search_over_document_reader -q
```

Expected: FAIL because Planner does not yet select `document_reader`.

- [ ] **Step 3: Implement Planner opt-in**

Replace `_collection_tool_name()` in `src/insight_graph/agents/planner.py` with:

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
    return "mock_search"
```

Keep the existing helper unchanged:

```python
def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}
```

- [ ] **Step 4: Run agent tests and lint**

Run:

```powershell
python -m pytest tests/test_agents.py -q
python -m ruff check src/insight_graph/agents/planner.py tests/test_agents.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 2**

Run:

```powershell
git add src/insight_graph/agents/planner.py tests/test_agents.py
git commit -m "feat: let planner opt into document reader"
```

---

### Task 3: Document Document Reader Opt-in

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update Search Provider configuration table**

In `README.md`, in the Search Provider configuration table, add this row after `INSIGHT_GRAPH_USE_NEWS_SEARCH`:

```markdown
| `INSIGHT_GRAPH_USE_DOCUMENT_READER` | `1` / `true` / `yes` 时 Planner collect subtask 使用本地 `document_reader`；若同时启用搜索工具，则搜索工具优先 | 未启用 |
```

- [ ] **Step 2: Add Document reader explanatory paragraph**

After the paragraph that starts with `需要只采集新闻和产品公告风格证据而不访问公网时`, add:

```markdown
需要从本地 text/Markdown 文档生成 evidence 时，可设置 `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` 并把用户请求写成本地文件路径，例如 `README.md`。第一版 `document_reader` 只读取当前工作目录内的 `.txt`、`.md`、`.markdown` 文件；不读取工作目录外路径、不读取 URL，也不解析 PDF/HTML。若同时启用搜索工具，Planner 会按 web search、GitHub search、news search、document reader、mock search 的顺序选择第一个启用工具。
```

- [ ] **Step 3: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_document_reader_when_enabled tests/test_tools.py::test_registry_runs_document_reader_tool -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document local document reader opt in"
```

---

### Task 4: Final Verification And CLI Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_tools.py tests/test_agents.py -q
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

Run:

```powershell
Remove-Item Env:\INSIGHT_GRAPH_USE_DOCUMENT_READER -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected: JSON is parseable and `tool_call_log[0].tool_name` is `mock_search`.

- [ ] **Step 5: Run Document reader opt-in CLI smoke**

Run:

```powershell
$env:INSIGHT_GRAPH_USE_DOCUMENT_READER = "1"; Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "README.md" --output-json
```

Expected: JSON is parseable and `tool_call_log[0].tool_name` is `document_reader`.

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
