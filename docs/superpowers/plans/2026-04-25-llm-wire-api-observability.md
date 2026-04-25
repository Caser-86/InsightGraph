# LLM Wire API Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safe `wire_api` metadata to LLM call observability so live failures clearly show whether a call used Chat Completions or Responses API.

**Architecture:** Extend `LLMCallRecord` and `build_llm_call_record()` with nullable `wire_api`, then pass it from Analyst, Reporter, and Relevance through a small helper that safely reads `llm_client.config.wire_api`. CLI table and JSON output will expose the field, while README documents `INSIGHT_GRAPH_LLM_WIRE_API` and its opt-in behavior.

**Tech Stack:** Python 3.13, Pydantic, Typer CLI, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/state.py`: add `LLMCallRecord.wire_api`.
- Modify `src/insight_graph/llm/observability.py`: add `wire_api` to `build_llm_call_record()` and add `get_llm_wire_api()` helper.
- Modify `src/insight_graph/agents/analyst.py`: record wire API on analyst LLM calls.
- Modify `src/insight_graph/agents/reporter.py`: record wire API on reporter LLM calls.
- Modify `src/insight_graph/agents/relevance.py`: record wire API on relevance LLM calls.
- Modify `src/insight_graph/cli.py`: add `Wire API` column to `--show-llm-log`.
- Modify `README.md`: document `INSIGHT_GRAPH_LLM_WIRE_API`.
- Modify `tests/test_state.py`: cover model/helper behavior.
- Modify `tests/test_agents.py`: cover analyst/reporter wire API logs.
- Modify `tests/test_relevance.py`: cover relevance wire API logs.
- Modify `tests/test_cli.py`: cover table and JSON output changes.

---

### Task 1: Add Wire API To LLM Call Record And Observability Helper

**Files:**
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/llm/observability.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing state and helper tests**

In `tests/test_state.py`, add `get_llm_wire_api` to the observability import:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
    get_llm_wire_api,
)
```

Add these tests after `test_llm_call_record_stores_nullable_token_fields()`:

```python
def test_llm_call_record_stores_nullable_wire_api() -> None:
    default_record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
    )
    responses_record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        wire_api="responses",
        success=True,
        duration_ms=12,
    )

    assert default_record.wire_api is None
    assert responses_record.wire_api == "responses"
```

Add these tests after `test_build_llm_call_record_normalizes_negative_token_values()`:

```python
def test_build_llm_call_record_stores_wire_api() -> None:
    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="relay-model",
        wire_api="responses",
        success=True,
        duration_ms=12,
    )

    assert record.wire_api == "responses"


def test_get_llm_wire_api_reads_optional_client_config() -> None:
    class ClientConfig:
        wire_api = "responses"

    class ConfiguredClient:
        config = ClientConfig()

    class LegacyClient:
        pass

    assert get_llm_wire_api(ConfiguredClient()) == "responses"
    assert get_llm_wire_api(LegacyClient()) is None
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_state.py::test_llm_call_record_stores_nullable_wire_api tests/test_state.py::test_build_llm_call_record_stores_wire_api tests/test_state.py::test_get_llm_wire_api_reads_optional_client_config -q
```

Expected: FAIL because `LLMCallRecord` does not expose `wire_api`, `build_llm_call_record()` does not accept `wire_api`, and `get_llm_wire_api()` does not exist.

- [ ] **Step 3: Implement state and helper changes**

In `src/insight_graph/state.py`, update `LLMCallRecord` to include `wire_api` after `model`:

```python
class LLMCallRecord(BaseModel):
    stage: str
    provider: str
    model: str
    wire_api: str | None = None
    success: bool
    duration_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    error: str | None = None
```

In `src/insight_graph/llm/observability.py`, update `build_llm_call_record()` signature and return:

```python
def build_llm_call_record(
    *,
    stage: str,
    provider: str,
    model: str,
    success: bool,
    duration_ms: int,
    error: Exception | None = None,
    secrets: list[str | None] | None = None,
    wire_api: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
) -> LLMCallRecord:
    return LLMCallRecord(
        stage=stage,
        provider=provider,
        model=model,
        wire_api=wire_api,
        success=success,
        duration_ms=max(duration_ms, 0),
        input_tokens=_normalize_token_count(input_tokens),
        output_tokens=_normalize_token_count(output_tokens),
        total_tokens=_normalize_token_count(total_tokens),
        error=_summarize_error(error, secrets or []) if error is not None else None,
    )
```

