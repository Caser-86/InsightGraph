# LLM Router And Analyst Integration Design

## Goal

Add a reusable OpenAI-compatible LLM layer and use it first in the Analyst node, while keeping the current deterministic/offline research flow as the default.

The first opt-in LLM consumer is Analyst because it has the clearest boundary: it receives the user request and verified evidence, then produces `Finding` objects with citations. Planner, Reporter, and other agents stay deterministic in this phase.

## Scope

In scope:

- Add `src/insight_graph/llm/` as the shared LLM package.
- Support OpenAI official and OpenAI-compatible relay providers through `/v1/chat/completions`.
- Reuse the same `INSIGHT_GRAPH_LLM_*` and `OPENAI_*` environment variables already introduced for relevance judging.
- Refactor the OpenAI-compatible relevance judge to reuse shared LLM config/client helpers instead of maintaining duplicate client setup logic.
- Add an opt-in LLM Analyst path controlled by `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`.
- Parse LLM Analyst output into existing `Finding` models.
- Validate that every LLM-produced evidence ID exists and refers to verified evidence.
- Fall back to deterministic Analyst behavior on missing key, API error, empty output, invalid JSON, invalid schema, empty findings, or invalid citations.
- Keep all tests offline by using fake clients only.

Out of scope:

- Native Anthropic, Gemini, DashScope, or provider-specific SDKs.
- Streaming responses.
- Token accounting or cost budgets.
- Planner, Reporter, Critic, or Executor LLM integration.
- Persistence of prompts or responses.
- Prompt/response tracing UI or observability dashboards.

## Default Behavior

Default CLI behavior must not change.

- Without `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`, `analyze_evidence()` uses the current deterministic implementation.
- Default tests must not require API keys or network access.
- `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL` are inert unless an LLM-backed component is explicitly enabled.
- Relevance filtering remains independently opt-in through `INSIGHT_GRAPH_RELEVANCE_FILTER` and `INSIGHT_GRAPH_RELEVANCE_JUDGE`.

## Configuration

The shared LLM config resolves values in this order:

| Field | Resolution | Default |
|-------|------------|---------|
| `api_key` | explicit argument, then `INSIGHT_GRAPH_LLM_API_KEY`, then `OPENAI_API_KEY` | `None` |
| `base_url` | explicit argument, then `INSIGHT_GRAPH_LLM_BASE_URL`, then `OPENAI_BASE_URL` | `None` |
| `model` | explicit argument, then `INSIGHT_GRAPH_LLM_MODEL` | `gpt-4o-mini` |

Analyst provider selection:

| Variable | Meaning | Default |
|----------|---------|---------|
| `INSIGHT_GRAPH_ANALYST_PROVIDER` | `deterministic` or `llm` | `deterministic` |

Unknown Analyst provider values should raise `ValueError` when explicitly resolved by a helper, but the graph default path should continue to use deterministic behavior unless the user opts into `llm`.

## Architecture

### `src/insight_graph/llm/config.py`

Responsibilities:

- Define `LLMConfig` with `api_key: str | None`, `base_url: str | None`, and `model: str`.
- Define `resolve_llm_config(api_key=None, base_url=None, model=None) -> LLMConfig`.
- Contain only environment/config logic. It must not import the OpenAI SDK.

### `src/insight_graph/llm/client.py`

Responsibilities:

- Define `ChatMessage` as a lightweight Pydantic model or typed structure with `role` and `content`.
- Define `ChatCompletionClient` protocol with a `complete_json(messages: list[ChatMessage]) -> str` method.
- Implement `OpenAICompatibleChatClient`.
- Lazily import `OpenAI` inside the concrete client or factory so importing the package does not require network access or eager SDK initialization.
- Call `client.chat.completions.create(...)` with:
  - configured model
  - serialized messages
  - `response_format={"type": "json_object"}`
  - `temperature=0`
- Return the raw message content string.
- Raise exceptions to the caller; caller-specific fallback policy belongs in the agent layer.

### `src/insight_graph/llm/router.py`

Responsibilities:

- Define `get_llm_client(config: LLMConfig | None = None) -> ChatCompletionClient`.
- Return an `OpenAICompatibleChatClient` for this phase.
- Remain intentionally small. Provider routing beyond OpenAI-compatible is deferred.

### `src/insight_graph/agents/relevance.py`

Responsibilities after refactor:

- Keep `DeterministicRelevanceJudge` unchanged.
- Keep `OpenAICompatibleRelevanceJudge` behavior unchanged.
- Replace duplicate config/client creation with shared `llm.config` and `llm.client` helpers.
- Preserve public behavior and tests from the previous relevance implementation.

### `src/insight_graph/agents/analyst.py`

Responsibilities:

