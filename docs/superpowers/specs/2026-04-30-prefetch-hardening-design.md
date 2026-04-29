# Pre-Fetch Pipeline Hardening Design

## Goal

Harden the existing search -> pre-fetch pipeline without changing InsightGraph's default offline and deterministic behavior.

## Scope

- Keep `web_search` as the entry point that converts search results into fetched `Evidence`.
- Keep network access behind the existing explicit search/fetch opt-in surfaces.
- Improve `pre_fetch_results()` so one failing URL does not fail the whole collection pass.
- Respect the existing research fetch budget when deciding how many search results to fetch.
- Pass the original research query into `fetch_url` as a retrieval query so long HTML/PDF chunks can be ranked for the active request.

## Design

`pre_fetch_results()` will accept an optional `query` argument. When present, each URL fetch will call `fetch_url()` with a JSON payload containing `url` and `query`; this reuses the existing `fetch_url` retrieval-query parser and chunk-ranking logic. When absent, it preserves the current plain-URL behavior.

The function will cap fetch attempts by the smaller of the caller limit and `get_research_budgets().max_fetches`. Each result fetch will be isolated with `try/except`; failures return no evidence for that URL but continue with remaining results.

`web_search()` will pass its active query into `pre_fetch_results()`. Existing tests that monkeypatch `pre_fetch_results()` will be updated to include the query argument.

## Testing

- RED test: `pre_fetch_results()` continues after a URL fetch raises.
- RED test: `pre_fetch_results()` respects `INSIGHT_GRAPH_MAX_FETCHES`.
- RED test: `pre_fetch_results()` passes JSON `{url, query}` to `fetch_url` when a retrieval query is provided.
- Regression test: `web_search()` passes the user query through to `pre_fetch_results()`.

## Non-Goals

- No new network provider.
- No external embedding or LLM reranking.
- No change to default CLI/API offline behavior.
- No persistent pre-fetch cache.
