# Executor Web Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-stage wenyi-style Executor with tool-call logging, shared evidence pool, evidence deduplication, and explicit web-search opt-in.

**Architecture:** Extend `GraphState` with Executor observability fields, add an `executor.py` agent that owns tool execution, keep `collect_evidence()` as a compatibility wrapper, and make Planner choose `web_search` only when `INSIGHT_GRAPH_USE_WEB_SEARCH` is explicitly enabled.

**Tech Stack:** Python 3.11+, Pydantic, LangGraph, Pytest, Ruff.

---

## File Structure

- Modify: `src/insight_graph/state.py` - add `ToolCallRecord`, `global_evidence_pool`, and `tool_call_log`.
- Modify: `tests/test_state.py` - cover new state defaults.
- Modify: `src/insight_graph/agents/planner.py` - add `INSIGHT_GRAPH_USE_WEB_SEARCH` planner switch.
- Modify: `tests/test_agents.py` - cover default and opt-in planner behavior.
- Create: `src/insight_graph/agents/executor.py` - execute suggested tools, log calls, deduplicate evidence, fill pools.
- Modify: `src/insight_graph/agents/collector.py` - delegate to `execute_subtasks()`.
- Create: `tests/test_executor.py` - executor success, failure, deduplication, and web-search opt-in tests.
- Modify: `README.md` - document first-stage Executor and explicit web-search flow switch.

---

### Task 1: State Model For Executor Observability

**Files:**
- Modify: `src/insight_graph/state.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing state tests**

Modify import in `tests/test_state.py` from:

```python
from insight_graph.state import Evidence, GraphState, Subtask
```

to:

```python
from insight_graph.state import Evidence, GraphState, Subtask, ToolCallRecord
```

Append these tests to `tests/test_state.py`:

```python

def test_tool_call_record_defaults_to_success() -> None:
    record = ToolCallRecord(
        subtask_id="collect",
        tool_name="mock_search",
        query="Compare AI coding agents",
    )

    assert record.evidence_count == 0
    assert record.success is True
    assert record.error is None


def test_graph_state_starts_with_executor_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.global_evidence_pool == []
    assert state.tool_call_log == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_state.py -v`

Expected: FAIL with `ImportError: cannot import name 'ToolCallRecord'` or missing `global_evidence_pool` / `tool_call_log` fields.

- [ ] **Step 3: Implement state model**

Modify `src/insight_graph/state.py` by adding `ToolCallRecord` after `Critique` and adding fields to `GraphState`:

```python
class ToolCallRecord(BaseModel):
    subtask_id: str
    tool_name: str
    query: str
    evidence_count: int = 0
    success: bool = True
    error: str | None = None


class GraphState(BaseModel):
    user_request: str
    subtasks: list[Subtask] = Field(default_factory=list)
    evidence_pool: list[Evidence] = Field(default_factory=list)
    global_evidence_pool: list[Evidence] = Field(default_factory=list)
    tool_call_log: list[ToolCallRecord] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    critique: Critique | None = None
    report_markdown: str | None = None
    iterations: int = 0
```

- [ ] **Step 4: Run state tests**

Run: `python -m pytest tests/test_state.py -v`

Expected: all state tests pass.

- [ ] **Step 5: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/state.py tests/test_state.py
git commit -m "feat: add executor state fields"
```

---

### Task 2: Planner Web Search Opt-In Switch

**Files:**
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Add failing planner tests**

Modify `test_planner_creates_core_research_subtasks` in `tests/test_agents.py` to accept `monkeypatch` and clear the env var:

```python
def test_planner_creates_core_research_subtasks(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")
```

Append this test to `tests/test_agents.py`:

```python

def test_planner_uses_web_search_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]


def test_planner_ignores_non_truthy_web_search_flag(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "0")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["mock_search"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_agents.py::test_planner_creates_core_research_subtasks tests/test_agents.py::test_planner_uses_web_search_when_enabled tests/test_agents.py::test_planner_ignores_non_truthy_web_search_flag -v`

Expected: FAIL because `INSIGHT_GRAPH_USE_WEB_SEARCH=1` still returns `mock_search`.

- [ ] **Step 3: Implement planner switch**

Replace `src/insight_graph/agents/planner.py` with:

