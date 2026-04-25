# GitHub Search Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic/offline `github_search` tool and Planner opt-in path so InsightGraph can collect GitHub evidence without network access.

**Architecture:** Implement `github_search()` as a small tool module returning stable verified `Evidence` records with `source_type="github"`. Register and export it through existing tool boundaries, then let Planner choose it only when `INSIGHT_GRAPH_USE_GITHUB_SEARCH` is truthy and `INSIGHT_GRAPH_USE_WEB_SEARCH` is not truthy.

**Tech Stack:** Python 3.13, Pydantic `Evidence`, existing `ToolRegistry`, pytest, ruff.

---

## File Structure

- Create `src/insight_graph/tools/github_search.py`: deterministic GitHub evidence tool.
- Modify `src/insight_graph/tools/registry.py`: register `github_search`.
- Modify `src/insight_graph/tools/__init__.py`: export `github_search`.
- Modify `src/insight_graph/agents/planner.py`: add `INSIGHT_GRAPH_USE_GITHUB_SEARCH` opt-in selection.
- Modify `tests/test_tools.py`: cover package export, direct tool output, registry execution.
- Modify `tests/test_agents.py`: cover Planner opt-in and Collector execution.
- Modify `README.md`: document deterministic GitHub search opt-in.

---

### Task 1: Add GitHub Search Tool And Registry Integration

**Files:**
- Create: `src/insight_graph/tools/github_search.py`
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing tool tests**

In `tests/test_tools.py`, update the tools import from:

```python
from insight_graph.tools import SearchResult, ToolRegistry, fetch_url, web_search
```

to:

```python
from insight_graph.tools import SearchResult, ToolRegistry, fetch_url, github_search, web_search
```

Add this test after `test_tools_package_exports_web_search_callable_and_search_result()`:

```python
def test_tools_package_exports_github_search_callable() -> None:
    assert callable(github_search)
```

Add this test after that export test:

```python
def test_github_search_returns_deterministic_verified_github_evidence() -> None:
    evidence = github_search("Compare Cursor, OpenCode, and GitHub Copilot", "s1")

    assert len(evidence) == 3
    assert [item.id for item in evidence] == [
        "github-opencode-repository",
        "github-copilot-docs-content",
        "github-ai-coding-assistant-ecosystem",
    ]
    assert {item.subtask_id for item in evidence} == {"s1"}
    assert all(item.verified for item in evidence)
    assert all(item.source_type == "github" for item in evidence)
    assert [item.source_url for item in evidence] == [
        "https://github.com/sst/opencode",
        "https://github.com/github/docs/tree/main/content/copilot",
        "https://github.com/safishamsi/graphify",
    ]
```

Add this test after `test_registry_runs_web_search_tool()`:

```python
def test_registry_runs_github_search_tool() -> None:
    evidence = ToolRegistry().run("github_search", "Compare AI coding agents", "s1")

    assert len(evidence) == 3
    assert evidence[0].id == "github-opencode-repository"
    assert evidence[0].subtask_id == "s1"
    assert all(item.source_type == "github" for item in evidence)
```

- [ ] **Step 2: Run tool tests and verify RED**

Run:

```powershell
python -m pytest tests/test_tools.py::test_tools_package_exports_github_search_callable tests/test_tools.py::test_github_search_returns_deterministic_verified_github_evidence tests/test_tools.py::test_registry_runs_github_search_tool -q
```

Expected: FAIL during import because `github_search` is not exported yet, or FAIL because the registry does not know `github_search`.

- [ ] **Step 3: Implement deterministic GitHub search tool**

Create `src/insight_graph/tools/github_search.py`:

```python
from insight_graph.state import Evidence


def github_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    return [
        Evidence(
            id="github-opencode-repository",
            subtask_id=subtask_id,
            title="OpenCode Repository",
            source_url="https://github.com/sst/opencode",
            snippet=(
                "The OpenCode repository provides public project information, README "
                "content, and release history for an AI coding tool."
            ),
            source_type="github",
            verified=True,
        ),
        Evidence(
            id="github-copilot-docs-content",
            subtask_id=subtask_id,
            title="GitHub Docs Copilot Content",
            source_url="https://github.com/github/docs/tree/main/content/copilot",
            snippet=(
                "The GitHub Docs repository contains public Copilot documentation content "
                "covering product behavior, integrations, and enterprise guidance."
            ),
            source_type="github",
            verified=True,
        ),
        Evidence(
            id="github-ai-coding-assistant-ecosystem",
            subtask_id=subtask_id,
            title="AI Coding Assistant Ecosystem Repository",
            source_url="https://github.com/safishamsi/graphify",
            snippet=(
                "This GitHub repository describes AI coding assistant tooling across "
                "Claude Code, Codex, OpenCode, Cursor, Gemini CLI, and GitHub Copilot CLI."
            ),
            source_type="github",
            verified=True,
        ),
    ]
```

