# Evidence Acquisition Pipeline Design

## Purpose

InsightGraph currently uses deterministic `mock_search` evidence. The next increment adds the first real evidence-acquisition layer: given a direct URL, fetch the page, extract readable content, and convert it into verified `Evidence`. This mirrors the reference project's `web_search -> fetch_url -> content_extract -> evidence_snippets -> verified sources` chain, but deliberately starts with direct URL fetching before adding search APIs.

## Scope

This design covers:

- Fetching text content from a direct HTTP/HTTPS URL.
- Extracting title, readable text, and a short snippet from HTML.
- Producing one verified `Evidence` object from a successfully fetched page.
- Registering `fetch_url` beside existing `mock_search` in `ToolRegistry`.
- Keeping the current CLI and Planner default behavior unchanged, so existing deterministic tests remain stable.

This design does not cover:

- Search engines such as DuckDuckGo, Tavily, or SerpAPI.
- Playwright, JavaScript rendering, login-gated pages, or anti-bot bypass.
- PDF parsing, RAG chunking, vector storage, FastAPI, PostgreSQL, or LLM relevance filtering.
- Live-network tests in CI.

## Recommended Approach

Use the Python standard library for HTTP and `beautifulsoup4` for HTML extraction.

This keeps the implementation small and stable while still giving the project a real evidence boundary. `urllib.request` is sufficient for direct URL fetching in this phase. `beautifulsoup4` provides predictable HTML parsing and easy removal of non-content tags.

Alternatives considered:

- `httpx + beautifulsoup4`: cleaner client API, but adds another runtime dependency before we need advanced HTTP behavior.
- `Playwright / Trafilatura`: closer to production research extraction, but too heavy for this increment and harder to test quickly.

## Architecture

```text
ToolRegistry
  ├── mock_search(query, subtask_id) -> list[Evidence]
  └── fetch_url(url, subtask_id) -> list[Evidence]

fetch_url
  ├── http_client.fetch_text(url)
  ├── content_extract.extract_page_content(html, url)
  └── Evidence(..., verified=True)
```

The `fetch_url` tool follows the same callable shape as `mock_search`: `(query: str, subtask_id: str) -> list[Evidence]`. For this tool, `query` is interpreted as the URL. This preserves the current `ToolRegistry` interface and avoids changing `Collector` in this increment.

## Components

### `http_client.py`

Responsibilities:

- Validate that the URL scheme is `http` or `https`.
- Fetch page bytes using `urllib.request.urlopen` with a timeout.
- Decode text using the response charset when available, falling back to UTF-8 with replacement.
- Return `FetchedPage(url, status_code, content_type, text)`.
- Raise `FetchError` for unsupported schemes, network errors, empty bodies, or non-2xx responses.

Public API:

```python
class FetchError(RuntimeError): ...

class FetchedPage(BaseModel):
    url: str
    status_code: int
    content_type: str
    text: str

def fetch_text(url: str, timeout: float = 10.0) -> FetchedPage: ...
```

### `content_extract.py`

Responsibilities:

- Parse HTML with BeautifulSoup.
- Extract title from `<title>` or fallback to the URL domain.
- Remove `script`, `style`, `nav`, `footer`, `header`, `noscript`, and `svg` tags.
- Normalize whitespace.
- Create a snippet from the first 300 characters of extracted text.
- Return `ExtractedContent(title, text, snippet)`.

Public API:

```python
class ExtractedContent(BaseModel):
    title: str
    text: str
    snippet: str

def extract_page_content(html: str, url: str, snippet_chars: int = 300) -> ExtractedContent: ...
```

If the extracted body is empty, the function returns an empty `text` and `snippet`; `fetch_url` decides whether that is acceptable evidence.

### `fetch_url.py`

Responsibilities:

- Call `fetch_text`.
- Call `extract_page_content`.
- Reject pages with empty snippets by returning an empty evidence list.
- Infer `source_type` from URL/domain:
  - `github.com` -> `github`
  - domains starting with `docs.` or paths containing `/docs` -> `docs`
  - otherwise `unknown`
- Build deterministic evidence IDs from URL domains and paths.
- Return exactly one verified `Evidence` for successful extraction.

Public API:

```python
def fetch_url(url: str, subtask_id: str = "collect") -> list[Evidence]: ...
```

## Data Flow

```text
Collector subtask suggested_tools = ["fetch_url"]
  -> ToolRegistry.run("fetch_url", query=url, subtask_id="collect")
  -> fetch_text(url)
  -> extract_page_content(html, url)
  -> Evidence(id, subtask_id, title, source_url, snippet, source_type, verified=True)
  -> state.evidence_pool
```

The current Planner will still emit `mock_search` by default. Direct URL collection can be exercised through tool-level tests first. A later plan can add CLI support such as `insight-graph fetch-url <url>` or Planner URL detection.

## Error Handling

- Unsupported URL schemes raise `FetchError` from `fetch_text`.
- HTTP/network errors raise `FetchError` with a concise message.
- Empty or non-extractable pages return no evidence from `fetch_url`.
- `ToolRegistry.run()` continues to raise `KeyError` for unknown tools.
- The Collector does not change in this increment, so existing graph failure behavior remains governed by Critic and Reporter.

## Testing Strategy

Tests must not use live network access.

Planned tests:

- `tests/test_content_extract.py`
  - Extracts title, body text, and snippet from simple HTML.
  - Removes script/style/navigation content.
  - Falls back to URL domain when title is missing.

- `tests/test_fetch_url.py`
  - Monkeypatches `fetch_url.fetch_text` to return a `FetchedPage`.
  - Verifies successful URL fetch returns one verified `Evidence`.
  - Verifies empty extracted content returns an empty list.
  - Verifies GitHub/docs source type inference.

- `tests/test_tools.py`
  - Verifies `ToolRegistry.run("fetch_url", url, subtask_id)` returns evidence.
  - Verifies unknown tools still raise `KeyError`.

Existing tests for `mock_search`, graph execution, Reporter verified-only behavior, and CLI output must remain unchanged and passing.

## Future Extensions

After this increment, the next natural steps are:

1. `web_search` tool that returns candidate URLs.
2. Pre-fetch top N search results using `fetch_url`.
3. LLM or rules-based relevance filtering before adding to `evidence_pool`.
4. Reporter-side citation URL revalidation.
5. PDF and large document extraction.

## Acceptance Criteria

- `fetch_url` is registered in `ToolRegistry` without breaking `mock_search`.
- HTML extraction removes non-content tags and creates deterministic snippets.
- Successful direct URL fetches produce verified `Evidence`.
- Empty extraction does not produce misleading evidence.
- All tests pass with no live network access.
- `python -m pytest -v` and `python -m ruff check .` pass.