Add this helper below `complete_json_with_observability()`:

```python
def get_llm_wire_api(llm_client: ChatCompletionClient) -> str | None:
    return getattr(getattr(llm_client, "config", None), "wire_api", None)
```

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_state.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add src/insight_graph/state.py src/insight_graph/llm/observability.py tests/test_state.py
git commit -m "feat: record llm wire api metadata"
```

---

### Task 2: Record Wire API From Analyst, Reporter, And Relevance Calls

**Files:**
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `src/insight_graph/agents/relevance.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_relevance.py`

- [ ] **Step 1: Write failing Analyst and Reporter tests**

In `tests/test_agents.py`, add this helper after `UsageLLMClient`:

```python
class FakeClientConfig:
    def __init__(self, wire_api: str) -> None:
        self.wire_api = wire_api
```

Add this test after `test_analyze_evidence_records_successful_llm_call()`:

```python
def test_analyze_evidence_records_llm_wire_api(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = FakeLLMClient(
        content=(
            '{"findings": [{"title": "Pricing differs", '
            '"summary": "Cursor and Copilot differ.", '
            '"evidence_ids": ["cursor-pricing"]}]}'
        )
    )
    client.config = FakeClientConfig(wire_api="responses")

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert updated.llm_call_log[0].wire_api == "responses"
```

Add this test after `test_write_report_records_successful_llm_call()`:

```python
def test_write_report_records_llm_wire_api(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
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
    client.config = FakeClientConfig(wire_api="responses")

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.llm_call_log[0].wire_api == "responses"
```

- [ ] **Step 2: Write failing Relevance test**

In `tests/test_relevance.py`, add this helper after `FakeChatCompletionClient`:

```python
class FakeClientConfig:
    def __init__(self, wire_api: str) -> None:
        self.wire_api = wire_api
```

Add this test after `test_openai_compatible_judge_records_successful_llm_call()`:

```python
def test_openai_compatible_judge_records_llm_wire_api() -> None:
    records: list[LLMCallRecord] = []
    client = FakeChatCompletionClient(
        '{"relevant": true, "reason": "Evidence directly matches."}'
    )
    client.config = FakeClientConfig(wire_api="responses")
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
        model="relay-model",
        llm_call_log=records,
    )

    decision = judge.judge(
        "Compare AI coding agents",
        Subtask(id="collect", description="Collect pricing evidence"),
        make_evidence(id="observed-kept"),
    )

    assert decision.relevant is True
    assert records[0].wire_api == "responses"
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```powershell
python -m pytest tests/test_agents.py::test_analyze_evidence_records_llm_wire_api tests/test_agents.py::test_write_report_records_llm_wire_api tests/test_relevance.py::test_openai_compatible_judge_records_llm_wire_api -q
```

Expected: FAIL because call records are created with `wire_api=None`.

- [ ] **Step 4: Implement Analyst wire API recording**

In `src/insight_graph/agents/analyst.py`, update the observability import to include `get_llm_wire_api`:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
    get_llm_wire_api,
)
```

Inside `_analyze_evidence_with_llm()`, after the optional client creation block and before `messages = _build_analyst_messages(state)`, add:

```python
    wire_api = get_llm_wire_api(llm_client)
```

Pass `wire_api=wire_api` to all three `build_llm_call_record(...)` calls in this function.

- [ ] **Step 5: Implement Reporter wire API recording**

In `src/insight_graph/agents/reporter.py`, update the observability import to include `get_llm_wire_api`:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
    get_llm_wire_api,
)
```

Inside `_write_report_with_llm()`, after the optional client creation block and before `messages = _build_reporter_messages(...)`, add:

```python
    wire_api = get_llm_wire_api(llm_client)
```

Pass `wire_api=wire_api` to all four `build_llm_call_record(...)` calls in this function.

- [ ] **Step 6: Implement Relevance wire API recording**

In `src/insight_graph/agents/relevance.py`, update the observability import to include `get_llm_wire_api`:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
    get_llm_wire_api,
)
```

Inside `OpenAICompatibleRelevanceJudge._record_llm_call()`, pass the wire API into `build_llm_call_record(...)`:

```python
                wire_api=get_llm_wire_api(self._client),
