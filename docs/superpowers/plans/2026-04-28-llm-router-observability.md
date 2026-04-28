# LLM Router Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface active LLM rules router decisions in existing LLM call logs without storing prompts or changing the client factory return shape.

**Architecture:** Add an `LLMRouterDecision` model in `llm/router.py` and attach it to clients returned by `get_llm_client()` only when `INSIGHT_GRAPH_LLM_ROUTER=rules`. Extend `LLMCallRecord` and `build_llm_call_record()` with optional router fields, reading metadata from the client. Update CLI LLM log formatting and docs to display router metadata safely.

**Tech Stack:** Python 3.13 local, Python 3.11 CI, Pydantic, Typer CLI, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/llm/router.py`: add `LLMRouterDecision`, decision selection helper, client metadata attachment, and safe decision getter.
- Modify `src/insight_graph/state.py`: add optional router fields to `LLMCallRecord`.
- Modify `src/insight_graph/llm/observability.py`: copy router decision metadata into `LLMCallRecord`.
- Modify `src/insight_graph/agents/analyst.py`: pass `llm_client` into `build_llm_call_record()`.
- Modify `src/insight_graph/agents/reporter.py`: pass `llm_client` into `build_llm_call_record()`.
- Modify `src/insight_graph/cli.py`: add Router/Tier/Reason columns to `--show-llm-log` output.
- Modify `tests/test_llm_router.py`: decision metadata tests.
- Modify `tests/test_state.py`: record/observability tests.
- Modify `tests/test_agents.py`: routed analyst/reporter log tests.
- Modify `tests/test_cli.py`: CLI router columns and JSON field tests.
- Modify `docs/configuration.md`: document router metadata in `llm_call_log`.

## Task 1: Router Decision Metadata

**Files:**
- Modify: `tests/test_llm_router.py`
- Modify: `src/insight_graph/llm/router.py`

- [ ] **Step 1: Write failing router decision tests**

Append these tests to `tests/test_llm_router.py`:

```python
from insight_graph.llm.router import get_llm_router_decision


def test_rules_router_attaches_fast_decision_to_client(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    client = get_llm_client(
        config=base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="short")],
    )

    decision = get_llm_router_decision(client)
    assert decision is not None
    assert decision.router == "rules"
    assert decision.tier == "fast"
    assert decision.reason == "short_default_prompt"
    assert decision.message_chars == len("short")


def test_rules_router_attaches_default_decision_to_client(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD", "3")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "100")

    client = get_llm_client(
        config=base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="medium")],
    )

    decision = get_llm_router_decision(client)
    assert decision is not None
    assert decision.tier == "default"
    assert decision.reason == "default"
    assert decision.message_chars == len("medium")


def test_rules_router_attaches_strong_decision_to_client(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "10")

    client = get_llm_client(
        config=base_config("base-model"),
        purpose="analyst",
        messages=[ChatMessage(role="user", content="x" * 11)],
    )

    decision = get_llm_router_decision(client)
    assert decision is not None
    assert decision.tier == "strong"
    assert decision.reason == "long_prompt"
    assert decision.message_chars == 11