```python
import os

from insight_graph.state import GraphState, Subtask


def plan_research(state: GraphState) -> GraphState:
    state.subtasks = [
        Subtask(
            id="scope",
            description="Identify key products, companies, and scope from the user request",
            subtask_type="research",
        ),
        Subtask(
            id="collect",
            description=(
                "Collect evidence about product positioning, features, pricing, and sources"
            ),
            subtask_type="research",
            dependencies=["scope"],
            suggested_tools=[_collection_tool_name()],
        ),
        Subtask(
            id="analyze",
            description="Analyze competitive patterns, differentiators, risks, and trends",
            subtask_type="synthesis",
            dependencies=["collect"],
        ),
        Subtask(
            id="report",
            description="Synthesize findings into a cited research report",
            subtask_type="synthesis",
            dependencies=["analyze"],
        ),
    ]
    return state


def _collection_tool_name() -> str:
    use_web_search = os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "").lower()
    if use_web_search in {"1", "true", "yes"}:
        return "web_search"
    return "mock_search"
```

- [ ] **Step 4: Run planner tests**

Run: `python -m pytest tests/test_agents.py -v`

Expected: all agent tests pass.

- [ ] **Step 5: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/agents/planner.py tests/test_agents.py
git commit -m "feat: add web search planner switch"
```

---

### Task 3: Executor Agent And Collector Wrapper

**Files:**
- Create: `src/insight_graph/agents/executor.py`
- Modify: `src/insight_graph/agents/collector.py`
- Create: `tests/test_executor.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing executor tests**

Create `tests/test_executor.py`:

```python
import importlib

from insight_graph.agents.executor import execute_subtasks
from insight_graph.state import Evidence, GraphState, Subtask


def test_executor_collects_evidence_and_records_success() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[
            Subtask(id="scope", description="Scope"),
            Subtask(
                id="collect",
                description="Collect evidence",
                suggested_tools=["mock_search"],
            ),
        ],
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 3
    assert updated.global_evidence_pool == updated.evidence_pool
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].subtask_id == "collect"
    assert updated.tool_call_log[0].tool_name == "mock_search"
    assert updated.tool_call_log[0].query == "Compare AI coding agents"
    assert updated.tool_call_log[0].evidence_count == 3
    assert updated.tool_call_log[0].success is True
    assert updated.tool_call_log[0].error is None


def test_executor_deduplicates_evidence(monkeypatch) -> None:
    registry_module = importlib.import_module("insight_graph.agents.executor")

    duplicate = Evidence(
        id="same",
        subtask_id="collect",
        title="Same",
        source_url="https://example.com/same",
        snippet="Same evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [duplicate, duplicate.model_copy()]

    monkeypatch.setattr(registry_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])]
    )

    updated = execute_subtasks(state)

    assert len(updated.evidence_pool) == 1
    assert updated.evidence_pool[0].id == "same"
    assert updated.tool_call_log[0].evidence_count == 2


def test_executor_logs_tool_failure_and_continues(monkeypatch) -> None:
    registry_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            raise KeyError("Unknown tool: broken")

    monkeypatch.setattr(registry_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["broken"])]
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert updated.global_evidence_pool == []
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].success is False
    assert updated.tool_call_log[0].evidence_count == 0
    assert "Unknown tool: broken" in updated.tool_call_log[0].error


def test_executor_appends_to_existing_tool_call_log() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["mock_search"])],
    )
    state.tool_call_log.append(
        {
            "subtask_id": "previous",
            "tool_name": "mock_search",
            "query": "previous query",
            "evidence_count": 1,
        }
    )

    updated = execute_subtasks(state)

    assert [record.subtask_id for record in updated.tool_call_log] == ["previous", "collect"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_executor.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.agents.executor'`.

- [ ] **Step 3: Implement executor**

Create `src/insight_graph/agents/executor.py`:

```python
from insight_graph.state import Evidence, GraphState, ToolCallRecord
from insight_graph.tools import ToolRegistry


def execute_subtasks(state: GraphState) -> GraphState:
    registry = ToolRegistry()
    collected: list[Evidence] = []
    records = list(state.tool_call_log)

    for subtask in state.subtasks:
        for tool_name in subtask.suggested_tools:
            try:
                results = registry.run(tool_name, state.user_request, subtask.id)
            except Exception as exc:
                records.append(
                    ToolCallRecord(
                        subtask_id=subtask.id,
                        tool_name=tool_name,
                        query=state.user_request,
                        success=False,
                        error=str(exc),
                    )
                )
                continue

            collected.extend(results)
            records.append(
                ToolCallRecord(
                    subtask_id=subtask.id,
                    tool_name=tool_name,
                    query=state.user_request,
                    evidence_count=len(results),
                )
            )

    deduped = _deduplicate_evidence(collected)
    state.evidence_pool = deduped
    state.global_evidence_pool = deduped
    state.tool_call_log = records
    return state


def _deduplicate_evidence(evidence: list[Evidence]) -> list[Evidence]:
    seen: set[tuple[str, str]] = set()
    deduped: list[Evidence] = []
    for item in evidence:
        key = (item.id, item.source_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
```

