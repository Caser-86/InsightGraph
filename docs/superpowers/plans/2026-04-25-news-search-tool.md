# News Search Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic/offline `news_search` tool and Planner opt-in path so InsightGraph can collect news and announcement evidence without network access.

**Architecture:** Implement `news_search()` as a small tool module returning stable verified `Evidence` records with readable news-oriented `source_type` values. Register and export it through existing tool boundaries, then let Planner choose it only when `INSIGHT_GRAPH_USE_NEWS_SEARCH` is truthy and higher-priority search opt-ins are not truthy.

**Tech Stack:** Python 3.13, Pydantic `Evidence`, existing `ToolRegistry`, pytest, ruff.

---

## File Structure

- Create `src/insight_graph/tools/news_search.py`: deterministic news and announcement evidence tool.
- Modify `src/insight_graph/tools/registry.py`: register `news_search`.
- Modify `src/insight_graph/tools/__init__.py`: export `news_search`.
- Modify `src/insight_graph/agents/planner.py`: add `INSIGHT_GRAPH_USE_NEWS_SEARCH` opt-in selection.
- Modify `tests/test_tools.py`: cover package export, direct tool output, registry execution.
- Modify `tests/test_agents.py`: cover Planner opt-in priority and Collector execution.
- Modify `README.md`: document deterministic news search opt-in.

---

### Task 1: Add News Search Tool And Registry Integration

**Files:**
- Create: `src/insight_graph/tools/news_search.py`
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing tool tests**

In `tests/test_tools.py`, update the tools import from:

```python
from insight_graph.tools import SearchResult, ToolRegistry, fetch_url, github_search, web_search
```

to:

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

Add this test after `test_tools_package_exports_github_search_callable()`:

```python
def test_tools_package_exports_news_search_callable() -> None:
    assert callable(news_search)
```

Add this test after `test_github_search_returns_deterministic_verified_github_evidence()`:

```python
def test_news_search_returns_deterministic_verified_news_evidence() -> None:
    evidence = news_search("AI coding agent funding", "s1")

    assert len(evidence) == 3
    assert [item.id for item in evidence] == [
        "news-github-copilot-changelog",
        "news-openai-codex-update",
        "news-cursor-changelog",
    ]
    assert {item.subtask_id for item in evidence} == {"s1"}
    assert all(item.verified for item in evidence)
    assert [item.source_type for item in evidence] == [
        "news",
        "official_announcement",
        "news",
    ]
    assert [item.source_url for item in evidence] == [
        "https://github.blog/changelog/",
        "https://openai.com/index/introducing-codex/",
        "https://www.cursor.com/changelog",
    ]
```

Add this test after `test_registry_runs_github_search_tool()`:

```python
def test_registry_runs_news_search_tool() -> None:
    evidence = ToolRegistry().run("news_search", "AI coding agent funding", "s1")

    assert len(evidence) == 3
    assert evidence[0].id == "news-github-copilot-changelog"
    assert evidence[0].subtask_id == "s1"
    assert {item.source_type for item in evidence} == {"news", "official_announcement"}
```

- [ ] **Step 2: Run tool tests and verify RED**

Run:

```powershell
python -m pytest tests/test_tools.py::test_tools_package_exports_news_search_callable tests/test_tools.py::test_news_search_returns_deterministic_verified_news_evidence tests/test_tools.py::test_registry_runs_news_search_tool -q
```

Expected: FAIL during import because `news_search` is not exported yet, or FAIL because the registry does not know `news_search`.

- [ ] **Step 3: Implement deterministic news search tool**

Create `src/insight_graph/tools/news_search.py`:

```python
from insight_graph.state import Evidence


def news_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    return [
        Evidence(
            id="news-github-copilot-changelog",
            subtask_id=subtask_id,
            title="GitHub Copilot Product Changelog",
            source_url="https://github.blog/changelog/",
            snippet=(
                "GitHub's changelog publishes product updates and release notes for "
                "GitHub Copilot and adjacent developer platform features."
            ),
            source_type="news",
            verified=True,
        ),
        Evidence(
            id="news-openai-codex-update",
            subtask_id=subtask_id,
            title="OpenAI Codex Product Update",
            source_url="https://openai.com/index/introducing-codex/",
            snippet=(
                "OpenAI's Codex announcement describes product capabilities and release "
                "context for cloud-based coding assistance."
            ),
            source_type="official_announcement",
            verified=True,
        ),
        Evidence(
            id="news-cursor-changelog",
            subtask_id=subtask_id,
            title="Cursor Product Changelog",
            source_url="https://www.cursor.com/changelog",
            snippet=(
                "Cursor's changelog tracks product updates, feature launches, and release "
                "signals for the AI coding editor."
            ),
            source_type="news",
            verified=True,
        ),
    ]
```

