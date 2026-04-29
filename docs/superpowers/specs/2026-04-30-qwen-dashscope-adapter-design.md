# Multi-Provider LLM Config Design

## Goal

Add a general LLM provider preset layer that supports local/self-hosted OpenAI-compatible runtimes first, while keeping Qwen/DashScope as one optional cloud preset. InsightGraph remains offline and deterministic by default; selecting a provider only resolves config and does not enable live LLM calls by itself.

## Providers

`INSIGHT_GRAPH_LLM_PROVIDER` supports:

- `openai_compatible`: existing generic behavior; reads `OPENAI_API_KEY` and `OPENAI_BASE_URL` fallbacks.
- `ollama`: local default `http://localhost:11434/v1`, model `qwen2.5:7b`, dummy API key `ollama`.
- `lmstudio`: local default `http://localhost:1234/v1`, model `local-model`, dummy API key `lm-studio`.
- `vllm`: self-hosted default `http://localhost:8000/v1`, model `local-model`, dummy API key `vllm`.
- `localai`: self-hosted default `http://localhost:8080/v1`, model `local-model`, dummy API key `localai`.
- `qwen`: DashScope default `https://dashscope.aliyuncs.com/compatible-mode/v1`, model `qwen-plus`, API key from `DASHSCOPE_API_KEY` when `INSIGHT_GRAPH_LLM_API_KEY` is unset.

All providers continue to use the existing OpenAI-compatible client. No provider adds network calls by default.

## Override Rules

Explicit `resolve_llm_config(...)` arguments win over all environment variables. `INSIGHT_GRAPH_LLM_API_KEY`, `INSIGHT_GRAPH_LLM_BASE_URL`, and `INSIGHT_GRAPH_LLM_MODEL` override provider defaults.

Provider-specific defaults apply only after explicit args and `INSIGHT_GRAPH_LLM_*` env vars are absent. `OPENAI_API_KEY` and `OPENAI_BASE_URL` remain compatibility fallbacks for `openai_compatible`; `OPENAI_API_KEY` may be a final API-key fallback for cloud-compatible providers, but `OPENAI_BASE_URL` must not override named provider endpoints.

## Architecture

`LLMConfig` keeps a `provider` field. `resolve_llm_config()` validates provider names and resolves defaults from a small in-module preset table. This avoids one-off provider conditionals and makes adding Minimax or other OpenAI-compatible providers a data change.

The existing `OpenAICompatibleChatClient` remains unchanged. It consumes the resolved `api_key`, `base_url`, `model`, and `wire_api` values.

## Error Handling

Unknown providers raise `ValueError` during config resolution. Missing API keys continue to fail at client call time, except local providers provide dummy keys because many local OpenAI-compatible runtimes require a syntactic key but do not authenticate it.

## Testing

Tests cover default behavior, all local provider defaults, Qwen/DashScope defaults, override precedence, stale `OPENAI_BASE_URL` isolation for named providers, and unknown provider rejection. Tests are config-only and never call external services.
