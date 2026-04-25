# LLM Token Usage Observability Design

## Goal

Extend LLM observability so `GraphState.llm_call_log` records token usage metadata when an OpenAI-compatible provider returns usage data, without estimating cost or changing default deterministic behavior.

## Non-Goals

- Do not estimate `cost_usd` in this iteration.
- Do not maintain model pricing tables.
- Do not require token usage for providers that omit it.
- Do not count tokens locally from prompts or responses.
- Do not record prompts, completions, raw responses, API keys, authorization headers, request bodies, or raw exception payloads.
- Do not change live-LLM preset defaults.

## User Experience

LLM call records gain nullable token fields:

```json
{
  "stage": "analyst",
  "provider": "llm",
  "model": "gpt-4o-mini",
  "success": true,
  "duration_ms": 812,
  "error": null,
  "input_tokens": 1234,
  "output_tokens": 321,
  "total_tokens": 1555
}
```

When a provider omits usage data, these fields are `null`.

`--show-llm-log` should include token columns after duration:

```markdown
| Stage | Provider | Model | Success | Duration ms | Input tokens | Output tokens | Total tokens | Error |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
```

`--output-json` automatically exposes the new fields because it serializes `llm_call_log` records.

## Architecture

Add token fields to `LLMCallRecord` in `src/insight_graph/state.py`:

- `input_tokens: int | None = None`
- `output_tokens: int | None = None`
- `total_tokens: int | None = None`

Add matching optional parameters to `build_llm_call_record()` in `src/insight_graph/llm/observability.py`. Clamp negative values to `None` or ignore them so invalid provider data does not create misleading counts.

Add a lightweight result model in `src/insight_graph/llm/client.py`:

```python
class ChatCompletionResult(BaseModel):
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
```

Extend the `ChatCompletionClient` protocol with a usage-aware method:

```python
def complete_json_with_usage(self, messages: list[ChatMessage]) -> ChatCompletionResult: ...
```

Keep the existing `complete_json(messages) -> str` method for compatibility. `OpenAICompatibleChatClient.complete_json()` should call `complete_json_with_usage()` and return only `.content`.

`OpenAICompatibleChatClient.complete_json_with_usage()` should call the same Chat Completions endpoint as today, extract `response.usage.prompt_tokens`, `response.usage.completion_tokens`, and `response.usage.total_tokens` when present, and return `ChatCompletionResult`.

## Caller Compatibility

Existing tests and fake clients often implement only `complete_json()`. To avoid a large test rewrite and to keep third-party clients easy to provide, agent code should use a small compatibility helper, for example in `src/insight_graph/llm/observability.py`:

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

Analyst, Reporter, and Relevance should call this helper instead of directly calling `complete_json()`. This allows production OpenAI-compatible clients to record usage while old fake clients continue to work with token fields set to `None`.

## Data Flow

For live OpenAI-compatible calls:

1. Agent builds messages as before.
2. Agent calls `complete_json_with_observability()`.
3. Production client returns `ChatCompletionResult(content=..., input_tokens=..., output_tokens=..., total_tokens=...)` when usage exists.
4. Agent parses content as before.
5. Agent appends an `LLMCallRecord` containing success/failure metadata plus token fields when available.

For parse failures after a successful provider response, token fields should still be recorded because the attempted LLM call completed and returned usage.

For transport/API failures before a response exists, token fields remain `None`.

For missing API key paths where no LLM call is attempted, no LLM call record is appended, preserving current behavior.

## Safety Rules

Token usage metadata is safe to expose because it contains only counts. The implementation must not derive token usage by reading or serializing prompt/response content. It should only copy provider-supplied usage numbers from the response object.

The existing sanitized error behavior remains unchanged. Error strings should continue to be generic summaries like `RuntimeError: LLM call failed.`.

## Testing

Add tests that use fake clients/responses only. Do not access the network.

Coverage:

- `LLMCallRecord` stores nullable token fields.
- `build_llm_call_record()` accepts token fields and ignores negative values.
- `OpenAICompatibleChatClient.complete_json_with_usage()` returns content and token counts when fake response has `usage`.
- `OpenAICompatibleChatClient.complete_json_with_usage()` returns content and `None` token fields when fake response has no `usage`.
- Existing `complete_json()` still returns only the content string.
- Analyst, Reporter, and Relevance successful calls record tokens when the fake client implements `complete_json_with_usage()`.
- Existing fake clients that only implement `complete_json()` still work and record token fields as `None`.
- Parse failures after a successful LLM response preserve token fields in failed `LLMCallRecord` entries.
- `--show-llm-log` includes token columns.
- `--output-json` includes token fields through `llm_call_log` serialization and does not expose prompt/response/API keys.

Run at minimum:

```bash
python -m pytest tests/test_state.py tests/test_llm_client.py tests/test_agents.py tests/test_relevance.py tests/test_cli.py -q
python -m ruff check src/insight_graph tests
```

Final verification:

```bash
python -m pytest -v
python -m ruff check .
```

## Rollout

This is a backward-compatible observability enhancement. Existing deterministic/offline runs continue to produce empty `llm_call_log`; existing LLM calls without provider usage continue to produce records with token fields set to `null`.
