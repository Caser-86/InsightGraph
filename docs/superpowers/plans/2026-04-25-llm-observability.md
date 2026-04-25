# LLM Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add in-memory LLM call metadata logging to `GraphState` for live relevance, Analyst, and Reporter calls without recording prompts, responses, or secrets.

**Architecture:** Add an `LLMCallRecord` state model plus a small helper module for timing and sanitized error summaries. Analyst and Reporter append one record per attempted LLM call; relevance appends one record per attempted OpenAI-compatible evidence judgment through the executor/filter path. Deterministic/offline paths do not create LLM records.

**Tech Stack:** Python 3.13, Pydantic, pytest, ruff, existing InsightGraph LLM client abstractions.

---

## File Structure

- Modify `src/insight_graph/state.py`: add `LLMCallRecord` and `GraphState.llm_call_log`.
- Create `src/insight_graph/llm/observability.py`: helper functions for duration measurement, error sanitization, and record creation.
- Modify `src/insight_graph/agents/analyst.py`: append success/failure records for attempted LLM Analyst calls.
- Modify `src/insight_graph/agents/reporter.py`: append success/failure records for attempted LLM Reporter calls.
- Modify `src/insight_graph/agents/relevance.py`: allow OpenAI-compatible relevance judge/filtering to append records.
- Modify `src/insight_graph/agents/executor.py`: pass `state.llm_call_log` into relevance filtering.
- Modify `tests/test_state.py`, `tests/test_agents.py`, `tests/test_relevance.py`, `tests/test_graph.py`: add observability coverage.
- Modify `README.md`: document `GraphState.llm_call_log` privacy-safe metadata.

---

### Task 1: Add LLM Call Record State And Helper

**Files:**
- Modify: `src/insight_graph/state.py`
- Create: `src/insight_graph/llm/observability.py`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing state/helper tests**

Update the import in `tests/test_state.py`:

```python
from insight_graph.llm.observability import build_llm_call_record
from insight_graph.state import Evidence, GraphState, LLMCallRecord, Subtask, ToolCallRecord
```

Add these tests at the end of `tests/test_state.py`:

```python
def test_llm_call_record_stores_metadata_only() -> None:
    record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
    )

    assert record.stage == "analyst"
    assert record.provider == "llm"
    assert record.model == "relay-model"
    assert record.success is True
    assert record.duration_ms == 12
    assert record.error is None


def test_graph_state_starts_with_empty_llm_call_log() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.llm_call_log == []


def test_build_llm_call_record_sanitizes_secret_values() -> None:
    record = build_llm_call_record(
        stage="reporter",
        provider="llm",
        model="relay-model",
        success=False,
        duration_ms=3,
        error=RuntimeError("request failed for sk-secret-value"),
        secrets=["sk-secret-value"],
    )

    assert record.error == "RuntimeError: request failed for [REDACTED]"
    assert "sk-secret-value" not in record.model_dump_json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_state.py::test_llm_call_record_stores_metadata_only tests/test_state.py::test_graph_state_starts_with_empty_llm_call_log tests/test_state.py::test_build_llm_call_record_sanitizes_secret_values -q
```

Expected: FAIL with import errors because `LLMCallRecord` and `build_llm_call_record` do not exist yet.

- [ ] **Step 3: Add state model**

In `src/insight_graph/state.py`, add this class after `ToolCallRecord`:

```python
class LLMCallRecord(BaseModel):
    stage: str
    provider: str
    model: str
    success: bool
    duration_ms: int
    error: str | None = None
```

Add this field to `GraphState` after `tool_call_log`:

```python
llm_call_log: list[LLMCallRecord] = Field(default_factory=list)
```

- [ ] **Step 4: Add observability helper**

Create `src/insight_graph/llm/observability.py`:

```python
from __future__ import annotations

from insight_graph.state import LLMCallRecord


def build_llm_call_record(
    *,
    stage: str,
    provider: str,
    model: str,
    success: bool,
    duration_ms: int,
    error: Exception | None = None,
    secrets: list[str | None] | None = None,
) -> LLMCallRecord:
    return LLMCallRecord(
        stage=stage,
        provider=provider,
        model=model,
        success=success,
        duration_ms=max(duration_ms, 0),
        error=_summarize_error(error, secrets or []) if error is not None else None,
    )


def _summarize_error(error: Exception, secrets: list[str | None]) -> str:
    summary = f"{type(error).__name__}: {error}"
    for secret in secrets:
        if secret:
            summary = summary.replace(secret, "[REDACTED]")
    return summary
```