```

Place it after `duration_ms=duration_ms,` and before `error=error,`.

- [ ] **Step 7: Run focused tests and lint**

Run:

```powershell
python -m pytest tests/test_agents.py tests/test_relevance.py -q
python -m ruff check src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py src/insight_graph/agents/relevance.py tests/test_agents.py tests/test_relevance.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 8: Commit Task 2**

Run:

```powershell
git add src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py src/insight_graph/agents/relevance.py tests/test_agents.py tests/test_relevance.py
git commit -m "feat: attach wire api to llm call logs"
```

---

### Task 3: Show Wire API In CLI Logs And JSON Output

**Files:**
- Modify: `src/insight_graph/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI table tests**

In `tests/test_cli.py`, update `test_cli_research_show_llm_log_appends_metadata_table()` records to include one wire API value:

```python
                LLMCallRecord(
                    stage="relevance",
                    provider="openai_compatible",
                    model="relay-model",
                    wire_api="responses",
                    success=True,
                    duration_ms=7,
                ),
```

Update its header assertion to:

```python
    assert (
        "| Stage | Provider | Model | Wire API | Success | Duration ms | "
        "Input tokens | Output tokens | Total tokens | Error |"
    ) in result.output
```

Update its row assertions to:

```python
    assert (
        "| relevance | openai_compatible | relay-model | responses | true | 7 |  |  |  |  |"
        in result.output
    )
    assert (
        "| reporter | llm | relay-model |  | false | 9 |  |  |  | "
        "ReporterFallbackError: LLM call failed. |"
    ) in result.output
```

Update `test_cli_research_show_llm_log_includes_token_columns()` row assertion to:

```python
    assert (
        "| analyst | llm | relay-model |  | true | 12 | 10 | 5 | 15 |  |"
        in result.output
    )
```

Update `test_cli_research_show_llm_log_reports_empty_log()` to assert the new header column:

```python
    assert "| Model | Wire API | Success |" in result.output
```

- [ ] **Step 2: Write failing JSON output test update**

In `test_cli_research_output_json_emits_parseable_summary()`, set the fake LLM call record wire API:

```python
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                wire_api="responses",
                success=True,
                duration_ms=12,
            )
```

Update the expected JSON object for that record to include:

```python
                "wire_api": "responses",
