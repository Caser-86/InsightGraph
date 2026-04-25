# LLM Token Usage Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record provider-supplied token usage in `GraphState.llm_call_log` without estimating cost or exposing prompt/response data.

**Architecture:** Add nullable token fields to `LLMCallRecord`, add a usage-aware LLM result type while keeping `complete_json()` backward compatible, and route Analyst/Reporter/Relevance through a compatibility helper that falls back to old fake clients. CLI Markdown and JSON output expose the new metadata through existing observability surfaces.

**Tech Stack:** Python 3.13, Pydantic, Typer, pytest, ruff, OpenAI-compatible Chat Completions.

---

## File Structure

- Modify `src/insight_graph/state.py`: add nullable token fields to `LLMCallRecord`.
- Modify `src/insight_graph/llm/client.py`: add `ChatCompletionResult`, `complete_json_with_usage()`, and provider usage extraction.
- Modify `src/insight_graph/llm/__init__.py`: export `ChatCompletionResult`.
- Modify `src/insight_graph/llm/observability.py`: accept token fields, normalize invalid counts, and add a compatibility completion helper.
- Modify `src/insight_graph/agents/analyst.py`, `src/insight_graph/agents/reporter.py`, `src/insight_graph/agents/relevance.py`: propagate token usage into LLM call records.
- Modify `src/insight_graph/cli.py`: add token columns to `--show-llm-log` output.
- Modify `tests/test_state.py`, `tests/test_llm_client.py`, `tests/test_agents.py`, `tests/test_relevance.py`, `tests/test_cli.py`: add token usage coverage.
- Modify `README.md`: document nullable token usage metadata.

---

### Task 1: Add Usage-Aware LLM Client Result

**Files:**
- Modify: `src/insight_graph/llm/client.py`
- Modify: `src/insight_graph/llm/__init__.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing LLM client tests**

In `tests/test_llm_client.py`, import `ChatCompletionResult` from `insight_graph.llm` and update the fake OpenAI response classes so `FakeOpenAIResponse` can expose an optional `usage` object:

```python
class FakeOpenAIUsage:
    def __init__(
        self,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens


class FakeOpenAIResponse:
    def __init__(
        self,
        content: str | None,
        usage: FakeOpenAIUsage | None = None,
    ) -> None:
        self.choices = [FakeOpenAIChoice(FakeOpenAIMessage(content))]
        self.usage = usage
```

Update `FakeOpenAICompletions.__init__()` to accept `usage: FakeOpenAIUsage | None = None`, save it as `self.usage`, and return `FakeOpenAIResponse(self.content, usage=self.usage)` from `create()`.

Add these tests:

```python
def test_openai_compatible_chat_client_completes_json_with_usage() -> None:
    completions = FakeOpenAICompletions(
        content='{"answer": "yes"}',
        usage=FakeOpenAIUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
    )
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=FakeOpenAIClient(completions),
    )

    result = client.complete_json_with_usage(
        [ChatMessage(role="user", content="Reply as JSON")]
    )

    assert result == ChatCompletionResult(
        content='{"answer": "yes"}',
        input_tokens=11,
        output_tokens=7,
        total_tokens=18,
    )


def test_openai_compatible_chat_client_handles_missing_usage() -> None:
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=FakeOpenAIClient(FakeOpenAICompletions(content='{"answer": "yes"}')),
    )

    result = client.complete_json_with_usage(
        [ChatMessage(role="user", content="Reply as JSON")]
    )

    assert result == ChatCompletionResult(content='{"answer": "yes"}')


def test_openai_compatible_chat_client_complete_json_still_returns_content() -> None:
    client = OpenAICompatibleChatClient(
        config=LLMConfig(api_key="test-key", base_url=None, model="test-model"),
        client=FakeOpenAIClient(
            FakeOpenAICompletions(
                content='{"answer": "yes"}',
                usage=FakeOpenAIUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
            )
        ),
    )

    assert client.complete_json([ChatMessage(role="user", content="Reply as JSON")]) == (
        '{"answer": "yes"}'
    )
