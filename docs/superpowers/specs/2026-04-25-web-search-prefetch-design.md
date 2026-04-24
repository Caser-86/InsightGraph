# Web Search Pre-fetch Pipeline Design

## Purpose

InsightGraph now has a direct URL evidence tool: `fetch_url` can turn an HTTP/HTTPS page into verified `Evidence`. The next increment adds the search-to-evidence bridge used by the reference architecture: `web_search -> candidate URLs -> pre-fetch -> verified evidence_pool`.

This phase deliberately uses deterministic mock search results. It establishes the interfaces and orchestration shape before introducing unstable external search APIs.

## Scope

This design covers:

- A typed `SearchResult` model for candidate search results.
- A deterministic `mock_web_search(query)` implementation.
- A `web_search(query, subtask_id)` tool adapter that matches the existing `ToolRegistry` callable shape and returns `Evidence` by pre-fetching candidate URLs.
- A `pre_fetch_results(results, subtask_id, limit)` function that calls the existing `fetch_url` tool for the first N results.
- ToolRegistry registration for `web_search`.
- Unit tests with monkeypatched fetch behavior and no live network.

This design does not cover:

- DuckDuckGo, Tavily, SerpAPI, Qwen Search, or any live search provider.
- LLM relevance filtering.
- Deduplication across subtasks or persistent `global_evidence_pool` storage.
- Changing the default Planner to use `web_search`.
- Changing the current CLI behavior.

## Recommended Approach

Add a deterministic `web_search` tool that internally uses `mock_web_search` plus `pre_fetch_results`. This gives the system the same architectural shape as the reference project while keeping tests stable and offline.

The existing `fetch_url` remains the evidence conversion boundary. Search returns candidate URLs; pre-fetch decides how many to fetch; `fetch_url` decides whether a page produces verified evidence.

## Architecture

```text
ToolRegistry
  ├── mock_search(query, subtask_id) -> list[Evidence]
  ├── fetch_url(url, subtask_id) -> list[Evidence]
  └── web_search(query, subtask_id) -> list[Evidence]

web_search(query, subtask_id)
  ├── mock_web_search(query) -> list[SearchResult]
  ├── pre_fetch_results(results, subtask_id, limit=3)
  │   └── fetch_url(result.url, subtask_id)
  └── list[Evidence]
```

## Components

### `web_search.py`

Responsibilities:

- Define `SearchResult(title, url, snippet, source)`.
- Provide `mock_web_search(query)` with deterministic candidate URLs.
- Provide `web_search(query, subtask_id="collect")` that returns verified evidence by pre-fetching top results.

Public API:

```python
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"

def mock_web_search(query: str) -> list[SearchResult]: ...

def web_search(query: str, subtask_id: str = "collect") -> list[Evidence]: ...
```

The mock implementation should return URLs aligned with the current domain:

- `https://cursor.com/pricing`
- `https://docs.github.com/copilot`
- `https://github.com/sst/opencode`

It may inspect `query` later, but in this increment it can return a stable list for all queries.

### `pre_fetch.py`

Responsibilities:

- Accept search results and a subtask ID.
- Fetch only the first `limit` results.
- Call `fetch_url(result.url, subtask_id)` for each result.
- Flatten returned evidence lists.
- Continue when one URL returns no evidence.

Public API:

```python
def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
) -> list[Evidence]: ...
```

In this increment, `pre_fetch_results` does not catch `FetchError`. Tests should exercise normal and empty-evidence paths. Error tolerance can be added later when real search providers are introduced.

### `ToolRegistry`

Register `web_search` beside `mock_search` and `fetch_url`.

The registry callable shape remains unchanged:

```python
ToolFn = Callable[[str, str], list[Evidence]]
```

This keeps Collector unchanged.

## Data Flow

```text
Collector subtask suggested_tools = ["web_search"]
  -> ToolRegistry.run("web_search", query=user_request, subtask_id="collect")
  -> mock_web_search(query)
  -> pre_fetch_results(results, subtask_id="collect", limit=3)
  -> fetch_url(candidate_url, subtask_id="collect")
  -> list[Evidence]
  -> state.evidence_pool
```

The current Planner still emits `mock_search`. This design only adds the tool path so later Planner/CLI work can opt into it.

## Error Handling

- Unknown tools still raise `KeyError` from `ToolRegistry`.
- Search result URLs are passed to `fetch_url` as-is.
- Empty evidence from one candidate is skipped naturally because `fetch_url` returns `[]`.
- Fetch errors are not swallowed in this increment; this keeps failures visible while the provider remains deterministic and test-controlled.

## Testing Strategy

Tests must not use live network access.

Planned tests:

- `tests/test_web_search.py`
  - Verifies `mock_web_search` returns deterministic `SearchResult` objects.
  - Verifies `web_search` returns evidence by monkeypatching `pre_fetch_results`.

- `tests/test_pre_fetch.py`
  - Verifies `pre_fetch_results` fetches only the first `limit` results.
  - Verifies it flattens evidence returned by `fetch_url`.
  - Verifies candidates returning empty evidence are skipped.

- `tests/test_tools.py`
  - Verifies `ToolRegistry.run("web_search", query, subtask_id)` returns evidence.
  - Verifies existing `mock_search`, `fetch_url`, and unknown tool behavior remain intact.

Existing CLI and graph tests should remain unchanged and passing.

## Acceptance Criteria

- `web_search` is registered in `ToolRegistry`.
- `mock_web_search` returns typed `SearchResult` objects.
- `pre_fetch_results` limits candidates and converts URLs to verified evidence through `fetch_url`.
- Tests do not access live network.
- Default Planner and CLI behavior remain unchanged.
- `python -m pytest -v` and `python -m ruff check .` pass.

## Future Extensions

After this increment:

1. Add a provider interface for real search engines.
2. Add provider-specific adapters for DuckDuckGo or Tavily.
3. Add relevance filtering before evidence enters `evidence_pool`.
4. Add URL deduplication and provenance metadata.
5. Add Planner or CLI opt-in to `web_search`.
