# Search Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add configurable `web_search` providers so InsightGraph can opt into DuckDuckGo search while keeping deterministic mock search as the default.

**Architecture:** Move `SearchResult` and provider selection into a focused `search_providers.py` module. Keep `web_search.py` as the ToolRegistry-facing adapter that resolves a provider, gets candidate URLs, and sends them through `pre_fetch_results`.

**Tech Stack:** Python 3.11+, Pydantic, `duckduckgo-search`, Pytest, Ruff.

---

## File Structure

- Create: `src/insight_graph/tools/search_providers.py` - provider protocol, mock provider, DuckDuckGo provider, provider/limit config helpers.
- Modify: `src/insight_graph/tools/web_search.py` - delegate candidate generation to selected provider while preserving callable module export.
- Modify: `src/insight_graph/tools/pre_fetch.py` - import `SearchResult` from `search_providers` to avoid provider/web_search cycles.
- Modify: `src/insight_graph/tools/__init__.py` - keep existing exports stable; add no new public package export unless needed by tests.
- Modify: `pyproject.toml` - add `duckduckgo-search` dependency.
- Create: `tests/test_search_providers.py` - provider selection, limit parsing, mock provider, DuckDuckGo mapping/failure tests.
- Modify: `tests/test_web_search.py` - verify provider delegation and env limit integration.
- Modify: `tests/test_tools.py` - keep callable export/submodule import regression coverage.
- Modify: `README.md` - document opt-in DuckDuckGo provider and default mock behavior.

---

### Task 1: Provider Abstraction And Mock Provider

**Files:**
- Create: `src/insight_graph/tools/search_providers.py`
- Modify: `src/insight_graph/tools/web_search.py`
- Modify: `src/insight_graph/tools/pre_fetch.py`
- Create: `tests/test_search_providers.py`
- Modify: `tests/test_web_search.py`

- [ ] **Step 1: Write failing provider tests**

Create `tests/test_search_providers.py`:

```python
import pytest

from insight_graph.tools.search_providers import (
    MockSearchProvider,
    SearchResult,
    get_search_provider,
    parse_search_limit,
)


def test_mock_search_provider_returns_deterministic_results() -> None:
    results = MockSearchProvider().search("Compare AI coding agents", limit=2)

    assert [result.url for result in results] == [
        "https://cursor.com/pricing",
        "https://docs.github.com/copilot",
    ]
    assert all(isinstance(result, SearchResult) for result in results)
    assert all(result.source == "mock" for result in results)


def test_get_search_provider_defaults_to_mock(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_SEARCH_PROVIDER", raising=False)

    provider = get_search_provider()

    assert isinstance(provider, MockSearchProvider)


def test_get_search_provider_accepts_explicit_mock() -> None:
    provider = get_search_provider("mock")

    assert isinstance(provider, MockSearchProvider)


def test_get_search_provider_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unknown search provider"):
        get_search_provider("unknown")


def test_parse_search_limit_reads_valid_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "5")

    assert parse_search_limit() == 5


def test_parse_search_limit_falls_back_for_invalid_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "not-a-number")

    assert parse_search_limit() == 3


def test_parse_search_limit_falls_back_for_non_positive_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "0")

    assert parse_search_limit() == 3
```

- [ ] **Step 2: Add failing web search provider delegation test**

Append to `tests/test_web_search.py`:

```python

def test_web_search_uses_configured_provider_and_limit(monkeypatch) -> None:
    captured = {}

    class FakeProvider:
        def search(self, query: str, limit: int):
            captured["provider_query"] = query
            captured["provider_limit"] = limit
            return [
                SearchResult(
                    title="One",
                    url="https://example.com/one",
                    snippet="one",
                    source="fake",
                ),
                SearchResult(
                    title="Two",
                    url="https://example.com/two",
                    snippet="two",
                    source="fake",
                ),
            ]

    def fake_pre_fetch_results(results, subtask_id: str, limit: int):
        captured["prefetch_urls"] = [result.url for result in results]
        captured["subtask_id"] = subtask_id
        captured["prefetch_limit"] = limit
        return [
            Evidence(
                id="provider-prefetched",
                subtask_id=subtask_id,
                title="Provider Prefetched",
                source_url="https://example.com/one",
                snippet="Provider prefetched evidence.",
                verified=True,
            )
        ]

    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_LIMIT", "2")
    monkeypatch.setattr(web_search_module, "get_search_provider", lambda: FakeProvider())
    monkeypatch.setattr(web_search_module, "pre_fetch_results", fake_pre_fetch_results)

    evidence = web_search_module.web_search("agentic coding tools", subtask_id="s1")

    assert captured == {
        "provider_query": "agentic coding tools",
        "provider_limit": 2,
        "prefetch_urls": ["https://example.com/one", "https://example.com/two"],
        "subtask_id": "s1",
        "prefetch_limit": 2,
    }
    assert [item.id for item in evidence] == ["provider-prefetched"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_search_providers.py tests/test_web_search.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.tools.search_providers'` or missing `get_search_provider` on `web_search_module`.