- [ ] **Step 5: Run state/helper tests to verify they pass**

Run:

```bash
python -m pytest tests/test_state.py::test_llm_call_record_stores_metadata_only tests/test_state.py::test_graph_state_starts_with_empty_llm_call_log tests/test_state.py::test_build_llm_call_record_sanitizes_secret_values -q
```

Expected: PASS.

- [ ] **Step 6: Run state tests and lint**

Run:

```bash
python -m pytest tests/test_state.py -q
python -m ruff check src/insight_graph/state.py src/insight_graph/llm/observability.py tests/test_state.py
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add src/insight_graph/state.py src/insight_graph/llm/observability.py tests/test_state.py
git commit -m "feat: add llm call log state"
```

---

### Task 2: Record Analyst And Reporter LLM Calls

**Files:**
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write failing Analyst/Reporter tests**

Add these tests to `tests/test_agents.py` near the existing Analyst and Reporter LLM tests:

```python
def test_analyze_evidence_records_successful_llm_call(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")
    client = FakeLLMClient(
        content=(
            '{"findings": [{"title": "Pricing differs", '
            '"summary": "Cursor and Copilot differ.", '
            '"evidence_ids": ["cursor-pricing"]}]}'
        )
    )

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "analyst"
    assert record.provider == "llm"
    assert record.model == "relay-model"
    assert record.success is True
    assert record.duration_ms >= 0
    assert record.error is None


def test_analyze_evidence_records_failed_llm_call_without_prompt_or_response(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")

    updated = analyze_evidence(
        make_analyst_state(), llm_client=FakeLLMClient(content="not json")
    )

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "analyst"
    assert record.success is False
    assert "JSON" in (record.error or "")
    serialized = record.model_dump_json()
    assert "not json" not in serialized
    assert "Cursor Pricing" not in serialized


def test_write_report_records_successful_llm_call(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")
    client = FakeLLMClient(
        content={
            "markdown": (
                "# InsightGraph Research Report\n\n"
                "## Key Findings\n\n"
                "### Pricing and packaging differ\n\n"
                "The verified sources support this comparison [1]."
            )
        }
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "reporter"
    assert record.provider == "llm"
    assert record.model == "relay-model"
    assert record.success is True
    assert record.duration_ms >= 0
    assert record.error is None


def test_write_report_records_failed_llm_call_without_prompt_or_response(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")

    updated = write_report(make_reporter_state(), llm_client=FakeLLMClient(content="not json"))

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "reporter"
    assert record.success is False
    assert "JSON" in (record.error or "")
    serialized = record.model_dump_json()
    assert "not json" not in serialized
    assert "Cursor Pricing" not in serialized
```

- [ ] **Step 2: Run new tests to verify they fail**

Run:

```bash
python -m pytest tests/test_agents.py::test_analyze_evidence_records_successful_llm_call tests/test_agents.py::test_analyze_evidence_records_failed_llm_call_without_prompt_or_response tests/test_agents.py::test_write_report_records_successful_llm_call tests/test_agents.py::test_write_report_records_failed_llm_call_without_prompt_or_response -q
```

Expected: FAIL because no LLM call records are appended yet.

- [ ] **Step 3: Implement Analyst recording**

Update imports in `src/insight_graph/agents/analyst.py`:

```python
import time

from insight_graph.llm.observability import build_llm_call_record
```

In `_analyze_evidence_with_llm()`, resolve config before any client setup and wrap only the `complete_json()` call:

