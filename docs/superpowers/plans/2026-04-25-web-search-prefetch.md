# Web Search Pre-fetch Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic `web_search` tool that produces candidate URLs and pre-fetches them through the existing `fetch_url` evidence boundary without changing the default Planner or CLI behavior.

**Architecture:** Add `web_search.py` for typed mock search results and the registry-facing `web_search` adapter, plus `pre_fetch.py` for limiting and flattening `fetch_url` evidence from candidate URLs. Register `web_search` in `ToolRegistry` while keeping existing `mock_search` and `fetch_url` behavior intact.

**Tech Stack:** Python 3.11+, Pydantic, existing `fetch_url`, Pytest, Ruff.

---

## File Structure

- Create: `src/insight_graph/tools/web_search.py` - `SearchResult`, deterministic `mock_web_search`, and registry-facing `web_search`.
- Create: `src/insight_graph/tools/pre_fetch.py` - `pre_fetch_results` that converts candidate URLs into Evidence using `fetch_url`.
- Modify: `src/insight_graph/tools/registry.py` - register `web_search` beside existing tools.
- Modify: `src/insight_graph/tools/__init__.py` - export callable `web_search` and `SearchResult` without breaking callable `fetch_url` export.
- Create: `tests/test_web_search.py` - deterministic search and adapter tests.
- Create: `tests/test_pre_fetch.py` - candidate limiting and flattening tests.
- Modify: `tests/test_tools.py` - add registry coverage for `web_search` while preserving existing tool tests.
- Modify: `README.md` - document the new deterministic `web_search -> pre_fetch -> fetch_url` tool path as current MVP tool-layer capability.

---

### Task 1: Pre-fetch Results

**Files:**
- Create: `src/insight_graph/tools/pre_fetch.py`
- Create: `tests/test_pre_fetch.py`

- [ ] **Step 1: Write failing pre-fetch tests**

Create `tests/test_pre_fetch.py`:

```python
import importlib

from insight_graph.state import Evidence
from insight_graph.tools.web_search import SearchResult


def test_pre_fetch_results_limits_and_flattens_evidence(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")
    fetched_urls = []

    def fake_fetch_url(url: str, subtask_id: str):
        fetched_urls.append(url)
        return [
            Evidence(
                id=url.rsplit("/", 1)[-1],
                subtask_id=subtask_id,
                title=f"Fetched {url}",
                source_url=url,
                snippet="Fetched evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(title="One", url="https://example.com/one", snippet="one"),
        SearchResult(title="Two", url="https://example.com/two", snippet="two"),
        SearchResult(title="Three", url="https://example.com/three", snippet="three"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1", limit=2)

    assert fetched_urls == ["https://example.com/one", "https://example.com/two"]
    assert [item.id for item in evidence] == ["one", "two"]
    assert all(item.subtask_id == "s1" for item in evidence)


def test_pre_fetch_results_skips_empty_evidence(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")

    def fake_fetch_url(url: str, subtask_id: str):
        if url.endswith("empty"):
            return []
        return [
            Evidence(
                id="kept",
                subtask_id=subtask_id,
                title="Kept",
                source_url=url,
                snippet="Kept evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(title="Empty", url="https://example.com/empty", snippet="empty"),
        SearchResult(title="Kept", url="https://example.com/kept", snippet="kept"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1")

    assert [item.id for item in evidence] == ["kept"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pre_fetch.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.tools.web_search'` or `No module named 'insight_graph.tools.pre_fetch'`.

- [ ] **Step 3: Implement minimal `SearchResult` dependency**

Create `src/insight_graph/tools/web_search.py` with only `SearchResult` for this task:

```python
from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"
```

- [ ] **Step 4: Implement pre-fetch**

Create `src/insight_graph/tools/pre_fetch.py`:

```python
from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.web_search import SearchResult


def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    for result in results[:limit]:
        evidence.extend(fetch_url(result.url, subtask_id))
    return evidence
```

- [ ] **Step 5: Run pre-fetch tests**

Run: `python -m pytest tests/test_pre_fetch.py -v`

Expected: 2 tests pass.