```

Place it after `"model": "relay-model",`.

- [ ] **Step 3: Run CLI tests and verify RED**

Run:

```powershell
python -m pytest tests/test_cli.py::test_cli_research_show_llm_log_appends_metadata_table tests/test_cli.py::test_cli_research_show_llm_log_includes_token_columns tests/test_cli.py::test_cli_research_show_llm_log_reports_empty_log tests/test_cli.py::test_cli_research_output_json_emits_parseable_summary -q
```

Expected: FAIL because `_format_llm_call_log()` does not render the `Wire API` column yet.

- [ ] **Step 4: Implement CLI table change**

In `src/insight_graph/cli.py`, update the header lines in `_format_llm_call_log()` to:

```python
        [
            "| Stage | Provider | Model | Wire API | Success | Duration ms | "
            "Input tokens | Output tokens | Total tokens | Error |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
```

In the row builder, insert `record.wire_api` after model:

```python
            f"{_markdown_table_cell(record.model)} | "
            f"{_markdown_table_cell(record.wire_api or '')} | "
            f"{str(record.success).lower()} | "
```

- [ ] **Step 5: Run CLI tests and lint**

Run:

```powershell
python -m pytest tests/test_cli.py -q
python -m ruff check src/insight_graph/cli.py tests/test_cli.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 3**

Run:

```powershell
git add src/insight_graph/cli.py tests/test_cli.py
git commit -m "feat: show llm wire api in cli logs"
```

---

### Task 4: Document LLM Wire API Configuration

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README LLM config tables**

In `README.md`, add this row to each LLM-related configuration table that currently lists `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL`:

```markdown
| `INSIGHT_GRAPH_LLM_WIRE_API` | OpenAI-compatible wire API，支持 `chat_completions` 或 `responses`；`responses` 需 provider 支持 `/v1/responses` | `chat_completions` |
```

The affected sections are:

- Relevance filtering table near `INSIGHT_GRAPH_RELEVANCE_JUDGE`.
- LLM Analyst configuration table.
- LLM Reporter configuration table.

- [ ] **Step 2: Update Live LLM preset documentation**

After this existing Live LLM preset paragraph:

```markdown
`live-llm` applies missing runtime defaults for DuckDuckGo search, relevance filtering, OpenAI-compatible relevance judging, LLM Analyst, and LLM Reporter. It does not permanently modify your environment and does not accept API keys as command-line arguments.
```

Add:

```markdown
`live-llm` does not set `INSIGHT_GRAPH_LLM_WIRE_API`; by default LLM calls use Chat Completions. To test a provider's Responses API support, explicitly set `INSIGHT_GRAPH_LLM_WIRE_API=responses`. If the provider does not support `/v1/responses` or the JSON response format, InsightGraph records the sanitized failure in `llm_call_log` and does not automatically fall back to Chat Completions.
```

- [ ] **Step 3: Update LLM Observability documentation**

Replace this sentence in the LLM Observability section:

```markdown
Live LLM paths populate `GraphState.llm_call_log` with metadata for attempted LLM calls. Each record includes the stage (`relevance`, `analyst`, or `reporter`), provider, model, success flag, duration in milliseconds, and a short sanitized error summary when a call fails. When the provider returns usage data, records also include nullable `input_tokens`, `output_tokens`, and `total_tokens` fields. InsightGraph does not estimate cost in this version.
```

with:

```markdown
Live LLM paths populate `GraphState.llm_call_log` with metadata for attempted LLM calls. Each record includes the stage (`relevance`, `analyst`, or `reporter`), provider, model, configured wire API when available, success flag, duration in milliseconds, and a short sanitized error summary when a call fails. When the provider returns usage data, records also include nullable `input_tokens`, `output_tokens`, and `total_tokens` fields. InsightGraph does not estimate cost in this version.
```

Replace this sentence:

```markdown
The appended table is opt-in and contains only stage, provider, model, success, duration, token counts when available, and sanitized error metadata.
```

with:

```markdown
The appended table is opt-in and contains only stage, provider, model, wire API when available, success, duration, token counts when available, and sanitized error metadata.
```

- [ ] **Step 4: Run docs-related verification**

Run:

```powershell
python -m pytest tests/test_cli.py::test_cli_research_output_json_emits_parseable_summary -q
python -m ruff check .
```

Expected: test passes and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 4**

Run:

```powershell
git add README.md
git commit -m "docs: document llm wire api observability"
```

---

### Task 5: Final Verification And Live Smoke

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run focused verification**

Run:

```powershell
python -m pytest tests/test_state.py tests/test_agents.py tests/test_relevance.py tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full verification**

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

Expected: command succeeds and installs `insightgraph==0.1.0` from the current checkout.

- [ ] **Step 4: Run default live smoke**

Run:

```powershell
$names = @("INSIGHT_GRAPH_LLM_API_KEY", "INSIGHT_GRAPH_LLM_BASE_URL", "INSIGHT_GRAPH_LLM_MODEL"); foreach ($name in $names) { $value = [Environment]::GetEnvironmentVariable($name, "User"); if (-not [string]::IsNullOrWhiteSpace($value)) { [Environment]::SetEnvironmentVariable($name, $value, "Process"); Set-Item -Path "env:$name" -Value $value } }; Remove-Item Env:\INSIGHT_GRAPH_LLM_WIRE_API -ErrorAction SilentlyContinue; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected: JSON is parseable; `llm_call_log` records include `wire_api` with `chat_completions` when OpenAI-compatible clients are used.

- [ ] **Step 5: Run Responses live smoke**

Run:

```powershell
$names = @("INSIGHT_GRAPH_LLM_API_KEY", "INSIGHT_GRAPH_LLM_BASE_URL", "INSIGHT_GRAPH_LLM_MODEL"); foreach ($name in $names) { $value = [Environment]::GetEnvironmentVariable($name, "User"); if (-not [string]::IsNullOrWhiteSpace($value)) { [Environment]::SetEnvironmentVariable($name, $value, "Process"); Set-Item -Path "env:$name" -Value $value } }; $env:INSIGHT_GRAPH_LLM_WIRE_API = "responses"; python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected: JSON is parseable; `llm_call_log` records include `wire_api` with `responses` when OpenAI-compatible clients are used. If the provider fails on `/v1/responses`, the failure remains sanitized and visible in `llm_call_log`.

- [ ] **Step 6: Inspect git status**

Run:

```powershell
git status --short --branch
```

Expected: clean working tree on the implementation branch.