- [ ] **Step 4: Implement provider abstraction and mock provider**

Create `src/insight_graph/tools/search_providers.py`:

```python
import os
from typing import Protocol

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"


class SearchProvider(Protocol):
    def search(self, query: str, limit: int) -> list[SearchResult]: ...


class MockSearchProvider:
    def search(self, query: str, limit: int) -> list[SearchResult]:
        return _mock_results()[:limit]


def get_search_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")).lower()
    if provider_name == "mock":
        return MockSearchProvider()
    raise ValueError(f"Unknown search provider: {provider_name}")


def parse_search_limit(default: int = 3) -> int:
    raw_limit = os.getenv("INSIGHT_GRAPH_SEARCH_LIMIT")
    if raw_limit is None:
        return default
    try:
        limit = int(raw_limit)
    except ValueError:
        return default
    if limit <= 0:
        return default
    return limit


def _mock_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Cursor Pricing",
            url="https://cursor.com/pricing",
            snippet="Cursor pricing information for AI coding plans.",
        ),
        SearchResult(
            title="GitHub Copilot Documentation",
            url="https://docs.github.com/copilot",
            snippet="GitHub Copilot documentation and feature guides.",
        ),
        SearchResult(
            title="opencode GitHub Repository",
            url="https://github.com/sst/opencode",
            snippet="Open source agentic coding tool repository.",
        ),
    ]
```

Modify `src/insight_graph/tools/pre_fetch.py`:

```python
from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.search_providers import SearchResult


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

Modify `src/insight_graph/tools/web_search.py`:

```python
import sys
from types import ModuleType

from insight_graph.state import Evidence
from insight_graph.tools.search_providers import (
    MockSearchProvider,
    SearchResult,
    get_search_provider,
    parse_search_limit,
)

from insight_graph.tools.pre_fetch import pre_fetch_results  # noqa: E402


def mock_web_search(query: str) -> list[SearchResult]:
    return MockSearchProvider().search(query, limit=3)


def web_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    limit = parse_search_limit()
    results = get_search_provider().search(query, limit)
    return pre_fetch_results(results, subtask_id, limit=limit)


class _CallableWebSearchModule(ModuleType):
    def __call__(self, query: str, subtask_id: str = "collect") -> list[Evidence]:
        return web_search(query, subtask_id)


sys.modules[__name__].__class__ = _CallableWebSearchModule
```

- [ ] **Step 5: Run provider and web search tests**

Run: `python -m pytest tests/test_search_providers.py tests/test_web_search.py tests/test_pre_fetch.py -v`

Expected: all selected tests pass.

- [ ] **Step 6: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 7: Commit**

```bash
git add src/insight_graph/tools/search_providers.py src/insight_graph/tools/web_search.py src/insight_graph/tools/pre_fetch.py tests/test_search_providers.py tests/test_web_search.py
git commit -m "feat: add search provider abstraction"
```

---

### Task 2: DuckDuckGo Provider

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/insight_graph/tools/search_providers.py`
- Modify: `tests/test_search_providers.py`

- [ ] **Step 1: Write failing DuckDuckGo provider tests**

Append to `tests/test_search_providers.py`:

