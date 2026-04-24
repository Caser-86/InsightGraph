# Search Provider Design

## Context

InsightGraph currently has the search-to-evidence shape used by the wenyi reference architecture: `web_search -> pre_fetch -> fetch_url -> Evidence`. The current `web_search` implementation is deterministic mock-only, which keeps tests stable but does not yet provide real search results.

The next increment aligns the tool layer with wenyi's real `web_search` capability while preserving the current MVP default behavior.

## Goals

- Add a provider abstraction for `web_search`.
- Keep deterministic mock search as the default provider.
- Add an opt-in DuckDuckGo provider for real web search.
- Keep `web_search(query, subtask_id)` returning `list[Evidence]` through the existing `pre_fetch_results` path.
- Keep all tests offline and deterministic.
- Preserve current CLI and Planner behavior unless the user explicitly enables a real provider.

## Non-Goals

- No `Collector -> Executor` rewrite in this phase.
- No multi-round tool loop.
- No LLM relevance filtering.
- No Qwen Search provider yet.
- No Playwright rendering.
- No PDF extraction, Trafilatura, or document RAG.
- No default live-network behavior in tests or CLI smoke tests.

## Architecture

Add a provider layer under `src/insight_graph/tools/search_providers.py`.

Core units:

- `SearchProvider`: protocol with `search(query: str, limit: int) -> list[SearchResult]`.
- `MockSearchProvider`: wraps the existing deterministic results.
- `DuckDuckGoSearchProvider`: calls a DuckDuckGo search client and maps results into `SearchResult`.
- `get_search_provider(name: str | None = None) -> SearchProvider`: resolves provider name from argument or environment.

`web_search.py` remains the registry-facing tool module. It will delegate candidate generation to the selected provider, then call `pre_fetch_results`:

```text
web_search(query, subtask_id)
  -> get_search_provider()
  -> provider.search(query, limit)
  -> pre_fetch_results(results, subtask_id, limit)
  -> list[Evidence]
```

The existing callable module export behavior for `from insight_graph.tools import web_search` must remain covered by tests.

## Configuration

Environment variables:

- `INSIGHT_GRAPH_SEARCH_PROVIDER`: provider name. Supported values: `mock`, `duckduckgo`. Default: `mock`.
- `INSIGHT_GRAPH_SEARCH_LIMIT`: number of candidate search results to pre-fetch. Default: `3`.

Invalid provider names raise a clear `ValueError` from provider resolution.

Invalid limits fall back to `3` rather than crashing the CLI.

## DuckDuckGo Provider

The DuckDuckGo provider should use the `duckduckgo-search` package if available. It should be isolated behind `DuckDuckGoSearchProvider` so tests can monkeypatch the underlying client without live network calls.

Result mapping:

- DuckDuckGo title -> `SearchResult.title`
- DuckDuckGo href/url/link -> `SearchResult.url`
- DuckDuckGo body/snippet -> `SearchResult.snippet`
- provider source -> `SearchResult.source = "duckduckgo"`

Malformed results without a URL are skipped.

Search failures return an empty result list. The failure is contained at the provider boundary so that the current MVP research flow does not crash because live search is temporarily unavailable.

## Testing Strategy

- Mock provider tests verify deterministic URL order and `source="mock"`.
- Provider resolution tests verify default `mock`, explicit `duckduckgo`, environment-based selection, invalid provider errors, and limit parsing.
- DuckDuckGo provider tests monkeypatch the DuckDuckGo client and do not access the network.
- `web_search` tests monkeypatch provider resolution or provider output, then verify pre-fetch is called with expected results and limit.
- Existing `pre_fetch`, `fetch_url`, registry, CLI, and callable export tests must continue to pass.

## README Update

Update current MVP documentation to say the tool layer supports:

- deterministic mock search by default;
- opt-in DuckDuckGo provider via `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo`;
- `web_search -> pre_fetch -> fetch_url` evidence acquisition.

The README must also state that default CLI behavior remains mock/offline unless the provider is explicitly changed.

## Acceptance Criteria

- `web_search` defaults to deterministic mock behavior with no environment variables.
- Setting `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo` makes `web_search` use the DuckDuckGo provider.
- Setting `INSIGHT_GRAPH_SEARCH_LIMIT` changes the candidate pre-fetch limit.
- Unit tests do not access the live network.
- Full test suite passes.
- Ruff passes.
- CLI smoke test still produces an InsightGraph report by default.

## Future Work

- Add Qwen Search provider.
- Add wenyi-style multi-round Executor.
- Add LLM relevance filtering after pre-fetch.
- Add PDF, Trafilatura, Playwright, and document RAG support.