- [ ] **Step 4: Register and export the tool**

In `src/insight_graph/tools/registry.py`, add the import:

```python
from insight_graph.tools.github_search import github_search
```

Add the registry entry between `fetch_url` and `mock_search` entries:

```python
            "github_search": github_search,
```

In `src/insight_graph/tools/__init__.py`, add the import:

```python
from insight_graph.tools.github_search import github_search
```

Update `__all__` to:

```python
__all__ = ["SearchResult", "ToolRegistry", "fetch_url", "github_search", "web_search"]
```

- [ ] **Step 5: Run tool tests and lint**

Run:

```powershell
python -m pytest tests/test_tools.py -q
python -m ruff check src/insight_graph/tools/github_search.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 1**

Run:

```powershell
git add src/insight_graph/tools/github_search.py src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
git commit -m "feat: add deterministic github search tool"
```

---

### Task 2: Add Planner Opt-in And Collector Coverage

**Files:**
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing Planner tests**

In `tests/test_agents.py`, update `clear_llm_env()` to also clear the GitHub search flag by adding this string to the list:

```python
        "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
```

Update `test_planner_creates_core_research_subtasks()` to clear both search flags at the top:

```python
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
```

Add this test after `test_planner_uses_web_search_when_enabled()`:

```python
def test_planner_uses_github_search_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["github_search"]
```

Add this test after it:

```python
def test_planner_prefers_web_search_over_github_search(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]
```

Update `test_planner_ignores_non_truthy_web_search_flag()` to also set non-truthy GitHub search:

```python
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "0")
```

- [ ] **Step 2: Write failing Collector test**

Add this test after `test_collector_adds_verified_mock_evidence()`:

```python
def test_collector_adds_verified_github_search_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) == 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} == {"github"}
    assert updated.tool_call_log[0].tool_name == "github_search"
```

- [ ] **Step 3: Run agent tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_github_search_when_enabled tests/test_agents.py::test_planner_prefers_web_search_over_github_search tests/test_agents.py::test_collector_adds_verified_github_search_evidence -q
```

Expected: FAIL because Planner does not yet select `github_search`.

- [ ] **Step 4: Implement Planner opt-in**

Replace `_collection_tool_name()` in `src/insight_graph/agents/planner.py` with:

```python
def _collection_tool_name() -> str:
    if _is_truthy_env("INSIGHT_GRAPH_USE_WEB_SEARCH"):
        return "web_search"
    if _is_truthy_env("INSIGHT_GRAPH_USE_GITHUB_SEARCH"):
        return "github_search"
    return "mock_search"


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
git commit -m "feat: let planner opt into github search"
```

---

### Task 3: Document GitHub Search Opt-in

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update Search Provider configuration table**

In `README.md`, in the Search Provider configuration table, add this row after `INSIGHT_GRAPH_USE_WEB_SEARCH`:

```markdown
| `INSIGHT_GRAPH_USE_GITHUB_SEARCH` | `1` / `true` / `yes` 时 Planner collect subtask 使用 deterministic `github_search`；若同时启用 web search，则 web search 优先 | 未启用 |
```

- [ ] **Step 2: Add GitHub search explanatory paragraph**

After the paragraph that starts with `当前 CLI 的 Planner 默认仍选择`, add:

```markdown
需要只采集 GitHub 风格证据而不访问公网时，可设置 `INSIGHT_GRAPH_USE_GITHUB_SEARCH=1`。第一版 `github_search` 是 deterministic/offline 工具，返回稳定 verified GitHub evidence，不调用 GitHub API、不需要 token，也不受 rate limit 影响。后续 live GitHub provider 会单独设计。
```

- [ ] **Step 3: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_agents.py::test_planner_uses_github_search_when_enabled tests/test_tools.py::test_registry_runs_github_search_tool -q
python -m ruff check .
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 4: Commit Task 3**

Run:

```powershell
git add README.md
git commit -m "docs: document github search opt in"
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
Remove-Item Env:\INSIGHT_GRAPH_USE_GITHUB_SEARCH -ErrorAction SilentlyContinue; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected: JSON is parseable and `tool_call_log[0].tool_name` is `mock_search`.

- [ ] **Step 5: Run GitHub opt-in CLI smoke**

Run:

```powershell
$env:INSIGHT_GRAPH_USE_GITHUB_SEARCH = "1"; Remove-Item Env:\INSIGHT_GRAPH_USE_WEB_SEARCH -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected: JSON is parseable and `tool_call_log[0].tool_name` is `github_search`.

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