```python
    config = resolve_llm_config()
    if llm_client is None:
        if not config.api_key:
            raise ValueError("LLM api_key is required")
        llm_client = get_llm_client(config)

    messages = _build_analyst_messages(state)
    started = time.perf_counter()
    try:
        content = llm_client.complete_json(messages)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="analyst",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise ValueError("LLM analyst failed.") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    try:
        state.findings = _parse_analyst_findings(content, state.evidence_pool)
    except ValueError as exc:
        state.llm_call_log.append(
            build_llm_call_record(
                stage="analyst",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise

    state.llm_call_log.append(
        build_llm_call_record(
            stage="analyst",
            provider="llm",
            model=config.model,
            success=True,
            duration_ms=duration_ms,
            secrets=[config.api_key],
        )
    )
    return state
```

Remove the previous `config = resolve_llm_config()` inside the `if llm_client is None` block to avoid duplicate definitions.

- [ ] **Step 4: Implement Reporter recording**

Update imports in `src/insight_graph/agents/reporter.py`:

```python
import time

from insight_graph.llm.observability import build_llm_call_record
```

In `_write_report_with_llm()`, resolve config before client setup and wrap only the `complete_json()` call:

```python
    config = resolve_llm_config()
    if llm_client is None:
        if not config.api_key:
            raise ReporterFallbackError("LLM api_key is required")
        llm_client = get_llm_client(config)

    messages = _build_reporter_messages(state, verified_evidence, reference_numbers)
    started = time.perf_counter()
    try:
        content = llm_client.complete_json(messages)
    except (ValueError, TypeError) as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise
    except Exception as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise ReporterFallbackError("LLM reporter failed.") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    try:
        body = _parse_llm_report_body(content)
        body = _strip_references_section(body)
        body = _normalize_smart_punctuation(body)
        _validate_llm_report_body(body, set(reference_numbers.values()))
    except ReporterFallbackError as exc:
        state.llm_call_log.append(
            build_llm_call_record(
                stage="reporter",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                error=exc,
                secrets=[config.api_key],
            )
        )
        raise

    state.llm_call_log.append(
        build_llm_call_record(
            stage="reporter",
            provider="llm",
            model=config.model,
            success=True,
            duration_ms=duration_ms,
            secrets=[config.api_key],
        )
    )
```

Keep the existing final report assembly after this block.

- [ ] **Step 5: Run Analyst/Reporter tests to verify they pass**

Run:

```bash
python -m pytest tests/test_agents.py::test_analyze_evidence_records_successful_llm_call tests/test_agents.py::test_analyze_evidence_records_failed_llm_call_without_prompt_or_response tests/test_agents.py::test_write_report_records_successful_llm_call tests/test_agents.py::test_write_report_records_failed_llm_call_without_prompt_or_response -q
```

Expected: PASS.

- [ ] **Step 6: Run agents tests and lint**

Run:

```bash
python -m pytest tests/test_agents.py -q
python -m ruff check src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py tests/test_agents.py
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 7: Commit Task 2**

Run:

```bash
git add src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py tests/test_agents.py
git commit -m "feat: record analyst and reporter llm calls"
```

---

### Task 3: Record Relevance LLM Calls

**Files:**
- Modify: `src/insight_graph/agents/relevance.py`
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_relevance.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing relevance tests**

Add this import to `tests/test_relevance.py`:

```python
from insight_graph.state import LLMCallRecord
```

Add these tests near existing OpenAI-compatible relevance tests:

```python
def test_openai_compatible_judge_records_successful_llm_call() -> None:
    records: list[LLMCallRecord] = []
    client = FakeChatCompletionClient(
        '{"relevant": true, "reason": "Evidence directly matches."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
        model="relay-model",
        llm_call_log=records,
    )
    evidence = make_evidence(id="observed-kept")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is True
    assert len(records) == 1
    assert records[0].stage == "relevance"
    assert records[0].provider == "openai_compatible"
    assert records[0].model == "relay-model"
    assert records[0].success is True
    assert records[0].duration_ms >= 0
    assert records[0].error is None


def test_openai_compatible_judge_records_failed_llm_call_without_prompt_or_key() -> None:
    records: list[LLMCallRecord] = []
    client = FakeChatCompletionClient(error=RuntimeError("boom test-key"))
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
        model="relay-model",
        llm_call_log=records,
    )
    evidence = make_evidence(id="observed-failed")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert len(records) == 1
    record = records[0]
    assert record.stage == "relevance"
    assert record.success is False
    assert "[REDACTED]" in (record.error or "")
    serialized = record.model_dump_json()
    assert "test-key" not in serialized
    assert "Cursor Pricing" not in serialized