def test_rules_router_attaches_reporter_strong_reason(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    client = get_llm_client(config=base_config("base-model"), purpose="reporter")

    decision = get_llm_router_decision(client)
    assert decision is not None
    assert decision.tier == "strong"
    assert decision.reason == "reporter_strong"
    assert decision.message_chars is None


def test_router_disabled_does_not_attach_decision(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_ROUTER", raising=False)

    client = get_llm_client(config=base_config("base-model"), purpose="reporter")

    assert get_llm_router_decision(client) is None


def test_get_llm_router_decision_ignores_malformed_metadata() -> None:
    class CustomClient:
        router_decision = {"router": "rules", "tier": "fast"}

    assert get_llm_router_decision(CustomClient()) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_router.py -v
```

Expected: FAIL because `LLMRouterDecision` and `get_llm_router_decision()` do not exist.

- [ ] **Step 3: Implement decision model and helper**

In `src/insight_graph/llm/router.py`, add `BaseModel` import:

```python
from pydantic import BaseModel
```

Add this model after constants:

```python
class LLMRouterDecision(BaseModel):
    router: str
    tier: str
    reason: str
    message_chars: int | None = None
```

Add this helper near the bottom:

```python
def get_llm_router_decision(llm_client: object) -> LLMRouterDecision | None:
    decision = getattr(llm_client, "router_decision", None)
    if isinstance(decision, LLMRouterDecision):
        return decision
    return None
```

- [ ] **Step 4: Implement decision selection and client attachment**

In `src/insight_graph/llm/router.py`, change `get_llm_client()` to:

```python
def get_llm_client(
    config: LLMConfig | None = None,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> OpenAICompatibleChatClient:
    resolved = config or resolve_llm_config()
    selected_model, decision = select_llm_model_with_decision(
        resolved,
        purpose=purpose,
        messages=messages,
    )
    if selected_model != resolved.model:
        resolved = resolved.model_copy(update={"model": selected_model})
    client = OpenAICompatibleChatClient(config=resolved)
    if decision is not None:
        client.router_decision = decision
    return client
```

Add a new helper and make `select_llm_model()` delegate to it:

```python
def select_llm_model(
    config: LLMConfig,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> str:
    selected_model, _decision = select_llm_model_with_decision(
        config,
        purpose=purpose,
        messages=messages,
    )
    return selected_model


def select_llm_model_with_decision(
    config: LLMConfig,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> tuple[str, LLMRouterDecision | None]:
    router = os.getenv("INSIGHT_GRAPH_LLM_ROUTER", LLM_ROUTER_DISABLED).strip().lower()
    if router not in SUPPORTED_LLM_ROUTERS:
        raise ValueError(f"Unsupported LLM router: {router}")
    if router != LLM_ROUTER_RULES:
        return config.model, None

    fast_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_FAST", config.model)
    default_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", config.model)
    strong_model = _tier_model("INSIGHT_GRAPH_LLM_MODEL_STRONG", default_model)
    message_chars = _message_char_count(messages)
    fast_threshold = _int_env(
        "INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD",
        DEFAULT_FAST_CHAR_THRESHOLD,
    )
    strong_threshold = _int_env(
        "INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD",
        DEFAULT_STRONG_CHAR_THRESHOLD,
    )

    if purpose == "reporter":
        return strong_model, LLMRouterDecision(
            router=LLM_ROUTER_RULES,
            tier="strong",
            reason="reporter_strong",
            message_chars=message_chars,
        )
    if message_chars is not None and message_chars > strong_threshold:
        return strong_model, LLMRouterDecision(
            router=LLM_ROUTER_RULES,
            tier="strong",
            reason="long_prompt",
            message_chars=message_chars,
        )
    if purpose == "default" and message_chars is not None and message_chars <= fast_threshold:
        return fast_model, LLMRouterDecision(
            router=LLM_ROUTER_RULES,
            tier="fast",
            reason="short_default_prompt",
            message_chars=message_chars,
        )
    return default_model, LLMRouterDecision(
        router=LLM_ROUTER_RULES,
        tier="default",
        reason="default",
        message_chars=message_chars,
    )
```

Remove the old routing body from `select_llm_model()` so threshold parsing happens only once.

- [ ] **Step 5: Run router tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_router.py -v
```

Expected: all router tests pass.

- [ ] **Step 6: Commit router metadata**

```powershell
git add src/insight_graph/llm/router.py tests/test_llm_router.py
git commit -m "feat: attach llm router decisions"
```

## Task 2: LLM Call Record Metadata

**Files:**
- Modify: `tests/test_state.py`
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/llm/observability.py`

- [ ] **Step 1: Write failing observability tests**

Append these tests to `tests/test_state.py`:

```python
from insight_graph.llm.router import LLMRouterDecision


def test_llm_call_record_stores_router_metadata() -> None:
    record = LLMCallRecord(
        stage="analyst",
        provider="llm",
        model="fast-model",
        success=True,
        duration_ms=12,
        router="rules",
        router_tier="fast",
        router_reason="short_default_prompt",
        router_message_chars=123,
    )

    assert record.router == "rules"
    assert record.router_tier == "fast"
    assert record.router_reason == "short_default_prompt"
    assert record.router_message_chars == 123


def test_build_llm_call_record_copies_router_metadata() -> None:
    class RoutedClient:
        router_decision = LLMRouterDecision(
            router="rules",
            tier="strong",
            reason="long_prompt",
            message_chars=12001,
        )

    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="strong-model",
        success=True,
        duration_ms=12,
        llm_client=RoutedClient(),
    )

    assert record.router == "rules"
    assert record.router_tier == "strong"
    assert record.router_reason == "long_prompt"
    assert record.router_message_chars == 12001


def test_build_llm_call_record_omits_router_metadata_without_decision() -> None:
    class PlainClient:
        pass

    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="relay-model",
        success=True,
        duration_ms=12,
        llm_client=PlainClient(),
    )

    assert record.router is None
    assert record.router_tier is None
    assert record.router_reason is None
    assert record.router_message_chars is None


def test_router_metadata_does_not_store_prompt_content() -> None:
    class RoutedClient:
        router_decision = LLMRouterDecision(
            router="rules",
            tier="fast",
            reason="short_default_prompt",
            message_chars=19,
        )

    record = build_llm_call_record(
        stage="analyst",
        provider="llm",
        model="fast-model",
        success=True,
        duration_ms=12,
        llm_client=RoutedClient(),
    )

    serialized = record.model_dump_json()
    assert "Sensitive prompt" not in serialized
    assert record.router_message_chars == 19
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py::test_llm_call_record_stores_router_metadata tests/test_state.py::test_build_llm_call_record_copies_router_metadata tests/test_state.py::test_build_llm_call_record_omits_router_metadata_without_decision tests/test_state.py::test_router_metadata_does_not_store_prompt_content -v
```

Expected: FAIL because `LLMCallRecord` and `build_llm_call_record()` do not support router metadata yet.

- [ ] **Step 3: Extend `LLMCallRecord`**

In `src/insight_graph/state.py`, add optional fields to `LLMCallRecord` after `wire_api`:

```python
    router: str | None = None
    router_tier: str | None = None
    router_reason: str | None = None
    router_message_chars: int | None = None
```

- [ ] **Step 4: Copy router metadata in observability helper**

In `src/insight_graph/llm/observability.py`, import the decision helper:

```python
from insight_graph.llm.router import get_llm_router_decision
```

Add optional parameter to `build_llm_call_record()`:

```python
    llm_client: ChatCompletionClient | None = None,
```

Inside the function before `return LLMCallRecord(...)`, add:

```python
    router_decision = get_llm_router_decision(llm_client) if llm_client is not None else None
```

Add these fields to `LLMCallRecord(...)`:

```python
        router=router_decision.router if router_decision is not None else None,
        router_tier=router_decision.tier if router_decision is not None else None,
        router_reason=router_decision.reason if router_decision is not None else None,
        router_message_chars=router_decision.message_chars if router_decision is not None else None,
```

- [ ] **Step 5: Run observability tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_state.py -v
```

Expected: all state/observability tests pass.

- [ ] **Step 6: Commit observability model changes**

```powershell
git add src/insight_graph/state.py src/insight_graph/llm/observability.py tests/test_state.py
git commit -m "feat: record llm router metadata"
```

## Task 3: Agent LLM Log Integration

**Files:**
- Modify: `tests/test_agents.py`
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `src/insight_graph/agents/reporter.py`

- [ ] **Step 1: Write failing agent log tests**

Append these tests near the existing LLM analyst/reporter log tests in `tests/test_agents.py`:

```python
def test_llm_analyst_log_records_router_metadata(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")

    updated = analyze_evidence(make_analyst_state())

    record = updated.llm_call_log[0]
    assert record.model == "default-model"
    assert record.router == "rules"
    assert record.router_tier == "default"
    assert record.router_reason == "default"
    assert record.router_message_chars is not None


def test_llm_reporter_log_records_router_metadata(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    updated = write_report(make_reporter_state())

    record = updated.llm_call_log[0]
    assert record.model == "strong-model"
    assert record.router == "rules"
    assert record.router_tier == "strong"
    assert record.router_reason == "reporter_strong"
    assert record.router_message_chars is not None
```

If these tests call real OpenAI-compatible clients, monkeypatch `get_llm_client()` to return a `RecordingRouterClient` with a `router_decision` and `config.model`. Keep the test offline.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_llm_analyst_log_records_router_metadata tests/test_agents.py::test_llm_reporter_log_records_router_metadata -v
```

Expected: FAIL because agents do not pass `llm_client` into `build_llm_call_record()` yet, or because tests need fake routed clients.

- [ ] **Step 3: Pass client to analyst log records**

In `src/insight_graph/agents/analyst.py`, add `llm_client=llm_client` to every `build_llm_call_record(...)` call inside `_analyze_evidence_with_llm()`.

Example:

```python
            build_llm_call_record(
                stage="analyst",
                provider="llm",
                model=config.model,
                success=False,
                duration_ms=duration_ms,
                wire_api=wire_api,
                error=exc,
                secrets=[config.api_key],
                llm_client=llm_client,
            )
```

Apply the same pattern to parse-failure and success records while keeping token fields unchanged.

- [ ] **Step 4: Pass selected model to log records**

Because routed clients update `llm_client.config.model`, replace analyst log `model=config.model` with:

```python
model=getattr(getattr(llm_client, "config", None), "model", config.model)
```

Apply the same replacement in all analyst LLM log records.

- [ ] **Step 5: Pass client and selected model to reporter log records**

In `src/insight_graph/agents/reporter.py`, add `llm_client=llm_client` to every `build_llm_call_record(...)` call inside `_write_report_with_llm()`.

Replace reporter log `model=config.model` with:

```python
model=getattr(getattr(llm_client, "config", None), "model", config.model)
```

Apply this to error, validation-failure, and success records while keeping token fields unchanged.

- [ ] **Step 6: Run agent tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py -v
```

Expected: all agent tests pass.

- [ ] **Step 7: Commit agent integration**

```powershell
git add src/insight_graph/agents/analyst.py src/insight_graph/agents/reporter.py tests/test_agents.py
git commit -m "feat: log llm router decisions from agents"
```

## Task 4: CLI Display and JSON Shape

**Files:**
- Modify: `tests/test_cli.py`
- Modify: `src/insight_graph/cli.py`

- [ ] **Step 1: Write failing CLI tests**

Append these tests near existing LLM log CLI tests in `tests/test_cli.py`:

```python
def test_cli_research_show_llm_log_includes_router_columns(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="fast-model",
                success=True,
                duration_ms=12,
                router="rules",
                router_tier="fast",
                router_reason="short_default_prompt",
                router_message_chars=19,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)

    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "| Stage | Provider | Model | Router | Tier | Reason | Wire API |" in result.output
    assert "| analyst | llm | fast-model | rules | fast | short_default_prompt |" in result.output


def test_cli_research_show_llm_log_renders_missing_router_metadata_as_dash(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="reporter",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)

    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "| reporter | llm | relay-model | - | - | - |" in result.output


def test_cli_research_output_json_includes_router_metadata(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="fast-model",
                success=True,
                duration_ms=12,
                router="rules",
                router_tier="fast",
                router_reason="short_default_prompt",
                router_message_chars=19,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)

    result = CliRunner().invoke(
        app, ["research", "Compare AI coding agents", "--output-json"]
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["llm_call_log"][0]["router"] == "rules"
    assert payload["llm_call_log"][0]["router_tier"] == "fast"
    assert payload["llm_call_log"][0]["router_reason"] == "short_default_prompt"
    assert payload["llm_call_log"][0]["router_message_chars"] == 19
```

- [ ] **Step 2: Run CLI tests to verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_cli.py::test_cli_research_show_llm_log_includes_router_columns tests/test_cli.py::test_cli_research_show_llm_log_renders_missing_router_metadata_as_dash tests/test_cli.py::test_cli_research_output_json_includes_router_metadata -v
```

Expected: FAIL because CLI table has no router columns yet.

- [ ] **Step 3: Add router columns to CLI formatter**

In `src/insight_graph/cli.py`, update `_format_llm_call_log()` header lines to include Router/Tier/Reason after Model:

```python
            "| Stage | Provider | Model | Router | Tier | Reason | Wire API | Success | "
            "Duration ms | Input tokens | Output tokens | Total tokens | Error |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
```

Update the row builder after model:

```python
            f"{_markdown_table_cell(record.router or '-')} | "
            f"{_markdown_table_cell(record.router_tier or '-')} | "
            f"{_markdown_table_cell(record.router_reason or '-')} | "
```

Keep `router_message_chars` out of the table for compactness; it remains in JSON output.

- [ ] **Step 4: Update existing CLI expected strings**

Update existing tests in `tests/test_cli.py` that assert old table rows:

```python
"| relevance | openai_compatible | relay-model | - | - | - | responses | true | 7 |  |  |  |  |"
```

```python
"| reporter | llm | relay-model | - | - | - |  | false | 9 |  |  |  | ReporterFallbackError: LLM call failed. |"
```

```python
"| analyst | llm | relay-model | - | - | - |  | true | 12 | 10 | 5 | 15 |  |"
```

Also update the empty-log test to assert the new header contains router columns.

- [ ] **Step 5: Run CLI tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_cli.py -v
```

Expected: all CLI tests pass.

- [ ] **Step 6: Commit CLI display**

```powershell
git add src/insight_graph/cli.py tests/test_cli.py
git commit -m "feat: show llm router metadata in cli"
```

## Task 5: Documentation and Final Verification

**Files:**
- Modify: `docs/configuration.md`

- [ ] **Step 1: Update documentation**

In `docs/configuration.md`, update the LLM Rules Router section with:

```markdown
When routing is enabled, each live LLM call record includes safe router metadata in `llm_call_log`: `router`, `router_tier`, `router_reason`, and `router_message_chars`. The log stores only aggregate prompt character count, not prompt text or completions. `--show-llm-log` displays router, tier, and reason columns; JSON output includes all four fields.
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_llm_router.py tests/test_state.py tests/test_agents.py tests/test_cli.py -v
```

Expected: all focused tests pass.

- [ ] **Step 3: Run full test suite**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
```

Expected: full suite passes with existing skipped test count.

- [ ] **Step 4: Run lint**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
```

Expected: `All checks passed!`.

- [ ] **Step 5: Run whitespace check**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 6: Commit docs**

```powershell
git add docs/configuration.md
git commit -m "docs: document llm router observability"
```

- [ ] **Step 7: Inspect status and commits**

Run:

```powershell
git status --short --branch
git log --oneline --max-count=8
```

Expected: clean feature branch with router observability commits on top of the plan/spec commits.

## Self-Review Checklist

- Spec coverage: client-attached decisions, optional `LLMCallRecord` fields, JSON output, CLI display, prompt-safety, missing metadata behavior, malformed metadata handling, tests, and docs are covered.
- Unfinished marker scan: the plan contains no unresolved implementation sections.
- Type consistency: `LLMRouterDecision`, `get_llm_router_decision()`, `router_tier`, `router_reason`, and `router_message_chars` are named consistently.
- Scope check: this is one focused subsystem and does not add cost estimation, provider pricing, a classifier model, or a separate router log.
