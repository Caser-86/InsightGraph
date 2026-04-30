# Embedding Provider Boundary Design

## Goal

Add an opt-in embedding provider boundary for external or local embedding services while preserving deterministic offline embeddings as the default. This prepares document indexing and memory retrieval for real embedding providers without requiring cloud credentials or network access in normal runs.

## Providers

`INSIGHT_GRAPH_EMBEDDING_PROVIDER` supports:

- `deterministic`: current offline hashing embedding; default.
- `openai_compatible`: POST to an OpenAI-compatible `/embeddings` endpoint.
- `local_http`: POST to a user-provided local HTTP endpoint with a simple JSON payload.

External providers are never used unless explicitly selected. Tests use fake transport functions and never call a live endpoint.

## Configuration

Common variables:

- `INSIGHT_GRAPH_EMBEDDING_PROVIDER`
- `INSIGHT_GRAPH_EMBEDDING_MODEL`
- `INSIGHT_GRAPH_EMBEDDING_DIMENSIONS`
- `INSIGHT_GRAPH_EMBEDDING_BASE_URL`
- `INSIGHT_GRAPH_EMBEDDING_API_KEY`

`openai_compatible` also falls back to `INSIGHT_GRAPH_LLM_BASE_URL` and `INSIGHT_GRAPH_LLM_API_KEY` when embedding-specific settings are absent. `local_http` requires an explicit base URL and can omit the API key.

## Architecture

`src/insight_graph/memory/embeddings.py` gains an `EmbeddingConfig`, provider resolution, and a single `embed_text()` entry point. `build_memory_record()` and document indexing can continue using deterministic embeddings until they opt into `embed_text()`. This phase should wire `build_memory_record()` to `embed_text()` and leave document index behavior deterministic unless explicitly updated in a later phase.

The HTTP boundary is dependency-light and accepts an injectable transport for tests. Provider failures raise a safe `EmbeddingProviderError`; callers should decide whether to fail or fall back.

## Request/Response Shapes

`openai_compatible` sends:

```json
{"model": "text-embedding-3-small", "input": "text"}
```

It expects `data[0].embedding` as a numeric list.

`local_http` sends:

```json
{"text": "text", "model": "optional-model", "dimensions": 64}
```

It accepts either `{"embedding": [...]}` or OpenAI-compatible `{"data": [{"embedding": [...]}]}`.

## Safety

The default remains offline. Unknown providers fall back to deterministic for backward compatibility in `get_embedding_provider()`, but explicit provider resolution used by `embed_text()` rejects unsupported providers. External responses validate finite numeric vectors and expected dimensions when dimensions are configured.

## Testing

Tests cover deterministic defaults, config resolution, unknown provider rejection in explicit resolution, OpenAI-compatible request/response parsing, local HTTP parsing, invalid response rejection, and `build_memory_record()` metadata using the selected provider.
