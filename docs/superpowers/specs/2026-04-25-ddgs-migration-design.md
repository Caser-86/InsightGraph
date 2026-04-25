# DDGS Migration Design

## Goal

Replace the deprecated `duckduckgo-search` package with the renamed `ddgs` package so live search no longer emits the runtime warning:

```text
This package (`duckduckgo_search`) has been renamed to `ddgs`! Use `pip install ddgs` instead.
```

## Non-Goals

- Do not change search provider selection names. `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo` remains valid.
- Do not change `SearchResult` fields or source labels.
- Do not alter fallback-to-mock behavior.
- Do not add a compatibility fallback to `duckduckgo_search`.
- Do not change live preset defaults.

## Decision

Use **replace only**:

- Remove `duckduckgo-search>=6.0.0` from `pyproject.toml`.
- Add `ddgs>=9.0.0` to `pyproject.toml`.
- Change `_create_duckduckgo_client()` to import `DDGS` from `ddgs`.

No legacy fallback import will be kept. The project is still early, and keeping a deprecated import path would preserve unnecessary complexity and may allow the warning to reappear.

## Current Compatibility Check

The local environment has both packages installed. `ddgs` exposes the same `DDGS().text(query, max_results=limit)` surface used by the current adapter:

- `ddgs` installed: yes
- `from ddgs import DDGS`: works
- `DDGS().text`: exists

The existing fake-client tests already isolate the adapter behavior without network access.

## Implementation

Modify `pyproject.toml`:

```toml
dependencies = [
  "beautifulsoup4>=4.12.0",
  "ddgs>=9.0.0",
  ...
]
```

Modify `src/insight_graph/tools/search_providers.py`:

```python
def _create_duckduckgo_client() -> Any:
    from ddgs import DDGS

    return DDGS()
```

All other code paths remain unchanged:

- `DuckDuckGoSearchProvider` class name stays the same.
- `get_search_provider("duckduckgo")` stays the same.
- `SearchResult.source` remains `"duckduckgo"` for mapped live results.
- Existing empty/failure behavior remains `[]`, allowing executor fallback to `mock_search` to handle live search failure or no evidence.

## Testing

Use fake clients only for unit tests. Do not access the network in automated tests.

Coverage:

- Existing DuckDuckGo mapping tests continue to pass.
- Existing provider selection tests continue to pass.
- `_create_duckduckgo_client()` imports `DDGS` from `ddgs`, not `duckduckgo_search`.
- Full test suite remains green.
- Live smoke no longer prints the `duckduckgo_search` rename warning.

Run at minimum:

```bash
python -m pytest tests/test_search_providers.py tests/test_web_search.py -q
python -m ruff check src/insight_graph/tools/search_providers.py tests/test_search_providers.py
```

Final verification:

```bash
python -m pytest -v
python -m ruff check .
```

Live smoke after implementation:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --output-json
```

Expected live smoke result:

- No `duckduckgo_search` rename warning appears.
- Workflow still completes.
- If live search returns no evidence, existing executor fallback records failed `web_search` and successful `mock_search` fallback records.

## Rollout

This is a dependency migration with no user-facing CLI changes. Users should reinstall dependencies after pulling the change so `ddgs` is available in their environment.
