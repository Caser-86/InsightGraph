# Web Search Mock Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fall back from empty or failed `web_search` results to deterministic `mock_search` evidence while making the fallback visible in `tool_call_log`.

**Architecture:** Keep fallback in `src/insight_graph/agents/executor.py` because executor owns tool execution and `ToolCallRecord` creation. Add a small private fallback helper that reuses the existing dedupe and relevance-filtering path so mock fallback evidence behaves like normal tool evidence while logs remain honest.

**Tech Stack:** Python 3.13, Pydantic state models, pytest, ruff, Typer CLI smoke tests.

---

## File Structure

- Modify `src/insight_graph/agents/executor.py`: detect empty/failed `web_search`, record the failed live attempt, run `mock_search`, and record fallback results.
- Modify `tests/test_executor.py`: cover empty result fallback, exception fallback, fallback failure, relevance filtering on fallback evidence, and non-`web_search` empty behavior.
- Modify `tests/test_cli.py`: cover JSON visibility of fallback tool records through existing `tool_call_log` output.
- Modify `README.md`: document that live preset may fall back to deterministic mock evidence when live search is unavailable or empty.

---

### Task 1: Executor Web Search Empty Fallback

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Modify: `tests/test_executor.py`

- [ ] **Step 1: Write failing empty-result fallback tests**

In `tests/test_executor.py`, add this test after `test_executor_logs_tool_failure_and_continues()`:

```python
def test_executor_falls_back_to_mock_search_for_empty_web_search(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    fallback = Evidence(
        id="fallback",
        subtask_id="collect",
        title="Fallback Evidence",
        source_url="https://example.com/fallback",
        snippet="Fallback evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                return [fallback]
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="Compare AI coding agents",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["fallback"]
    assert updated.global_evidence_pool == updated.evidence_pool
    assert [record.tool_name for record in updated.tool_call_log] == [
        "web_search",
        "mock_search",
    ]
    assert updated.tool_call_log[0].success is False
    assert updated.tool_call_log[0].evidence_count == 0
    assert updated.tool_call_log[0].filtered_count == 0
    assert updated.tool_call_log[0].error == (
        "web_search returned no evidence; falling back to mock_search"
    )
    assert updated.tool_call_log[1].success is True
    assert updated.tool_call_log[1].evidence_count == 1
    assert updated.tool_call_log[1].filtered_count == 0
    assert updated.tool_call_log[1].error == "fallback for web_search"


def test_executor_keeps_successful_empty_results_for_non_web_search(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return []

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["custom_tool"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].tool_name == "custom_tool"
    assert updated.tool_call_log[0].success is True
    assert updated.tool_call_log[0].evidence_count == 0
    assert updated.tool_call_log[0].error is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_executor.py::test_executor_falls_back_to_mock_search_for_empty_web_search tests/test_executor.py::test_executor_keeps_successful_empty_results_for_non_web_search -q
```

Expected: first test FAILS because empty `web_search` is still recorded as successful and no fallback runs; second test PASSES or remains compatible.

- [ ] **Step 3: Implement empty-result fallback**

In `src/insight_graph/agents/executor.py`, add constants near imports:

```python
WEB_SEARCH_TOOL = "web_search"
MOCK_SEARCH_TOOL = "mock_search"
WEB_SEARCH_EMPTY_FALLBACK_ERROR = (
    "web_search returned no evidence; falling back to mock_search"
)
WEB_SEARCH_FALLBACK_NOTE = "fallback for web_search"
```

Replace the normal success block inside `execute_subtasks()` with a helper-based flow. The loop body should call a new `_run_tool_with_fallback()` helper and extend collected evidence with its returned kept evidence:

```python
            kept_results, new_records = _run_tool_with_fallback(
                registry,
                tool_name,
                state.user_request,
                subtask,
                filter_enabled,
                state.llm_call_log,
            )
            collected.extend(kept_results)
            records.extend(new_records)
```

Add these helpers below `execute_subtasks()`:

```python
def _run_tool_with_fallback(
    registry: ToolRegistry,
    tool_name: str,
    query: str,
    subtask: Subtask,
    filter_enabled: bool,
    llm_call_log: list[LLMCallRecord],
) -> tuple[list[Evidence], list[ToolCallRecord]]:
    try:
        results = registry.run(tool_name, query, subtask.id)
    except Exception as exc:
        failed_record = ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            success=False,
            error=str(exc),
        )
        if tool_name != WEB_SEARCH_TOOL:
            return [], [failed_record]
        fallback_results, fallback_records = _run_mock_search_fallback(
            registry, query, subtask, filter_enabled, llm_call_log
        )
        return fallback_results, [failed_record, *fallback_records]

    if tool_name == WEB_SEARCH_TOOL and not results:
        failed_record = ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            success=False,
            error=WEB_SEARCH_EMPTY_FALLBACK_ERROR,
        )
        fallback_results, fallback_records = _run_mock_search_fallback(
            registry, query, subtask, filter_enabled, llm_call_log
        )
        return fallback_results, [failed_record, *fallback_records]

    kept_results, filtered_count = _process_tool_results(
        query, subtask, results, filter_enabled, llm_call_log
    )
    return kept_results, [
        ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=tool_name,
            query=query,
            evidence_count=len(results),
            filtered_count=filtered_count,
        )
    ]
```

