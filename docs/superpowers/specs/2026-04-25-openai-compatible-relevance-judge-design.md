# OpenAI-Compatible Relevance Judge Design

## Context

InsightGraph currently supports opt-in deterministic relevance filtering. The filtering hook is in Executor, and `DeterministicRelevanceJudge` keeps tests offline while establishing the data flow.

The next increment adds a real LLM relevance judge through the OpenAI-compatible chat completions API. This supports OpenAI official endpoints and common API-compatible gateways or model providers without introducing multiple SDK integrations.

## Goals

- Add `OpenAICompatibleRelevanceJudge` as an opt-in relevance judge.
- Support OpenAI official API and OpenAI-compatible relay/provider endpoints.
- Keep `deterministic` as the default judge.
- Keep tests offline by mocking the OpenAI client.
- Fail closed: API/config/parse failures should return `relevant=False` instead of crashing Executor.

## Non-Goals

- No Anthropic/Gemini/native DashScope SDK integration in this phase.
- No LLM router.
- No streaming responses.
- No batch relevance calls.
- No token budget manager.
- No full prompt/response observability log.

## Dependencies

Add runtime dependency:

- `openai>=1.0.0`

The dependency is only used when `INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible` or an explicit `get_relevance_judge("openai_compatible")` call is used.

## Configuration

Primary configuration:

- `INSIGHT_GRAPH_RELEVANCE_FILTER=1`
- `INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible`
- `INSIGHT_GRAPH_LLM_API_KEY`
- `INSIGHT_GRAPH_LLM_BASE_URL`
- `INSIGHT_GRAPH_LLM_MODEL`

Fallback compatibility:

- If `INSIGHT_GRAPH_LLM_API_KEY` is missing, read `OPENAI_API_KEY`.
- If `INSIGHT_GRAPH_LLM_BASE_URL` is missing, read `OPENAI_BASE_URL`.
- If `INSIGHT_GRAPH_LLM_MODEL` is missing, default to `gpt-4o-mini`.

`INSIGHT_GRAPH_LLM_BASE_URL` / `OPENAI_BASE_URL` may be omitted for OpenAI official default endpoint. For relay services, it should point at a compatible `/v1` endpoint.

## Supported Providers

Any service compatible with OpenAI chat completions can be used, including:

- OpenAI official API.
- User-provided relay/gateway services.
- OpenRouter.
- DeepSeek OpenAI-compatible endpoint.
- Moonshot/Kimi compatible endpoint.
- SiliconFlow compatible endpoint.
- Other compatible `/v1/chat/completions` providers.

Provider-specific quirks are not handled in this phase; the contract is OpenAI-compatible chat completions with text content.

## Relevance Module Changes

Extend `src/insight_graph/agents/relevance.py`.

New units:

- `OpenAICompatibleRelevanceJudge`
  - Accepts optional `client`, `api_key`, `base_url`, and `model` for test injection.
  - Creates an OpenAI client lazily or during initialization using `openai.OpenAI`.
  - Calls `client.chat.completions.create(...)`.
  - Parses the first message content as JSON.
  - Returns `EvidenceRelevanceDecision`.
- `_create_openai_client(api_key: str, base_url: str | None)`
  - Uses `OpenAI(api_key=api_key, base_url=base_url)` when `base_url` is set.
  - Uses `OpenAI(api_key=api_key)` when `base_url` is unset.
- `_parse_relevance_json(content: str, evidence_id: str)`
  - Parses strict JSON object.
  - Requires `relevant` boolean.
  - Uses `reason` if it is a non-empty string; otherwise uses a generic reason.
  - Raises `ValueError` for invalid JSON or invalid schema.

`get_relevance_judge()` supports:

- `deterministic`
- `openai_compatible`

Unknown judge names still raise `ValueError`.

## Prompt Contract

The OpenAI-compatible judge sends a small instruction asking for JSON only.

Inputs included:

- User research query.
- Subtask id and description.
- Evidence id.
- Evidence title.
- Evidence source URL.
- Evidence snippet.
- Evidence verified flag.

Expected response content:

```json
{"relevant": true, "reason": "The evidence directly discusses the requested product pricing."}
```

or:

```json
{"relevant": false, "reason": "The evidence is about an unrelated topic."}
```

## Failure Strategy

The judge must fail closed and return a not-relevant decision for:

- Missing API key.
- OpenAI client creation failure.
- API call failure.
- Empty model response.
- Invalid JSON.
- JSON with missing or non-boolean `relevant`.

The reason should be explicit enough for debugging, for example:

- `OpenAI-compatible relevance judge is missing an API key.`
- `OpenAI-compatible relevance judge failed: <message>`
- `OpenAI-compatible relevance judge returned invalid JSON.`

Executor should not need new exception handling for relevance judge failures because the judge converts them into decisions.

## Testing Strategy

- Existing deterministic tests remain unchanged.
- OpenAI-compatible tests use fake clients only and do not access the network.
- Tests cover:
  - `get_relevance_judge("openai_compatible")` returns `OpenAICompatibleRelevanceJudge`.
  - API key/model/base URL resolution from `INSIGHT_GRAPH_LLM_*` env vars.
  - fallback to `OPENAI_API_KEY` and `OPENAI_BASE_URL`.
  - relevant true JSON response.
  - relevant false JSON response.
  - malformed JSON response fails closed.
  - API exception fails closed.
  - missing API key fails closed.
- Full CLI tests continue to use default deterministic/offline path unless env vars are explicitly set in a test.

## README Update

Document:

- `INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible` enables the compatible LLM judge.
- `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL` configure provider access.
- `OPENAI_API_KEY` and `OPENAI_BASE_URL` are supported fallbacks.
- Default judge remains deterministic.
- Tests do not call external LLMs.

## Acceptance Criteria

- `get_relevance_judge("openai_compatible")` returns an OpenAI-compatible judge.
- OpenAI-compatible judge supports custom base URL for relays.
- OpenAI-compatible judge returns relevance decisions from valid JSON responses.
- Missing API key, API errors, and invalid JSON return `relevant=False` without raising.
- Default CLI and test suite remain offline unless explicitly configured.
- Full tests pass.
- Ruff passes.

## Future Work

- Add native Qwen/DashScope judge if OpenAI-compatible endpoints are insufficient.
- Add Anthropic or Gemini native judges.
- Add prompt/response logging and token accounting.
- Add batched relevance evaluation.