- Preserve current deterministic logic in a separate helper, such as `_analyze_evidence_deterministic(state)`.
- Add `get_analyst_provider(name: str | None = None) -> str` or equivalent helper that reads `INSIGHT_GRAPH_ANALYST_PROVIDER`.
- `analyze_evidence(state)` should:
  - use deterministic behavior by default;
  - use LLM behavior only when provider is `llm`;
  - fall back to deterministic behavior on any LLM failure or invalid output.
- Add injectable client support for tests through a helper or optional internal function parameter rather than exposing test-only behavior through the graph API.

## LLM Analyst Prompt And Output

The LLM Analyst prompt should contain:

- The original user request.
- Each verified evidence item with ID, title, source URL, source type, and snippet.
- A strict instruction to return only JSON.
- A strict instruction that every `evidence_ids` entry must come from the provided evidence IDs.

Expected JSON shape:

```json
{
  "findings": [
    {
      "title": "Concise finding title",
      "summary": "Evidence-grounded explanation.",
      "evidence_ids": ["evidence-id-1"]
    }
  ]
}
```

Validation rules:

- Top-level value must be an object.
- `findings` must be a non-empty list.
- Each finding must have non-empty string `title` and `summary`.
- Each finding must have a non-empty list of string `evidence_ids`.
- Every referenced ID must exist in the current evidence pool.
- Every referenced ID must belong to verified evidence.
- If any finding violates these rules, the whole LLM Analyst result is rejected and deterministic findings are used.

Whole-result fallback is preferred over partial acceptance because it prevents hallucinated or partially invalid citations from mixing with valid-looking findings.

## Error Handling

LLM Analyst must fall back to deterministic Analyst behavior for:

- missing API key;
- OpenAI-compatible client construction error;
- API call error;
- empty response content;
- invalid JSON;
- invalid schema;
- empty `findings`;
- evidence IDs not present in the input evidence pool;
- evidence IDs that refer to unverified evidence.

The fallback should not mutate unrelated state. It should produce the same findings the deterministic Analyst would have produced for the same input.

Relevance judge error handling should remain as already implemented: it fails closed per evidence item rather than falling back to deterministic relevance, because filtering semantics are different from Analyst generation.

## Tests

Add or update tests without live network access.

### LLM Config Tests

- InsightGraph env vars override OpenAI env vars.
- OpenAI env vars are used as fallback.
- Default model is `gpt-4o-mini`.
- Explicit arguments override env vars.

### LLM Client Tests

- Fake OpenAI client receives configured model, messages, JSON response format, and `temperature=0`.
- Base URL is passed when configured.
- No test imports or calls a live OpenAI network client.
- API exceptions are not swallowed by the generic client.

### Relevance Refactor Tests

- Existing relevance tests continue to pass.
- OpenAI-compatible relevance judge still supports fake clients and factory/base URL behavior.

### Analyst Tests

- Default Analyst behavior remains deterministic.
- `INSIGHT_GRAPH_ANALYST_PROVIDER=llm` uses a fake LLM client and returns validated LLM findings.
- Missing API key falls back to deterministic findings.
- API error falls back to deterministic findings.
- Empty content falls back to deterministic findings.
- Invalid JSON falls back to deterministic findings.
- Invalid schema falls back to deterministic findings.
- Empty findings falls back to deterministic findings.
- Unknown evidence ID in LLM output falls back to deterministic findings.
- Unverified evidence ID in LLM output falls back to deterministic findings.

### Final Verification

- `python -m pytest -v`
- `python -m ruff check .`
- `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

The final CLI smoke test must run without setting LLM env vars and must still produce a deterministic report.

## Documentation

Update `README.md` to document:

- `INSIGHT_GRAPH_ANALYST_PROVIDER=deterministic|llm`.
- Reuse of `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL`.
- Default deterministic/offline behavior.
- OpenAI-compatible Analyst example command.
- Warning that tests do not call external LLMs.

## Migration Notes

The existing OpenAI-compatible relevance judge has local config/client helpers. This phase should move shared config/client responsibilities to `src/insight_graph/llm/` and update relevance to use them.

The migration must preserve:

- `get_relevance_judge("openai_compatible")` behavior.
- Existing relevance env vars.
- Existing fail-closed relevance behavior.
- Existing tests that instantiate fake clients or factories.

## Success Criteria

- The project has a shared LLM package that can call OpenAI-compatible chat completions through injected/fake clients in tests.
- Analyst can opt into LLM-generated findings with `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`.
- Default Analyst behavior remains deterministic and offline.
- Invalid LLM results never produce uncited or hallucinated findings.
- Relevance judge uses the shared LLM infrastructure without behavior regressions.
- Full tests, lint, and default CLI smoke pass.