```

Also update `test_llm_package_exports_core_types()`:

```python
assert ChatCompletionResult(content="{}").content == "{}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_llm_client.py::test_openai_compatible_chat_client_completes_json_with_usage tests/test_llm_client.py::test_openai_compatible_chat_client_handles_missing_usage tests/test_llm_client.py::test_openai_compatible_chat_client_complete_json_still_returns_content tests/test_llm_client.py::test_llm_package_exports_core_types -q
```

Expected: FAIL because `ChatCompletionResult` and `complete_json_with_usage()` do not exist yet.

- [ ] **Step 3: Implement usage-aware result and export**

In `src/insight_graph/llm/client.py`, add after `ChatMessage`:

```python
class ChatCompletionResult(BaseModel):
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
```

Update `ChatCompletionClient`:

```python
class ChatCompletionClient(Protocol):
    def complete_json(self, messages: list[ChatMessage]) -> str: ...

    def complete_json_with_usage(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult: ...
```

Replace `OpenAICompatibleChatClient.complete_json()` with:

```python
    def complete_json(self, messages: list[ChatMessage]) -> str:
        return self.complete_json_with_usage(messages).content

    def complete_json_with_usage(
        self,
        messages: list[ChatMessage],
    ) -> ChatCompletionResult:
        if not self.config.api_key:
            raise ValueError("LLM api_key is required")

        response = self._get_client().chat.completions.create(
            model=self.config.model,
            messages=[message.model_dump() for message in messages],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        if content is None:
            raise ValueError("LLM response content is required")
        usage = getattr(response, "usage", None)
        return ChatCompletionResult(
            content=content,
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
            total_tokens=getattr(usage, "total_tokens", None),
        )
```

Export `ChatCompletionResult` from `src/insight_graph/llm/__init__.py` by importing it and adding it to `__all__`.

- [ ] **Step 4: Run client tests and lint**

Run:

```bash
python -m pytest tests/test_llm_client.py -q
python -m ruff check src/insight_graph/llm/client.py src/insight_graph/llm/__init__.py tests/test_llm_client.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add src/insight_graph/llm/client.py src/insight_graph/llm/__init__.py tests/test_llm_client.py
git commit -m "feat: return llm token usage"
```

---

### Task 2: Add Token Fields And Completion Compatibility Helper

**Files:**
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/llm/observability.py`
- Modify: `tests/test_state.py`

- [ ] **Step 1: Write failing state/helper tests**

In `tests/test_state.py`, import `ChatCompletionResult` and `ChatMessage`:

```python
from insight_graph.llm import ChatCompletionResult, ChatMessage
```

Update the observability import:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
)
```

Add these tests:

```python
def test_llm_call_record_stores_nullable_token_fields() -> None:
    record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )

    assert record.input_tokens == 10
    assert record.output_tokens == 5
    assert record.total_tokens == 15


def test_build_llm_call_record_normalizes_negative_token_values() -> None:
    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
        input_tokens=-1,
        output_tokens=2,
        total_tokens=-3,
    )

    assert record.input_tokens is None
    assert record.output_tokens == 2
    assert record.total_tokens is None


def test_complete_json_with_observability_uses_usage_aware_client() -> None:
    class UsageAwareClient:
        def complete_json_with_usage(self, messages: list[ChatMessage]) -> ChatCompletionResult:
            return ChatCompletionResult(
                content='{"ok": true}',
                input_tokens=3,
                output_tokens=4,
                total_tokens=7,
            )

        def complete_json(self, messages: list[ChatMessage]) -> str:
            raise AssertionError("complete_json should not be called")

    result = complete_json_with_observability(
        UsageAwareClient(), [ChatMessage(role="user", content="Return JSON")]
    )

    assert result == ChatCompletionResult(
        content='{"ok": true}',
        input_tokens=3,
        output_tokens=4,
        total_tokens=7,
    )