```python

from insight_graph.tools.search_providers import DuckDuckGoSearchProvider


class FakeDuckDuckGoClient:
    def __init__(self, results):
        self.results = results
        self.calls = []

    def text(self, query: str, max_results: int):
        self.calls.append((query, max_results))
        return self.results


def test_get_search_provider_accepts_explicit_duckduckgo() -> None:
    provider = get_search_provider("duckduckgo")

    assert isinstance(provider, DuckDuckGoSearchProvider)


def test_get_search_provider_reads_duckduckgo_from_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "duckduckgo")

    provider = get_search_provider()

    assert isinstance(provider, DuckDuckGoSearchProvider)


def test_duckduckgo_provider_maps_results() -> None:
    client = FakeDuckDuckGoClient(
        [
            {
                "title": "Cursor Pricing",
                "href": "https://cursor.com/pricing",
                "body": "Cursor pricing details.",
            },
            {
                "title": "GitHub Copilot",
                "url": "https://docs.github.com/copilot",
                "snippet": "GitHub Copilot docs.",
            },
            {
                "title": "Missing URL",
                "body": "This result should be skipped.",
            },
        ]
    )
    provider = DuckDuckGoSearchProvider(client_factory=lambda: client)

    results = provider.search("AI coding agents", limit=3)

    assert client.calls == [("AI coding agents", 3)]
    assert [result.url for result in results] == [
        "https://cursor.com/pricing",
        "https://docs.github.com/copilot",
    ]
    assert [result.title for result in results] == ["Cursor Pricing", "GitHub Copilot"]
    assert [result.snippet for result in results] == [
        "Cursor pricing details.",
        "GitHub Copilot docs.",
    ]
    assert all(result.source == "duckduckgo" for result in results)


def test_duckduckgo_provider_supports_link_field() -> None:
    client = FakeDuckDuckGoClient(
        [
            {
                "title": "OpenCode",
                "link": "https://github.com/sst/opencode",
                "body": "OpenCode repository.",
            }
        ]
    )
    provider = DuckDuckGoSearchProvider(client_factory=lambda: client)

    results = provider.search("OpenCode", limit=1)

    assert [result.url for result in results] == ["https://github.com/sst/opencode"]


def test_duckduckgo_provider_returns_empty_list_on_failure() -> None:
    def broken_client_factory():
        raise RuntimeError("network unavailable")

    provider = DuckDuckGoSearchProvider(client_factory=broken_client_factory)

    assert provider.search("AI coding agents", limit=3) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_search_providers.py -v`

Expected: FAIL because `DuckDuckGoSearchProvider` is not implemented and `duckduckgo` is not an accepted provider.

- [ ] **Step 3: Add dependency**

Modify `pyproject.toml` dependencies to include `duckduckgo-search`:

```toml
dependencies = [
  "beautifulsoup4>=4.12.0",
  "duckduckgo-search>=6.0.0",
  "langgraph>=0.2.0",
  "langchain-core>=0.3.0",
  "pydantic>=2.7.0",
  "typer>=0.12.0",
  "rich>=13.7.0",
]
```

- [ ] **Step 4: Implement DuckDuckGo provider**

Replace `src/insight_graph/tools/search_providers.py` with:

```python
import os
from collections.abc import Callable, Iterable
from typing import Any, Protocol

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"


class SearchProvider(Protocol):
    def search(self, query: str, limit: int) -> list[SearchResult]: ...


class MockSearchProvider:
    def search(self, query: str, limit: int) -> list[SearchResult]:
        return _mock_results()[:limit]


class DuckDuckGoSearchProvider:
    def __init__(self, client_factory: Callable[[], Any] | None = None) -> None:
        self._client_factory = client_factory or _create_duckduckgo_client

    def search(self, query: str, limit: int) -> list[SearchResult]:
        try:
            client = self._client_factory()
            raw_results = _run_text_search(client, query, limit)
            return _map_duckduckgo_results(raw_results)
        except Exception:
            return []


def get_search_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")).lower()
    if provider_name == "mock":
        return MockSearchProvider()
    if provider_name == "duckduckgo":
        return DuckDuckGoSearchProvider()
    raise ValueError(f"Unknown search provider: {provider_name}")


def parse_search_limit(default: int = 3) -> int:
    raw_limit = os.getenv("INSIGHT_GRAPH_SEARCH_LIMIT")
    if raw_limit is None:
        return default
    try:
        limit = int(raw_limit)
    except ValueError:
        return default
    if limit <= 0:
        return default
    return limit


def _create_duckduckgo_client() -> Any:
    from duckduckgo_search import DDGS

    return DDGS()


def _run_text_search(client: Any, query: str, limit: int) -> Iterable[dict[str, Any]]:
    if hasattr(client, "__enter__"):
        with client as active_client:
            return active_client.text(query, max_results=limit)
    return client.text(query, max_results=limit)


def _map_duckduckgo_results(raw_results: Iterable[dict[str, Any]]) -> list[SearchResult]:
    results: list[SearchResult] = []
    for raw in raw_results:
        url = raw.get("href") or raw.get("url") or raw.get("link")
        if not url:
            continue
        results.append(
            SearchResult(
                title=raw.get("title") or url,
                url=url,
                snippet=raw.get("body") or raw.get("snippet") or "",
                source="duckduckgo",
            )
        )
    return results


def _mock_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Cursor Pricing",
            url="https://cursor.com/pricing",
            snippet="Cursor pricing information for AI coding plans.",
        ),
        SearchResult(
            title="GitHub Copilot Documentation",
            url="https://docs.github.com/copilot",
            snippet="GitHub Copilot documentation and feature guides.",
        ),
        SearchResult(
            title="opencode GitHub Repository",
            url="https://github.com/sst/opencode",
            snippet="Open source agentic coding tool repository.",
        ),
    ]
```