Add `_process_tool_results()`:

```python
def _process_tool_results(
    query: str,
    subtask: Subtask,
    results: list[Evidence],
    filter_enabled: bool,
    llm_call_log: list[LLMCallRecord],
) -> tuple[list[Evidence], int]:
    deduped_results = _deduplicate_evidence(results)
    if not filter_enabled:
        return deduped_results, 0
    return filter_relevant_evidence(
        query,
        subtask,
        deduped_results,
        llm_call_log=llm_call_log,
    )
```

Add `_run_mock_search_fallback()`:

```python
def _run_mock_search_fallback(
    registry: ToolRegistry,
    query: str,
    subtask: Subtask,
    filter_enabled: bool,
    llm_call_log: list[LLMCallRecord],
) -> tuple[list[Evidence], list[ToolCallRecord]]:
    try:
        results = registry.run(MOCK_SEARCH_TOOL, query, subtask.id)
    except Exception as exc:
        return [], [
            ToolCallRecord(
                subtask_id=subtask.id,
                tool_name=MOCK_SEARCH_TOOL,
                query=query,
                success=False,
                error=f"fallback for web_search failed: {exc}",
            )
        ]

    kept_results, filtered_count = _process_tool_results(
        query, subtask, results, filter_enabled, llm_call_log
    )
    return kept_results, [
        ToolCallRecord(
            subtask_id=subtask.id,
            tool_name=MOCK_SEARCH_TOOL,
            query=query,
            evidence_count=len(results),
            filtered_count=filtered_count,
            error=WEB_SEARCH_FALLBACK_NOTE,
        )
    ]
```

Update imports to include `LLMCallRecord` and `Subtask`:

```python
from insight_graph.state import Evidence, GraphState, LLMCallRecord, Subtask, ToolCallRecord
```

- [ ] **Step 4: Run executor tests and lint**

Run:

```bash
python -m pytest tests/test_executor.py -q
python -m ruff check src/insight_graph/agents/executor.py tests/test_executor.py
```

