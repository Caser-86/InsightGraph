# Pre-Fetch Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the existing search -> pre-fetch pipeline with failure isolation, fetch-budget capping, and retrieval-query propagation.

**Architecture:** Keep `web_search()` as the search entry point and `pre_fetch_results()` as the fetch fan-out boundary. Reuse existing `fetch_url` JSON query parsing for retrieval-query ranked chunks, and reuse `get_research_budgets()` for max fetches.

**Tech Stack:** Python 3.11+, Pydantic state models, pytest, ruff.

---

### Task 1: Pre-Fetch Failure Isolation And Budget

**Files:**
- Modify: `tests/test_pre_fetch.py`
- Modify: `src/insight_graph/tools/pre_fetch.py`

- [ ] **Step 1: Write failing tests**

Add these tests to `tests/test_pre_fetch.py`:

```python
def test_pre_fetch_results_continues_after_fetch_error(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")

    def fake_fetch_url(url: str, subtask_id: str):
        if url.endswith("broken"):
            raise RuntimeError("fetch failed")
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
        SearchResult(title="Broken", url="https://example.com/broken", snippet="broken"),
        SearchResult(title="Kept", url="https://example.com/kept", snippet="kept"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1")

    assert [item.id for item in evidence] == ["kept"]


def test_pre_fetch_results_respects_fetch_budget(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")
    fetched_urls = []

    def fake_fetch_url(url: str, subtask_id: str):
        fetched_urls.append(url)
        return []

    monkeypatch.setenv("INSIGHT_GRAPH_MAX_FETCHES", "1")
    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [
        SearchResult(title="One", url="https://example.com/one", snippet="one"),
        SearchResult(title="Two", url="https://example.com/two", snippet="two"),
    ]

    evidence = pre_fetch_module.pre_fetch_results(results, "s1", limit=2)

    assert evidence == []
    assert fetched_urls == ["https://example.com/one"]
```

- [ ] **Step 2: Run tests to verify RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_pre_fetch.py::test_pre_fetch_results_continues_after_fetch_error tests/test_pre_fetch.py::test_pre_fetch_results_respects_fetch_budget -v`

Expected: first test errors from unhandled `RuntimeError`; second test fails because both URLs are fetched.

- [ ] **Step 3: Implement minimal code**

Update `src/insight_graph/tools/pre_fetch.py`:

```python
from insight_graph.report_quality.budgeting import get_research_budgets
from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.search_providers import SearchResult


def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    fetch_limit = min(limit, get_research_budgets().max_fetches)
    for result in results[:fetch_limit]:
        try:
            evidence.extend(fetch_url(result.url, subtask_id))
        except Exception:
            continue
    return evidence
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_pre_fetch.py -q`

Expected: all `test_pre_fetch.py` tests pass.

### Task 2: Retrieval Query Propagation

**Files:**
- Modify: `tests/test_pre_fetch.py`
- Modify: `tests/test_web_search.py`
- Modify: `src/insight_graph/tools/pre_fetch.py`
- Modify: `src/insight_graph/tools/web_search.py`

- [ ] **Step 1: Write failing tests**

Add this test to `tests/test_pre_fetch.py`:

```python
def test_pre_fetch_results_passes_query_to_fetch_url(monkeypatch) -> None:
    pre_fetch_module = importlib.import_module("insight_graph.tools.pre_fetch")
    observed_queries = []

    def fake_fetch_url(url: str, subtask_id: str):
        observed_queries.append(url)
        return []

    monkeypatch.setattr(pre_fetch_module, "fetch_url", fake_fetch_url)
    results = [SearchResult(title="One", url="https://example.com/one", snippet="one")]

    evidence = pre_fetch_module.pre_fetch_results(
        results,
        "s1",
        limit=1,
        query="pricing strategy",
    )

    assert evidence == []
    assert observed_queries == [
        '{"url":"https://example.com/one","query":"pricing strategy"}'
    ]
```

Update existing fake functions in `tests/test_web_search.py` to accept `query: str | None = None`, then assert `captured["query"] == "agentic coding tools"` in both `test_web_search_prefetches_results` and `test_web_search_uses_configured_provider_and_limit`.

- [ ] **Step 2: Run tests to verify RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_pre_fetch.py::test_pre_fetch_results_passes_query_to_fetch_url tests/test_web_search.py::test_web_search_prefetches_results tests/test_web_search.py::test_web_search_uses_configured_provider_and_limit -v`

Expected: fails because `pre_fetch_results()` does not accept/pass `query`, and `web_search()` does not pass it.

- [ ] **Step 3: Implement minimal code**

Update `src/insight_graph/tools/pre_fetch.py`:

```python
import json

from insight_graph.report_quality.budgeting import get_research_budgets
from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.search_providers import SearchResult


def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
    query: str | None = None,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    fetch_limit = min(limit, get_research_budgets().max_fetches)
    for result in results[:fetch_limit]:
        fetch_query = _fetch_query(result.url, query)
        try:
            evidence.extend(fetch_url(fetch_query, subtask_id))
        except Exception:
            continue
    return evidence


def _fetch_query(url: str, query: str | None) -> str:
    if not query:
        return url
    return json.dumps({"url": url, "query": query}, separators=(",", ":"))
```

Update `src/insight_graph/tools/web_search.py` line calling pre-fetch:

```python
return pre_fetch_results(results, subtask_id, limit=limit, query=query)
```

- [ ] **Step 4: Run tests to verify GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_pre_fetch.py tests/test_web_search.py -q`

Expected: all pre-fetch and web-search tests pass.

### Task 3: Documentation, Verification, Commit, Merge

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] **Step 1: Update docs**

Add an Unreleased changelog bullet for pre-fetch hardening. In `docs/configuration.md`, update the search/fetch text to mention per-result failure isolation, fetch-budget capping, and retrieval-query ranked chunks. In `docs/reference-parity-roadmap.md`, mark pre-search fetch pipeline hardening implemented and make Reporter URL revalidation the next phase.

- [ ] **Step 2: Run full verification**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: pytest passes, ruff reports `All checks passed!`, and `git diff --check` has no whitespace errors except acceptable CRLF warnings before commit.

- [ ] **Step 3: Commit**

Run:

```powershell
git add CHANGELOG.md docs/configuration.md docs/reference-parity-roadmap.md src/insight_graph/tools/pre_fetch.py src/insight_graph/tools/web_search.py tests/test_pre_fetch.py tests/test_web_search.py
git commit -m "feat(search): harden prefetch pipeline"
```

- [ ] **Step 4: Merge and verify on master**

Fast-forward merge the phase branch to `master`, rerun full pytest, ruff, and `git diff --check`, then remove the worktree and branch.