- [ ] **Step 5: Run provider tests**

Run: `python -m pytest tests/test_search_providers.py -v`

Expected: all provider tests pass without live network access.

- [ ] **Step 6: Run broader tests and lint**

Run: `python -m pytest tests/test_search_providers.py tests/test_web_search.py tests/test_tools.py -v`

Expected: all selected tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/insight_graph/tools/search_providers.py tests/test_search_providers.py
git commit -m "feat: add duckduckgo search provider"
```

---

### Task 3: Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README current MVP table**

Modify the current MVP evidence row from:

```markdown
| 证据链 | 已实现 deterministic `mock_search`、direct URL `fetch_url` 和 mock `web_search -> pre_fetch -> fetch_url`；报告引用仅来自 verified evidence |
```

to:

```markdown
| 证据链 | 已实现 deterministic `mock_search`、direct URL `fetch_url`、默认 mock `web_search -> pre_fetch -> fetch_url`，并支持 opt-in DuckDuckGo provider；报告引用仅来自 verified evidence |
```

Modify the note below the table from:

```markdown
> MVP 阶段默认 CLI 仍使用固定 mock evidence，适合验证架构闭环；工具层已支持 direct URL 抓取、HTML evidence 提取，以及 deterministic web_search pre-fetch 链路。真实 web/news/GitHub 搜索、FastAPI、PostgreSQL、pgvector、LLM 路由和可观测性属于后续路线图。
```

to:

```markdown
> MVP 阶段默认 CLI 仍使用固定 mock evidence，适合验证架构闭环；工具层已支持 direct URL 抓取、HTML evidence 提取、默认 mock web_search pre-fetch 链路，以及通过 `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo` 启用的 DuckDuckGo 搜索入口。新闻/GitHub 专用搜索、FastAPI、PostgreSQL、pgvector、LLM 路由和可观测性属于后续路线图。
```

- [ ] **Step 2: Add provider configuration section**

Add this section after the current MVP note:

```markdown

### Search Provider 配置

`web_search` 默认使用 deterministic mock provider，测试和默认 CLI 不访问公网。需要真实搜索时可显式启用 DuckDuckGo：

```bash
INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo INSIGHT_GRAPH_SEARCH_LIMIT=3 python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_SEARCH_PROVIDER` | `mock` 或 `duckduckgo` | `mock` |
| `INSIGHT_GRAPH_SEARCH_LIMIT` | `web_search` 候选 URL pre-fetch 数量 | `3` |
```

- [ ] **Step 3: Run full verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`. This command should use default mock behavior and should not require DuckDuckGo network access.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document search provider configuration"
```

---

## Self-Review

- Spec coverage: Tasks implement provider abstraction, default mock behavior, opt-in DuckDuckGo provider, environment-based provider/limit configuration, offline tests, README documentation, and final CLI verification.
- Deferred scope: Executor rewrite, multi-round tools, LLM relevance, Qwen Search, Playwright, PDF, Trafilatura, and RAG remain excluded.
- Placeholder scan: No placeholders remain; each task includes exact files, test code, implementation code, commands, expected failures, expected pass conditions, and commit commands.
- Type consistency: `SearchResult`, `SearchProvider`, `MockSearchProvider`, `DuckDuckGoSearchProvider`, `get_search_provider`, `parse_search_limit`, and `pre_fetch_results` signatures are consistent across tasks.