Replace `src/insight_graph/agents/collector.py` with:

```python
from insight_graph.agents.executor import execute_subtasks
from insight_graph.state import GraphState


def collect_evidence(state: GraphState) -> GraphState:
    return execute_subtasks(state)
```

- [ ] **Step 4: Update existing collector test expectations**

Modify `test_collector_adds_verified_mock_evidence` in `tests/test_agents.py` to include Executor assertions:

```python
def test_collector_adds_verified_mock_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) >= 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} >= {"official_site", "github"}
    assert updated.global_evidence_pool == updated.evidence_pool
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].tool_name == "mock_search"
```

- [ ] **Step 5: Run executor and agent tests**

Run: `python -m pytest tests/test_executor.py tests/test_agents.py -v`

Expected: all selected tests pass.

- [ ] **Step 6: Run graph and CLI tests**

Run: `python -m pytest tests/test_graph.py tests/test_cli.py -v`

Expected: default graph and CLI tests pass without web-search env vars.

- [ ] **Step 7: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 8: Commit**

```bash
git add src/insight_graph/agents/executor.py src/insight_graph/agents/collector.py tests/test_executor.py tests/test_agents.py
git commit -m "feat: add executor tool execution"
```

---

### Task 4: Web Search Flow Documentation And Final Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README Search Provider section**

In `README.md`, replace the paragraph after the provider config command with:

```markdown
当前 CLI 的 Planner 默认仍选择 `mock_search`，不会因为设置 DuckDuckGo provider 而自动联网。需要让研究流调用 `web_search` 时，显式设置 `INSIGHT_GRAPH_USE_WEB_SEARCH=1`；此时 `INSIGHT_GRAPH_SEARCH_PROVIDER` 再决定 `web_search` 使用 mock provider 还是 DuckDuckGo provider。
```

Update the provider config table to include `INSIGHT_GRAPH_USE_WEB_SEARCH`:

```markdown
| 变量 | 说明 | 默认值 |
|------|------|--------|
| `INSIGHT_GRAPH_USE_WEB_SEARCH` | `1` / `true` / `yes` 时 Planner collect subtask 使用 `web_search` | 未启用 |
| `INSIGHT_GRAPH_SEARCH_PROVIDER` | `mock` 或 `duckduckgo` | `mock` |
| `INSIGHT_GRAPH_SEARCH_LIMIT` | `web_search` 候选 URL pre-fetch 数量 | `3` |
```

Add this note after the table:

```markdown
当前 Executor 是第一阶段实现：它会执行 planned tools、记录 `tool_call_log`、维护 `global_evidence_pool` 并去重 evidence；尚未包含 LLM relevance 判断、多轮 agentic tool loop、conversation compression 或收敛检测。
```

- [ ] **Step 2: Run full verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`. Do not set `INSIGHT_GRAPH_USE_WEB_SEARCH` for this smoke test.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document executor web search switch"
```

---

## Self-Review

- Spec coverage: The plan implements `ToolCallRecord`, `global_evidence_pool`, `tool_call_log`, planner web-search opt-in, Executor tool execution, failure logging, evidence deduplication, collector compatibility, README updates, and default CLI verification.
- Deferred scope: LLM relevance filtering, real multi-round tool-decision loops, conversation compression, convergence detection, PDF/Playwright/Trafilatura/RAG, and default live-network behavior are excluded.
- Placeholder scan: No placeholders remain; each task includes exact file paths, code, commands, expected failures, expected pass conditions, and commit commands.
- Type consistency: `ToolCallRecord`, `GraphState.global_evidence_pool`, `GraphState.tool_call_log`, `execute_subtasks`, `collect_evidence`, and `INSIGHT_GRAPH_USE_WEB_SEARCH` are consistently named across tasks.