Expected: executor tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/insight_graph/agents/executor.py tests/test_executor.py
git commit -m "feat: fallback to mock search for empty web search"
```

---

### Task 2: Exception Fallback And Relevance Filtering

**Files:**
- Modify: `tests/test_executor.py`
- Modify: `src/insight_graph/agents/executor.py` only if Task 1 implementation missed behavior

- [ ] **Step 1: Write failing exception and filtering tests**

Add these tests after the empty fallback tests in `tests/test_executor.py`:

```python
def test_executor_falls_back_to_mock_search_for_web_search_exception(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    fallback = Evidence(
        id="fallback",
        subtask_id="collect",
        title="Fallback Evidence",
        source_url="https://example.com/fallback",
        snippet="Fallback evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                raise RuntimeError("live search unavailable")
            if name == "mock_search":
                return [fallback]
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["fallback"]
    assert [record.tool_name for record in updated.tool_call_log] == [
        "web_search",
        "mock_search",
    ]
    assert updated.tool_call_log[0].success is False
    assert "live search unavailable" in updated.tool_call_log[0].error
    assert updated.tool_call_log[1].success is True
    assert updated.tool_call_log[1].error == "fallback for web_search"


def test_executor_records_failed_mock_search_fallback(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                raise RuntimeError("mock unavailable")
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert updated.evidence_pool == []
    assert [record.tool_name for record in updated.tool_call_log] == [
        "web_search",
        "mock_search",
    ]
    assert updated.tool_call_log[0].success is False
    assert updated.tool_call_log[1].success is False
    assert updated.tool_call_log[1].error == (
        "fallback for web_search failed: mock unavailable"
    )


def test_executor_applies_relevance_filter_to_mock_search_fallback(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    kept = Evidence(
        id="kept",
        subtask_id="collect",
        title="Kept",
        source_url="https://example.com/kept",
        snippet="Kept evidence.",
        verified=True,
    )
    dropped = Evidence(
        id="dropped",
        subtask_id="collect",
        title="Dropped",
        source_url="https://example.com/dropped",
        snippet="Dropped evidence.",
        verified=False,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            if name == "web_search":
                return []
            if name == "mock_search":
                return [kept, dropped]
            raise AssertionError(f"unexpected tool: {name}")

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["web_search"])],
    )

    updated = execute_subtasks(state)

    assert [item.id for item in updated.evidence_pool] == ["kept"]
    assert updated.tool_call_log[1].tool_name == "mock_search"
    assert updated.tool_call_log[1].evidence_count == 2
    assert updated.tool_call_log[1].filtered_count == 1
```

- [ ] **Step 2: Run tests to verify behavior**

Run:

```bash
python -m pytest tests/test_executor.py::test_executor_falls_back_to_mock_search_for_web_search_exception tests/test_executor.py::test_executor_records_failed_mock_search_fallback tests/test_executor.py::test_executor_applies_relevance_filter_to_mock_search_fallback -q
```

Expected: PASS if Task 1 implementation already covered exception fallback and filtering; otherwise FAIL and proceed to Step 3.

- [ ] **Step 3: Fill any missing implementation**

If tests fail, update `src/insight_graph/agents/executor.py` so:

```python
if tool_name != WEB_SEARCH_TOOL:
    return [], [failed_record]
```

is used for non-web exceptions, and both empty and exception `web_search` paths call `_run_mock_search_fallback()`.

Ensure `_run_mock_search_fallback()` calls `_process_tool_results()` so relevance filtering runs for fallback evidence.

- [ ] **Step 4: Run executor tests and lint**

Run:

```bash
python -m pytest tests/test_executor.py -q
python -m ruff check src/insight_graph/agents/executor.py tests/test_executor.py
```

Expected: executor tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add src/insight_graph/agents/executor.py tests/test_executor.py
git commit -m "test: cover web search fallback edge cases"
```

---

### Task 3: JSON Visibility And Documentation

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing/passing CLI JSON visibility test**

Add this test near the existing `--output-json` tests in `tests/test_cli.py`:

```python
def test_cli_research_output_json_includes_tool_fallback_records(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.tool_call_log.extend(
            [
                ToolCallRecord(
                    subtask_id="collect",
                    tool_name="web_search",
                    query=query,
                    success=False,
                    error="web_search returned no evidence; falling back to mock_search",
                ),
                ToolCallRecord(
                    subtask_id="collect",
                    tool_name="mock_search",
                    query=query,
                    evidence_count=3,
                    success=True,
                    error="fallback for web_search",
                ),
            ]
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [record["tool_name"] for record in payload["tool_call_log"]] == [
        "web_search",
        "mock_search",
    ]
    assert payload["tool_call_log"][0]["success"] is False
    assert payload["tool_call_log"][1]["error"] == "fallback for web_search"
```

This test should pass if JSON serialization already exposes tool records. Keep it as regression coverage.

- [ ] **Step 2: Update README**

In `README.md`, update the live preset section after the paragraph that starts with `` `live-llm` applies missing runtime defaults``:

```markdown
If live `web_search` returns no evidence or fails, the executor records the failed `web_search` attempt and falls back to deterministic `mock_search` evidence. This keeps live smoke/demo runs from producing empty reports while making the fallback visible in `tool_call_log` and `--output-json`.
```

- [ ] **Step 3: Run CLI tests and lint**

Run:

```bash
python -m pytest tests/test_cli.py -q
python -m ruff check tests/test_cli.py
```

Expected: CLI tests pass and ruff reports `All checks passed!`.

- [ ] **Step 4: Commit Task 3**

Run:

```bash
git add tests/test_cli.py README.md
git commit -m "docs: document web search fallback"
```

---

### Task 4: Final Verification And Live Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run full verification**

Run:

```bash
python -m pytest -v
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 2: Ensure current checkout is installed editable**

Run:

```bash
python -m pip install -e .
```

Expected: command succeeds and installs `insightgraph==0.1.0` from the current working directory.

- [ ] **Step 3: Run live JSON smoke with User env imported into Process env**

Run:

```powershell
$names = @("INSIGHT_GRAPH_LLM_API_KEY", "INSIGHT_GRAPH_LLM_BASE_URL", "INSIGHT_GRAPH_LLM_MODEL"); foreach ($name in $names) { $value = [Environment]::GetEnvironmentVariable($name, "User"); if (-not [string]::IsNullOrWhiteSpace($value)) { [Environment]::SetEnvironmentVariable($name, $value, "Process"); Set-Item -Path "env:$name" -Value $value } }; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected when DuckDuckGo returns no evidence:

- `tool_call_log` includes failed `web_search` entries.
- `tool_call_log` includes `mock_search` entries with `error="fallback for web_search"`.
- `report_markdown` includes key findings and references from fallback evidence.
- `llm_call_log` includes token fields for attempted LLM calls when provider usage is returned.

- [ ] **Step 4: Inspect final git state**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch.