```

- [ ] **Step 2: Write failing executor integration test**

Add this test to `tests/test_executor.py` near relevance filtering tests:

```python
def test_executor_passes_llm_call_log_to_relevance_filter(monkeypatch) -> None:
    executor_module = importlib.import_module("insight_graph.agents.executor")
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", "1")

    evidence = Evidence(
        id="verified",
        subtask_id="collect",
        title="Verified",
        source_url="https://example.com/verified",
        snippet="Verified evidence.",
        verified=True,
    )

    class FakeRegistry:
        def run(self, name: str, query: str, subtask_id: str):
            return [evidence]

    def fake_filter_relevant_evidence(query, subtask, evidence, judge=None, llm_call_log=None):
        assert llm_call_log is not None
        llm_call_log.append(
            LLMCallRecord(
                stage="relevance",
                provider="openai_compatible",
                model="relay-model",
                success=True,
                duration_ms=1,
            )
        )
        return evidence, 0

    monkeypatch.setattr(executor_module, "ToolRegistry", FakeRegistry)
    monkeypatch.setattr(
        executor_module, "filter_relevant_evidence", fake_filter_relevant_evidence
    )
    state = GraphState(
        user_request="query",
        subtasks=[Subtask(id="collect", description="Collect", suggested_tools=["fake"])],
    )

    updated = execute_subtasks(state)

    assert len(updated.llm_call_log) == 1
    assert updated.llm_call_log[0].stage == "relevance"
```

Also update `tests/test_executor.py` imports to include `LLMCallRecord` if needed:

```python
from insight_graph.state import Evidence, GraphState, LLMCallRecord, Subtask
```

- [ ] **Step 3: Run new relevance/executor tests to verify they fail**

Run:

```bash
python -m pytest tests/test_relevance.py::test_openai_compatible_judge_records_successful_llm_call tests/test_relevance.py::test_openai_compatible_judge_records_failed_llm_call_without_prompt_or_key tests/test_executor.py::test_executor_passes_llm_call_log_to_relevance_filter -q
```

Expected: FAIL because relevance logging and executor log passing do not exist yet.

- [ ] **Step 4: Implement relevance logging**

Update imports in `src/insight_graph/agents/relevance.py`:

```python
import time

from insight_graph.llm.observability import build_llm_call_record
from insight_graph.state import Evidence, LLMCallRecord, Subtask
```

Update `OpenAICompatibleRelevanceJudge.__init__()` signature and store the log:

```python
        llm_call_log: list[LLMCallRecord] | None = None,
    ) -> None:
        ...
        self._llm_call_log = llm_call_log
```

In `judge()`, wrap only the LLM client call and append records when `_llm_call_log` is not `None`:

```python
        started = time.perf_counter()
        try:
            content = self._client.complete_json(
                _build_relevance_messages(query, subtask, evidence)
            )
        except ValueError as exc:
            self._record_llm_call(False, started, exc)
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge returned invalid JSON.",
            )
        except Exception as exc:
            self._record_llm_call(False, started, exc)
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason=f"OpenAI-compatible relevance judge failed: {exc}",
            )

        try:
            decision = _parse_relevance_json(content, evidence.id)
        except ValueError as exc:
            self._record_llm_call(False, started, exc)
            return EvidenceRelevanceDecision(
                evidence_id=evidence.id,
                relevant=False,
                reason="OpenAI-compatible relevance judge returned invalid JSON.",
            )

        self._record_llm_call(True, started)
        return decision
```

Add this private method to `OpenAICompatibleRelevanceJudge`:

```python
    def _record_llm_call(
        self,
        success: bool,
        started: float,
        error: Exception | None = None,
    ) -> None:
        if self._llm_call_log is None:
            return
        duration_ms = int((time.perf_counter() - started) * 1000)
        self._llm_call_log.append(
            build_llm_call_record(
                stage="relevance",
                provider="openai_compatible",
                model=self._config.model,
                success=success,
                duration_ms=duration_ms,
                error=error,
                secrets=[self._config.api_key],
            )
        )