- [ ] **Step 4: Register and export the tool**

In `src/insight_graph/tools/registry.py`, add the import:

```python
from insight_graph.tools.news_search import news_search
```

Add the registry entry between `mock_search` and `web_search` entries:

```python
            "news_search": news_search,
```

In `src/insight_graph/tools/__init__.py`, add the import:

```python
from insight_graph.tools.news_search import news_search
```

Update `__all__` to:

```python
__all__ = [
    "SearchResult",
    "ToolRegistry",
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
python -m ruff check src/insight_graph/tools/news_search.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src/insight_graph/tools/news_search.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
git commit -m "feat: add deterministic news search tool"
```

---

### Task 2: Add Planner Opt-in And Collector Coverage

**Files:**
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing Planner tests**

In `tests/test_agents.py`, update `clear_llm_env()` to also clear the news search flag by adding this string to the list:

```python
        "INSIGHT_GRAPH_USE_NEWS_SEARCH",
```

Update `test_planner_creates_core_research_subtasks()` to clear all search flags at the top:

```python
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
```

Add this test after `test_planner_uses_github_search_when_enabled()`:

```python
def test_planner_uses_news_search_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["news_search"]
```

Add this test after `test_planner_prefers_web_search_over_github_search()`:

```python
def test_planner_prefers_github_search_over_news_search(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["github_search"]
```

Add this test after it:

```python
def test_planner_prefers_web_search_over_news_search(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]
```

Update `test_planner_ignores_non_truthy_web_search_flag()` to also set non-truthy news search:

```python
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "0")
```

- [ ] **Step 2: Write failing Collector test**

Add this test after `test_collector_adds_verified_github_search_evidence()`:

```python
def test_collector_adds_verified_news_search_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) == 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} == {
        "news",
        "official_announcement",
    }
    assert updated.tool_call_log[0].tool_name == "news_search"
```

- [ ] **Step 3: Run agent tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_news_search_when_enabled tests/test_agents.py::test_planner_prefers_github_search_over_news_search tests/test_agents.py::test_planner_prefers_web_search_over_news_search tests/test_agents.py::test_collector_adds_verified_news_search_evidence -q
```

Expected: FAIL because Planner does not yet select `news_search`.

- [ ] **Step 4: Implement Planner opt-in**

Replace `_collection_tool_name()` in `src/insight_graph/agents/planner.py` with:

```python
def _collection_tool_name() -> str:
    if _is_truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"):
        return "web_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"):
        return "github_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_NEWS_SEARCH"):
        return "news_search"
    return "mock_search"
```

Keep the existing helper unchanged:

```python
def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}
```

- [ ] **Step 5: Run agent tests and lint**

Run:

```powershell
python -m pytest tests/test_agents.py -q
python -m ruff check src/insight_graph/agents/planner.py tests/test_agents.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add src/insight_graph/agents/planner.py tests/test_agents.py
git commit -m "feat: let planner opt into news search"
```

---

### Task 3: Document News Search Opt-in

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update Search Provider configuration table**

In `README.md`, in the Search Provider configuration table, add this row after `INSIGHT_GRAPH_USE_GITHUB_SEARCH`:

```markdown
| `INSIGHT_GRAPH_USE_NEWS_SEARCH` | `1` / `true` / `yes` 时 Planner collect subtask 使用 deterministic `news_search`；若同时启用 web 或 GitHub search，则前者优先 | 未启用 |
```

- [ ] **Step 2: Add News search explanatory paragraph**

After the paragraph that starts with `需要只采集 GitHub 风格证据而不访问公网时`, add:

```markdown
需要只采集新闻和产品公告风格证据而不访问公网时，可设置 `INSIGHT_GRAPH_USE_NEWS_SEARCH=1`。第一版 `news_search` 是 deterministic/offline 工具，返回稳定 verified news/announcement evidence，不调用新闻 API、不需要 token，也不受 rate limit 影响。若同时启用 `INSIGHT_GRAPH_USE_WEB_SEARCH` 或 `INSIGHT_GRAPH_USE_GITHUB_SEARCH`，Planner 会按 web search、GitHub search、news search、mock search 的顺序选择第一个启用工具。
```

- [ ] **Step 3: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_news_search_when_enabled tests/test_tools.py::test_registry_runs_news_search_tool -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document news search opt in"
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
Remove-Item Env:\INSIGHT_GRAPH_USE_NEWS_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected: JSON is parseable and `tool_call_log[0].tool_name` is `mock_search`.

- [ ] **Step 5: Run News opt-in CLI smoke**

Run:

```powershell
$env:INSIGHT_GRAPH_USE_NEWS_SEARCH = "1"; Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected: JSON is parseable and `tool_call_log[0].tool_name` is `news_search`.

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