def test_complete_json_with_observability_falls_back_to_legacy_client() -> None:
    class LegacyClient:
        def complete_json(self, messages: list[ChatMessage]) -> str:
            return '{"ok": true}'

    result = complete_json_with_observability(
        LegacyClient(), [ChatMessage(role="user", content="Return JSON")]
    )

    assert result == ChatCompletionResult(content='{"ok": true}')
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_state.py::test_llm_call_record_stores_nullable_token_fields tests/test_state.py::test_build_llm_call_record_normalizes_negative_token_values tests/test_state.py::test_complete_json_with_observability_uses_usage_aware_client tests/test_state.py::test_complete_json_with_observability_falls_back_to_legacy_client -q
```

Expected: FAIL because token fields and compatibility helper do not exist yet.

- [ ] **Step 3: Implement token fields and helper**

In `src/insight_graph/state.py`, add to `LLMCallRecord` after `duration_ms`:

```python
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
```

In `src/insight_graph/llm/observability.py`, update imports:

```python
from insight_graph.llm.client import ChatCompletionClient, ChatCompletionResult, ChatMessage
from insight_graph.state import LLMCallRecord
```

Update `build_llm_call_record()` signature with optional token fields and pass them to `LLMCallRecord`:

```python
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    total_tokens: int | None = None,
```

Use this helper for values:

```python
def _normalize_token_count(value: int | None) -> int | None:
    if value is None or value < 0:
        return None
    return value
```

Add this completion helper:

```python
def complete_json_with_observability(
    llm_client: ChatCompletionClient,
    messages: list[ChatMessage],
) -> ChatCompletionResult:
    complete_with_usage = getattr(llm_client, "complete_json_with_usage", None)
    if complete_with_usage is not None:
        return complete_with_usage(messages)
    return ChatCompletionResult(content=llm_client.complete_json(messages))
```

- [ ] **Step 4: Run state/helper tests and lint**

Run:

```bash
python -m pytest tests/test_state.py -q
python -m ruff check src/insight_graph/state.py src/insight_graph/llm/observability.py tests/test_state.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add src/insight_graph/state.py src/insight_graph/llm/observability.py tests/test_state.py
git commit -m "feat: add llm token usage fields"
```

---

### Task 3: Propagate Token Usage Through Agents

**Files:**
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `src/insight_graph/agents/relevance.py`
- Modify: `tests/test_agents.py`
- Modify: `tests/test_relevance.py`

- [ ] **Step 1: Write failing agent/relevance tests**

In `tests/test_agents.py`, import `ChatCompletionResult`:

```python
from insight_graph.llm import ChatCompletionResult, ChatMessage
```

Add this fake client class after `FakeLLMClient`:

```python
class UsageLLMClient(FakeLLMClient):
    def __init__(
        self,
        content: str | None = None,
        result: ChatCompletionResult | None = None,
        error: Exception | None = None,
        messages: list[list[ChatMessage]] | None = None,
    ) -> None:
        super().__init__(content=content, error=error, messages=messages)
        self.result = result

    def complete_json_with_usage(self, messages: list[ChatMessage]) -> ChatCompletionResult:
        self.messages.append(messages)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return ChatCompletionResult(content=self.content)
