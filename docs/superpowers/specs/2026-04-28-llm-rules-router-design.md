# LLM Rules Router Design

## Goal

Add an internal rules-based LLM model router so InsightGraph can choose among user-defined model tiers by task purpose and prompt size. The router should support LiteLLM Proxy through the existing OpenAI-compatible client path without adding a required LiteLLM SDK dependency.

## Scope

- Add internal model routing for live LLM mode.
- Let users define model names for fast/default/strong tiers.
- Preserve existing `INSIGHT_GRAPH_LLM_MODEL` behavior when routing is disabled.
- Keep existing OpenAI-compatible client and wire API support.
- Keep all tests offline with fake clients/config.

## Non-goals

- No required `litellm` Python dependency.
- No automatic classifier model call before routing.
- No public API response changes.
- No provider-specific pricing or latency database.
- No per-user routing policy.

## Configuration

Routing is opt-in:

- `INSIGHT_GRAPH_LLM_ROUTER=rules`

Model tiers:

- `INSIGHT_GRAPH_LLM_MODEL_FAST`
- `INSIGHT_GRAPH_LLM_MODEL_DEFAULT`
- `INSIGHT_GRAPH_LLM_MODEL_STRONG`

Fallbacks:

- `FAST` falls back to `DEFAULT`.
- `DEFAULT` falls back to `INSIGHT_GRAPH_LLM_MODEL`, then current default `gpt-4o-mini`.
- `STRONG` falls back to `DEFAULT`.

Thresholds:

- `INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD`, default `2000`.
- `INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD`, default `12000`.

Invalid threshold values fail closed with `ValueError`.

## Architecture

Keep `get_llm_client()` as the public factory in `src/insight_graph/llm/router.py`.

Extend it to accept routing context:

```python
def get_llm_client(
    config: LLMConfig | None = None,
    *,
    purpose: str = "default",
    messages: list[ChatMessage] | None = None,
) -> OpenAICompatibleChatClient:
    ...
```

When routing is disabled, the function returns `OpenAICompatibleChatClient(config=config)` as today.

When `INSIGHT_GRAPH_LLM_ROUTER=rules`, the function resolves a selected model and creates a copied `LLMConfig` with that model. API key, base URL, and wire API are preserved.

This means LiteLLM Proxy works by setting:

```powershell
$env:INSIGHT_GRAPH_LLM_BASE_URL = "http://localhost:4000/v1"
$env:INSIGHT_GRAPH_LLM_API_KEY = "anything-or-proxy-key"
$env:INSIGHT_GRAPH_LLM_ROUTER = "rules"
$env:INSIGHT_GRAPH_LLM_MODEL_FAST = "cheap-model-alias"
$env:INSIGHT_GRAPH_LLM_MODEL_DEFAULT = "default-model-alias"
$env:INSIGHT_GRAPH_LLM_MODEL_STRONG = "strong-model-alias"
```

The aliases can be real OpenAI/OpenRouter model names or LiteLLM Proxy aliases.

## Routing Rules

Routing uses deterministic rules only.

Inputs:

- `purpose`: `analyst`, `reporter`, or `default` initially.
- total message characters, if messages are provided.

Initial behavior:

- `reporter` uses `strong` because final report quality matters.
- `analyst` uses `default`, upgraded to `strong` when total message characters exceed the strong threshold.
- `default` uses `default`, upgraded to `strong` when total message characters exceed the strong threshold.
- `default` prompts below the fast threshold use `fast`.
- `analyst` never uses `fast` in the first implementation to avoid reducing analysis quality.

If messages are not provided, routing uses purpose only.

## Agent Integration

Update agent call sites to pass purpose and messages when creating a client:

- Analyst: `purpose="analyst"`.
- Reporter: `purpose="reporter"`.

Existing tests and callers that inject `llm_client` remain unchanged. Routing only applies when the agent creates its own client.

## Observability

Existing LLM call logs already record the selected model through `config.model`. No new public fields are required.

Tier logging is out of scope for the first implementation. A future change can add it if users need to audit routing decisions separately from model names.

## Error Handling

- Unknown router values fail closed with `ValueError`.
- Invalid thresholds fail closed with `ValueError`.
- Missing tier model env vars use the fallback chain.
- Missing API key behavior remains unchanged in `OpenAICompatibleChatClient`.

## Testing Requirements

Add `tests/test_llm_router.py` for pure routing behavior:

- Router disabled preserves current configured model.
- Rules router selects `fast`, `default`, and `strong` in expected cases.
- Missing tier env vars fall back correctly.
- Selected configs preserve API key, base URL, and wire API.
- Invalid router names fail.
- Invalid thresholds fail.

Update existing agent tests only where needed:

- Analyst-created clients use `purpose="analyst"` and pass messages.
- Reporter-created clients use `purpose="reporter"` and pass messages.

All tests must remain deterministic and offline.

## Documentation

Document the new env vars and include a LiteLLM Proxy example. The docs should clearly state that LiteLLM Proxy is optional and works through the existing OpenAI-compatible base URL path.