- [ ] **Step 6: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 7: Commit**

```bash
git add src/insight_graph/tools/web_search.py src/insight_graph/tools/pre_fetch.py tests/test_pre_fetch.py
git commit -m "feat: add search result prefetching"
```

---

### Task 2: Deterministic Web Search Tool

**Files:**
- Modify: `src/insight_graph/tools/web_search.py`
- Create: `tests/test_web_search.py`

- [ ] **Step 1: Write failing web search tests**

Create `tests/test_web_search.py`:

```python
import importlib

from insight_graph.state import Evidence
from insight_graph.tools.web_search import SearchResult, mock_web_search, web_search


def test_mock_web_search_returns_deterministic_results() -> None:
    results = mock_web_search("Compare AI coding agents")

    assert [result.url for result in results] == [
        "https://cursor.com/pricing",
        "https://docs.github.com/copilot",
        "https://github.com/sst/opencode",
    ]
    assert all(isinstance(result, SearchResult) for result in results)
    assert all(result.source == "mock" for result in results)


def test_web_search_prefetches_results(monkeypatch) -> None:
    web_search_module = importlib.import_module("insight_graph.tools.web_search")
    captured = {}

    def fake_pre_fetch_results(results, subtask_id: str, limit: int = 3):
        captured["urls"] = [result.url for result in results]
        captured["subtask_id"] = subtask_id
        captured["limit"] = limit
        return [
            Evidence(
                id="prefetched",
                subtask_id=subtask_id,
                title="Prefetched Evidence",
                source_url="https://example.com/prefetched",
                snippet="Prefetched evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = web_search("Compare AI coding agents", "s1")

    assert captured == {
        "urls": [
            "https://cursor.com/pricing",
            "https://docs.github.com/copilot",
            "https://github.com/sst/opencode",
        ],
        "subtask_id": "s1",
        "limit": 3,
    }
    assert len(evidence) == 1
    assert evidence[0].id == "prefetched"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_web_search.py -v`

Expected: FAIL because `mock_web_search` and `web_search` are not implemented.

- [ ] **Step 3: Implement web search tool**

Replace `src/insight_graph/tools/web_search.py` with:

```python
from pydantic import BaseModel

from insight_graph.state import Evidence
from insight_graph.tools.pre_fetch import pre_fetch_results


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"


def mock_web_search(query: str) -> list[SearchResult]:
    return [
        SearchResult(
            title="Cursor Pricing",
            url="https://cursor.com/pricing",
            snippet="Cursor pricing and plan information.",
        ),
        SearchResult(
            title="GitHub Copilot Documentation",
            url="https://docs.github.com/copilot",
            snippet="GitHub Copilot documentation and feature overview.",
        ),
        SearchResult(
            title="OpenCode Repository",
            url="https://github.com/sst/opencode",
            snippet="OpenCode public repository and README.",
        ),
    ]


def web_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    results = mock_web_search(query)
    return pre_fetch_results(results, subtask_id, limit=3)
```

- [ ] **Step 4: Run web search tests**

Run: `python -m pytest tests/test_web_search.py -v`

Expected: 2 tests pass.

- [ ] **Step 5: Run pre-fetch tests**

Run: `python -m pytest tests/test_pre_fetch.py -v`

Expected: 2 tests still pass.

- [ ] **Step 6: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 7: Commit**

```bash
git add src/insight_graph/tools/web_search.py tests/test_web_search.py
git commit -m "feat: add deterministic web search tool"
```

---

### Task 3: Register Web Search Tool

**Files:**
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Add failing registry tests**

Append to `tests/test_tools.py`:

```python
from insight_graph.tools import SearchResult, web_search


def test_tools_package_exports_web_search_callable_and_search_result() -> None:
    assert callable(web_search)
    result = SearchResult(title="Title", url="https://example.com", snippet="Snippet")
    assert result.source == "mock"


def test_registry_runs_web_search_tool(monkeypatch) -> None:
    web_search_module = importlib.import_module("insight_graph.tools.web_search")

    def fake_pre_fetch_results(results, subtask_id: str, limit: int = 3):
        return [
            Evidence(
                id="web-search-evidence",
                subtask_id=subtask_id,
                title="Web Search Evidence",
                source_url="https://example.com/web",
                snippet="Web search evidence snippet.",
                verified=True,
            )
        ]

    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = ToolRegistry().run("web_search", "Compare AI coding agents", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == "web-search-evidence"
    assert evidence[0].subtask_id == "s1"
```