```

Add tests near existing LLM observability tests:

```python
def test_analyze_evidence_records_llm_token_usage(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = UsageLLMClient(
        result=ChatCompletionResult(
            content=(
                '{"findings": [{"title": "Pricing differs", '
                '"summary": "Cursor and Copilot differ.", '
                '"evidence_ids": ["cursor-pricing"]}]}'
            ),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
    )

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert updated.llm_call_log[0].input_tokens == 10
    assert updated.llm_call_log[0].output_tokens == 5
    assert updated.llm_call_log[0].total_tokens == 15


def test_analyze_evidence_records_tokens_for_parse_failure(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = UsageLLMClient(
        result=ChatCompletionResult(
            content="not json",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
    )

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert updated.llm_call_log[0].success is False
    assert updated.llm_call_log[0].input_tokens == 10
    assert updated.llm_call_log[0].output_tokens == 5
    assert updated.llm_call_log[0].total_tokens == 15


def test_write_report_records_llm_token_usage(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    client = UsageLLMClient(
        result=ChatCompletionResult(
            content=(
                '{"markdown": "# InsightGraph Research Report\\n\\n'
                '## Key Findings\\n\\n'
                '### Pricing and packaging differ\\n\\n'
                'The verified sources support this comparison [1]."}'
            ),
            input_tokens=20,
            output_tokens=8,
            total_tokens=28,
        )
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.llm_call_log[0].input_tokens == 20
    assert updated.llm_call_log[0].output_tokens == 8
    assert updated.llm_call_log[0].total_tokens == 28
```

In `tests/test_relevance.py`, import `ChatCompletionResult`:

```python
from insight_graph.llm import ChatCompletionResult
```

Add `complete_json_with_usage()` to `FakeChatCompletionClient`:

```python
    def complete_json_with_usage(self, messages):
        self.messages = messages
        if self.error is not None:
            raise self.error
        return ChatCompletionResult(
            content=self.content,
            input_tokens=6,
            output_tokens=4,
            total_tokens=10,
        )
```

Add this test near existing relevance observability tests:

```python
def test_openai_compatible_judge_records_llm_token_usage() -> None:
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

    decision = judge.judge(
        "Compare AI coding agents",
        Subtask(id="collect", description="Collect pricing evidence"),
        make_evidence(id="observed-kept"),
    )

    assert decision.relevant is True
    assert records[0].input_tokens == 6
    assert records[0].output_tokens == 4
    assert records[0].total_tokens == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_agents.py::test_analyze_evidence_records_llm_token_usage tests/test_agents.py::test_analyze_evidence_records_tokens_for_parse_failure tests/test_agents.py::test_write_report_records_llm_token_usage tests/test_relevance.py::test_openai_compatible_judge_records_llm_token_usage -q
```

Expected: FAIL because agents still call `complete_json()` and do not pass token fields into `build_llm_call_record()`.

- [ ] **Step 3: Implement propagation**

In `src/insight_graph/agents/analyst.py`, replace the observability import with:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
)
```

Replace the LLM call inside `_analyze_evidence_with_llm()` with:

```python
        result = complete_json_with_observability(llm_client, messages)
```

Replace parse input:

```python
        state.findings = _parse_analyst_findings(result.content, state.evidence_pool)
```

In both the parse-failure and success `build_llm_call_record()` calls, add:

```python
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
```

Do not add token fields to the transport/API exception record because `result` does not exist in that branch.

In `src/insight_graph/agents/reporter.py`, replace the observability import with:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
)
```

Replace the LLM call inside `_write_report_with_llm()` with:

```python
        result = complete_json_with_observability(llm_client, messages)
```

Replace parse input:

```python
        body = _parse_llm_report_body(result.content)
```

In both the parse/validation-failure and success `build_llm_call_record()` calls, add:

```python
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                total_tokens=result.total_tokens,
```

Do not add token fields to transport/API exception records because `result` does not exist in those branches.

In `src/insight_graph/agents/relevance.py`, replace the observability import with:

```python
from insight_graph.llm.observability import (
    build_llm_call_record,
    complete_json_with_observability,
)
```

Add `ChatCompletionResult` to the client import list:

```python
from insight_graph.llm.client import (
    ChatCompletionClient,
    ChatCompletionResult,
    ChatMessage,
    OpenAICompatibleChatClient,
)
```

Replace the LLM call in `OpenAICompatibleRelevanceJudge.judge()` with:

```python
            result = complete_json_with_observability(
                self._client,
                _build_relevance_messages(query, subtask, evidence),
            )
```

Replace parse input and success recording with:

```python
            decision = _parse_relevance_json(result.content, evidence.id)
```

```python
        self._record_llm_call(True, started, result=result)
```

Update the parse-failure recording call:

```python
            self._record_llm_call(False, started, exc, result=result)
```

Update `_record_llm_call()` signature:

```python
    def _record_llm_call(
        self,
        success: bool,
        started: float,
        error: Exception | None = None,
        result: ChatCompletionResult | None = None,
    ) -> None:
```

Pass token fields to `build_llm_call_record()`:

```python
                input_tokens=result.input_tokens if result is not None else None,
                output_tokens=result.output_tokens if result is not None else None,
                total_tokens=result.total_tokens if result is not None else None,
```

Keep transport/API failure records token fields as `None` because no result exists.

- [ ] **Step 4: Run focused and related tests**

Run:

```bash
python -m pytest tests/test_agents.py tests/test_relevance.py -q
python -m ruff check src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py src/insight_graph/agents/relevance.py tests/test_agents.py tests/test_relevance.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py src/insight_graph/agents/relevance.py tests/test_agents.py tests/test_relevance.py
git commit -m "feat: record llm token usage"
```

---

### Task 4: Display Token Usage In CLI And Docs

**Files:**
- Modify: `src/insight_graph/cli.py`
- Modify: `tests/test_cli.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing CLI tests**

Update `test_cli_research_show_llm_log_appends_metadata_table()` expectations so the table header includes token columns:

```python
assert (
    "| Stage | Provider | Model | Success | Duration ms | "
    "Input tokens | Output tokens | Total tokens | Error |"
) in result.output
```

Add this test near the existing CLI LLM log tests:

```python
def test_cli_research_show_llm_log_includes_token_columns(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "| analyst | llm | relay-model | true | 12 | 10 | 5 | 15 |  |" in result.output
```

Add to `test_cli_research_output_json_emits_parseable_summary()` expected `llm_call_log` entry:

```python
"input_tokens": None,
"output_tokens": None,
"total_tokens": None,
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_cli.py::test_cli_research_show_llm_log_appends_metadata_table tests/test_cli.py::test_cli_research_show_llm_log_includes_token_columns tests/test_cli.py::test_cli_research_output_json_emits_parseable_summary -q
```

Expected: FAIL because CLI table does not include token columns yet and JSON expected fields changed.

- [ ] **Step 3: Update CLI table formatting**

In `src/insight_graph/cli.py`, change the table header to:

```python
"| Stage | Provider | Model | Success | Duration ms | Input tokens | Output tokens | Total tokens | Error |",
"| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
```

Add token fields to each row between duration and error:

```python
f"{_format_optional_int(record.input_tokens)} | "
f"{_format_optional_int(record.output_tokens)} | "
f"{_format_optional_int(record.total_tokens)} | "
```

Add helper:

```python
def _format_optional_int(value: int | None) -> str:
    return "" if value is None else str(value)
```

- [ ] **Step 4: Update README**

In `README.md`, in the LLM Observability section, update the metadata description to mention token counts when available:

```markdown
When the provider returns usage data, records also include nullable `input_tokens`, `output_tokens`, and `total_tokens` fields. InsightGraph does not estimate cost in this version.
```

- [ ] **Step 5: Run CLI tests and lint**

Run:

```bash
python -m pytest tests/test_cli.py -q
python -m ruff check src/insight_graph/cli.py tests/test_cli.py
```

Expected: tests pass and ruff reports `All checks passed!`.

- [ ] **Step 6: Commit Task 4**

Run:

```bash
git add src/insight_graph/cli.py tests/test_cli.py README.md
git commit -m "feat: show llm token usage in cli"
```

---

### Task 5: Final Verification

**Files:**
- Verify: entire repository

- [ ] **Step 1: Run full tests and lint**

Run:

```bash
python -m pytest -v
python -m ruff check .
```

Expected: all tests pass and ruff reports `All checks passed!`.

- [ ] **Step 2: Run offline CLI smoke with LLM log**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --show-llm-log
```

Expected: Markdown report includes `## LLM Call Log` and the token column headers. Because the default run is deterministic/offline, it should also include `No LLM calls were recorded.`.

- [ ] **Step 3: Run offline CLI JSON smoke**

Run:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

Expected: parseable JSON prints successfully and `llm_call_log` is an empty list for the default deterministic/offline run.

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected: clean working tree on the implementation branch.