```

Do not record when `self._config.api_key` is missing, because no LLM call is attempted.

- [ ] **Step 5: Thread log through relevance factory and filter**

Update signatures in `src/insight_graph/agents/relevance.py`:

```python
def get_relevance_judge(
    name: str | None = None,
    llm_call_log: list[LLMCallRecord] | None = None,
) -> RelevanceJudge:
```

When creating `OpenAICompatibleRelevanceJudge`, pass `llm_call_log=llm_call_log`.

Update `filter_relevant_evidence()` signature:

```python
def filter_relevant_evidence(
    query: str,
    subtask: Subtask,
    evidence: list[Evidence],
    judge: RelevanceJudge | None = None,
    llm_call_log: list[LLMCallRecord] | None = None,
) -> tuple[list[Evidence], int]:
    active_judge = judge or get_relevance_judge(llm_call_log=llm_call_log)
```

- [ ] **Step 6: Pass state log from executor**

Update the relevance filtering call in `src/insight_graph/agents/executor.py`:

```python
                kept_results, filtered_count = filter_relevant_evidence(
                    state.user_request,
                    subtask,
                    deduped_results,
                    llm_call_log=state.llm_call_log,
                )
```

- [ ] **Step 7: Run new relevance/executor tests to verify they pass**

Run:

```bash
python -m pytest tests/test_relevance.py::test_openai_compatible_judge_records_successful_llm_call tests/test_relevance.py::test_openai_compatible_judge_records_failed_llm_call_without_prompt_or_key tests/test_executor.py::test_executor_passes_llm_call_log_to_relevance_filter -q
```

Expected: PASS.

- [ ] **Step 8: Run relevance/executor tests and lint**

Run:

```bash
python -m pytest tests/test_relevance.py tests/test_executor.py -q
python -m ruff check src/insight_graph/agents/relevance.py src/insight_graph/agents/executor.py tests/test_relevance.py tests/test_executor.py
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add src/insight_graph/agents/relevance.py src/insight_graph/agents/executor.py tests/test_relevance.py tests/test_executor.py
git commit -m "feat: record relevance llm calls"
```

---

### Task 4: Verify Offline Graph And Document Observability

**Files:**
- Modify: `tests/test_graph.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing offline graph test assertion**

In `tests/test_graph.py`, update `test_run_research_executes_full_graph()` to assert no default LLM records:

```python
    assert result.llm_call_log == []
```

Run:

```bash
python -m pytest tests/test_graph.py::test_run_research_executes_full_graph -q
```

Expected: PASS if previous tasks kept default offline behavior unchanged. If it fails, fix the code path that appends records during deterministic/offline execution before continuing.

- [ ] **Step 2: Add README observability section**

Add this section after `### Live LLM Preset` in `README.md`:

```markdown
### LLM Observability

Live LLM paths populate `GraphState.llm_call_log` with metadata for attempted LLM calls. Each record includes the stage (`relevance`, `analyst`, or `reporter`), provider, model, success flag, duration in milliseconds, and a short sanitized error summary when a call fails.

The log is in-memory only for this MVP. It does not store prompts, completions, raw response JSON, API keys, authorization headers, or request bodies.
```

- [ ] **Step 3: Run graph and CLI tests**

Run:

```bash
python -m pytest tests/test_graph.py tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 4**

Run:

```bash
git add tests/test_graph.py README.md
git commit -m "docs: document llm observability"
```

---

### Task 5: Final Verification

**Files:**
- No code changes expected

- [ ] **Step 1: Run full test suite**

Run:

```bash
python -m pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Run full lint**

Run:

```bash
python -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 3: Run offline CLI smoke**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

Expected: report prints without needing LLM credentials or network access.

- [ ] **Step 4: Inspect final git state**

Run:

```bash
git status --short --branch
```

Expected: clean branch after task commits.

---

## Self-Review Notes

- Spec coverage: the plan covers the state model, metadata fields, Analyst/Reporter/Relevance recording, privacy constraints, deterministic/offline no-log behavior, README documentation, and final verification.
- Placeholder scan: no placeholder markers are present.
- Type consistency: `LLMCallRecord`, `llm_call_log`, `build_llm_call_record()`, and `LLMCallRecord` imports are named consistently across tasks.