Also update the existing import at the top of `tests/test_tools.py` from:

```python
from insight_graph.tools import ToolRegistry, fetch_url
```

to:

```python
from insight_graph.state import Evidence
from insight_graph.tools import SearchResult, ToolRegistry, fetch_url, web_search
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tools.py -v`

Expected: FAIL because package exports and registry do not know `web_search` yet.

- [ ] **Step 3: Register and export web search**

Modify `src/insight_graph/tools/registry.py`:

```python
from collections.abc import Callable

from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.mock_search import mock_search
from insight_graph.tools.web_search import web_search

ToolFn = Callable[[str, str], list[Evidence]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {
            "mock_search": mock_search,
            "fetch_url": fetch_url,
            "web_search": web_search,
        }

    def run(self, name: str, query: str, subtask_id: str) -> list[Evidence]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](query, subtask_id)
```

Modify `src/insight_graph/tools/__init__.py`:

```python
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.registry import ToolRegistry
from insight_graph.tools.web_search import SearchResult, web_search

__all__ = ["SearchResult", "ToolRegistry", "fetch_url", "web_search"]
```

- [ ] **Step 4: Run registry tests**

Run: `python -m pytest tests/test_tools.py -v`

Expected: all tool tests pass.

- [ ] **Step 5: Run full test suite and lint**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
git commit -m "feat: register web search tool"
```

---

### Task 4: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Add: `docs/superpowers/specs/2026-04-25-web-search-prefetch-design.md`
- Add: `docs/superpowers/plans/2026-04-25-web-search-prefetch.md`

- [ ] **Step 1: Update README current MVP section**

Update the current MVP capability table row for evidence chain from:

```markdown
| 证据链 | 已实现 deterministic `mock_search` 和 direct URL `fetch_url`；报告引用仅来自 verified evidence |
```

to:

```markdown
| 证据链 | 已实现 deterministic `mock_search`、direct URL `fetch_url` 和 mock `web_search -> pre_fetch -> fetch_url`；报告引用仅来自 verified evidence |
```

Update the note below that table from:

```markdown
> MVP 阶段默认 CLI 仍使用固定 mock evidence，适合验证架构闭环；工具层已支持 direct URL 抓取和 HTML evidence 提取。真实 web/news/GitHub 搜索、FastAPI、PostgreSQL、pgvector、LLM 路由和可观测性属于后续路线图。
```

to:

```markdown
> MVP 阶段默认 CLI 仍使用固定 mock evidence，适合验证架构闭环；工具层已支持 direct URL 抓取、HTML evidence 提取，以及 deterministic web_search pre-fetch 链路。真实 web/news/GitHub 搜索、FastAPI、PostgreSQL、pgvector、LLM 路由和可观测性属于后续路线图。
```

- [ ] **Step 2: Run final verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`.

- [ ] **Step 3: Commit docs and plan/spec**

```bash
git add README.md docs/superpowers/specs/2026-04-25-web-search-prefetch-design.md docs/superpowers/plans/2026-04-25-web-search-prefetch.md
git commit -m "docs: add web search prefetch plan"
```

---

## Self-Review

- Spec coverage: The plan implements typed search results, deterministic mock search, pre-fetch through existing `fetch_url`, registry registration, no live-network tests, and no default Planner/CLI behavior change.
- Deferred scope: Real search providers, relevance filtering, URL deduplication, persistent evidence pools, Planner changes, and CLI changes are explicitly excluded.
- Placeholder scan: No placeholders remain; every task includes concrete file paths, code, commands, expected failures, and expected pass conditions.
- Type consistency: The plan consistently uses `SearchResult`, `mock_web_search`, `web_search`, `pre_fetch_results`, `Evidence`, `ToolRegistry`, and existing `fetch_url`.
