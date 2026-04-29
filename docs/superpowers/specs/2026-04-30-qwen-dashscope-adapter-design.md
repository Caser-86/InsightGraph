# Qwen/DashScope Adapter Design

## Goal

Add a named Qwen/DashScope LLM provider without changing InsightGraph's offline deterministic defaults. The provider is config sugar over the existing OpenAI-compatible client because DashScope exposes an OpenAI-compatible API surface for chat completions.

## User-Facing Behavior

Users can select Qwen with `INSIGHT_GRAPH_LLM_PROVIDER=qwen`. When selected, config resolution supplies Qwen defaults only for fields the user did not explicitly set:

- `base_url`: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `model`: `qwen-plus`
- `api_key`: `INSIGHT_GRAPH_LLM_API_KEY`, then `DASHSCOPE_API_KEY`, then existing OpenAI fallback
- `wire_api`: existing default, unless `INSIGHT_GRAPH_LLM_WIRE_API` or explicit args override it

Existing env vars and explicit function arguments continue to win. `INSIGHT_GRAPH_LLM_BASE_URL` and `INSIGHT_GRAPH_LLM_MODEL` override Qwen defaults. `OPENAI_API_KEY` remains a final fallback for compatibility, but Qwen-specific `DASHSCOPE_API_KEY` is preferred when provider is `qwen`.

## Architecture

`LLMConfig` gains a `provider` field. `resolve_llm_config()` reads an explicit `provider` argument or `INSIGHT_GRAPH_LLM_PROVIDER`, defaults to `openai_compatible`, validates supported names, and resolves provider defaults in one place.

No separate client class is added. `OpenAICompatibleChatClient` keeps using `LLMConfig.base_url`, `model`, `api_key`, and `wire_api`. This keeps network behavior unchanged and avoids duplicating the OpenAI SDK wrapper.

## Error Handling

Unknown providers raise `ValueError` during config resolution, matching existing `wire_api` validation behavior. Missing API keys continue to fail at client call time with `LLM api_key is required`.

## Testing

Tests cover:

- default provider remains OpenAI-compatible behavior
- `INSIGHT_GRAPH_LLM_PROVIDER=qwen` applies DashScope base URL and `qwen-plus`
- explicit args and `INSIGHT_GRAPH_LLM_*` env vars override provider defaults
- Qwen provider reads `DASHSCOPE_API_KEY`
- unknown provider is rejected

All tests remain offline and use config-only assertions.
