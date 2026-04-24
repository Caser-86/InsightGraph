# Evidence Acquisition Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a direct URL evidence-acquisition tool that fetches HTML, extracts readable content, and converts successful pages into verified `Evidence` without changing the default deterministic CLI workflow.

**Architecture:** Add three focused tool modules: `http_client.py` for direct HTTP fetching, `content_extract.py` for deterministic HTML extraction, and `fetch_url.py` for Evidence conversion. Register `fetch_url` in the existing `ToolRegistry` while keeping `mock_search` and Planner defaults unchanged.

**Tech Stack:** Python 3.11+, urllib.request, BeautifulSoup4, Pydantic, Pytest, Ruff.

---

## File Structure

- Modify: `pyproject.toml` - add `beautifulsoup4` runtime dependency.
- Create: `src/insight_graph/tools/http_client.py` - URL validation, HTTP fetch, response decoding, and `FetchError`.
- Create: `src/insight_graph/tools/content_extract.py` - HTML title/body/snippet extraction.
- Create: `src/insight_graph/tools/fetch_url.py` - `fetch_url` tool that returns verified `Evidence`.
- Modify: `src/insight_graph/tools/registry.py` - register `fetch_url` beside `mock_search`.
- Create: `tests/test_content_extract.py` - content extraction unit tests.
- Create: `tests/test_fetch_url.py` - fetch URL tool tests using monkeypatch, no live network.
- Create: `tests/test_tools.py` - tool registry tests.

---

### Task 1: HTML Content Extraction

**Files:**
- Modify: `pyproject.toml`
- Create: `src/insight_graph/tools/content_extract.py`
- Create: `tests/test_content_extract.py`

- [ ] **Step 1: Add failing content extraction tests**

Create `tests/test_content_extract.py`:

```python
from insight_graph.tools.content_extract import extract_page_content


def test_extract_page_content_returns_title_text_and_snippet() -> None:
    html = """
    <html>
      <head><title>Example Product Page</title></head>
      <body>
        <main>
          <h1>Product Overview</h1>
          <p>Cursor helps developers write code with AI assistance.</p>
          <p>It supports editing, chat, and codebase-aware workflows.</p>
        </main>
      </body>
    </html>
    """

    content = extract_page_content(html, "https://example.com/product", snippet_chars=80)

    assert content.title == "Example Product Page"
    assert "Product Overview" in content.text
    assert "Cursor helps developers" in content.text
    assert len(content.snippet) <= 80
    assert content.snippet.startswith("Product Overview")


def test_extract_page_content_removes_non_content_tags() -> None:
    html = """
    <html>
      <head><title>Noise Removal</title><style>.hidden { display: none; }</style></head>
      <body>
        <nav>Navigation should not appear</nav>
        <script>window.secret = "do not include";</script>
        <main><p>Only this useful evidence should remain.</p></main>
        <footer>Footer should not appear</footer>
      </body>
    </html>
    """

    content = extract_page_content(html, "https://example.com/noise")

    assert "Only this useful evidence should remain." in content.text
    assert "Navigation should not appear" not in content.text
    assert "do not include" not in content.text
    assert "Footer should not appear" not in content.text


def test_extract_page_content_falls_back_to_domain_for_missing_title() -> None:
    html = "<html><body><main><p>Useful body text.</p></main></body></html>"

    content = extract_page_content(html, "https://docs.example.com/path")

    assert content.title == "docs.example.com"
    assert content.text == "Useful body text."
    assert content.snippet == "Useful body text."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_content_extract.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.tools.content_extract'`.

- [ ] **Step 3: Add BeautifulSoup dependency**

Modify `pyproject.toml` dependencies to include `beautifulsoup4>=4.12.0`:

```toml
dependencies = [
  "beautifulsoup4>=4.12.0",
  "langgraph>=0.2.0",
  "langchain-core>=0.3.0",
  "pydantic>=2.7.0",
  "typer>=0.12.0",
  "rich>=13.7.0",
]
```

- [ ] **Step 4: Install updated package dependencies**

Run: `python -m pip install -e ".[dev]"`

Expected: install succeeds and includes `beautifulsoup4`.

- [ ] **Step 5: Implement content extractor**

Create `src/insight_graph/tools/content_extract.py`:

```python
from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel


NON_CONTENT_TAGS = ("script", "style", "nav", "footer", "header", "noscript", "svg")


class ExtractedContent(BaseModel):
    title: str
    text: str
    snippet: str


def extract_page_content(html: str, url: str, snippet_chars: int = 300) -> ExtractedContent:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(NON_CONTENT_TAGS):
        tag.decompose()

    title = _extract_title(soup, url)
    text = _normalize_whitespace(soup.get_text(" "))
    snippet = text[:snippet_chars].strip()
    return ExtractedContent(title=title, text=text, snippet=snippet)


def _extract_title(soup: BeautifulSoup, url: str) -> str:
    if soup.title is not None and soup.title.string is not None:
        title = _normalize_whitespace(soup.title.string)
        if title:
            return title
    domain = urlparse(url).netloc.lower()
    return domain or url


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
```

- [ ] **Step 6: Run content extraction tests**

Run: `python -m pytest tests/test_content_extract.py -v`

Expected: 3 tests pass.

- [ ] **Step 7: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml src/insight_graph/tools/content_extract.py tests/test_content_extract.py
git commit -m "feat: add HTML content extraction"
```

---

### Task 2: HTTP Client

**Files:**
- Create: `src/insight_graph/tools/http_client.py`
- Create: `tests/test_http_client.py`

- [ ] **Step 1: Write failing HTTP client tests**

Create `tests/test_http_client.py`:

```python
import pytest

from insight_graph.tools.http_client import FetchError, fetch_text


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self._body = body
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_fetch_text_rejects_unsupported_scheme() -> None:
    with pytest.raises(FetchError, match="Unsupported URL scheme"):
        fetch_text("ftp://example.com/file")


def test_fetch_text_decodes_response(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        assert request.full_url == "https://example.com/page"
        assert timeout == 10.0
        return FakeResponse("Café".encode("utf-8"))

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    page = fetch_text("https://example.com/page")

    assert page.url == "https://example.com/page"
    assert page.status_code == 200
    assert page.content_type == "text/html; charset=utf-8"
    assert page.text == "Café"


def test_fetch_text_rejects_empty_body(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        return FakeResponse(b"")

    monkeypatch.setattr("insight_graph.tools.http_client.urlopen", fake_urlopen)

    with pytest.raises(FetchError, match="Empty response body"):
        fetch_text("https://example.com/empty")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_http_client.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.tools.http_client'`.

- [ ] **Step 3: Implement HTTP client**

Create `src/insight_graph/tools/http_client.py`:

```python
from __future__ import annotations

from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel


class FetchError(RuntimeError):
    pass


class FetchedPage(BaseModel):
    url: str
    status_code: int
    content_type: str
    text: str


def fetch_text(url: str, timeout: float = 10.0) -> FetchedPage:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise FetchError(f"Unsupported URL scheme: {parsed.scheme or 'missing'}")

    request = Request(url, headers={"User-Agent": "InsightGraph/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if status_code < 200 or status_code >= 300:
                raise FetchError(f"Unexpected HTTP status: {status_code}")
            body = response.read()
            if not body:
                raise FetchError("Empty response body")
            content_type = response.headers.get("Content-Type", "")
            encoding = _encoding_from_content_type(content_type)
            return FetchedPage(
                url=url,
                status_code=status_code,
                content_type=content_type,
                text=body.decode(encoding, errors="replace"),
            )
    except HTTPError as exc:
        raise FetchError(f"HTTP error while fetching URL: {exc.code}") from exc
    except URLError as exc:
        raise FetchError(f"Network error while fetching URL: {exc.reason}") from exc


def _encoding_from_content_type(content_type: str) -> str:
    for part in content_type.split(";"):
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            return value
    return "utf-8"
```

- [ ] **Step 4: Run HTTP client tests**

Run: `python -m pytest tests/test_http_client.py -v`

Expected: 3 tests pass.

- [ ] **Step 5: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/tools/http_client.py tests/test_http_client.py
git commit -m "feat: add HTTP fetch client"
```

---

### Task 3: Fetch URL Evidence Tool

**Files:**
- Create: `src/insight_graph/tools/fetch_url.py`
- Create: `tests/test_fetch_url.py`

- [ ] **Step 1: Write failing fetch URL tests**

Create `tests/test_fetch_url.py`:

```python
from insight_graph.tools.fetch_url import fetch_url, infer_source_type
from insight_graph.tools.http_client import FetchedPage


def test_fetch_url_returns_verified_evidence(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        assert url == "https://example.com/product"
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html; charset=utf-8",
            text="""
            <html>
              <head><title>Example Product</title></head>
              <body><main><p>Example product evidence text.</p></main></body>
            </html>
            """,
        )

    monkeypatch.setattr("insight_graph.tools.fetch_url.fetch_text", fake_fetch_text)

    evidence = fetch_url("https://example.com/product", "s1")

    assert len(evidence) == 1
    item = evidence[0]
    assert item.id == "example-com-product"
    assert item.subtask_id == "s1"
    assert item.title == "Example Product"
    assert item.source_url == "https://example.com/product"
    assert item.snippet == "Example product evidence text."
    assert item.source_type == "unknown"
    assert item.verified is True


def test_fetch_url_returns_empty_list_for_empty_snippet(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(url=url, status_code=200, content_type="text/html", text="<html></html>")

    monkeypatch.setattr("insight_graph.tools.fetch_url.fetch_text", fake_fetch_text)

    assert fetch_url("https://example.com/empty", "s1") == []


def test_infer_source_type_from_url() -> None:
    assert infer_source_type("https://github.com/sst/opencode") == "github"
    assert infer_source_type("https://docs.github.com/copilot") == "docs"
    assert infer_source_type("https://example.com/docs/product") == "docs"
    assert infer_source_type("https://example.com/product") == "unknown"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fetch_url.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'insight_graph.tools.fetch_url'`.

- [ ] **Step 3: Implement fetch URL tool**

Create `src/insight_graph/tools/fetch_url.py`:

```python
from __future__ import annotations

import re
from urllib.parse import urlparse

from insight_graph.state import Evidence, SourceType
from insight_graph.tools.content_extract import extract_page_content
from insight_graph.tools.http_client import fetch_text


def fetch_url(url: str, subtask_id: str = "collect") -> list[Evidence]:
    page = fetch_text(url)
    content = extract_page_content(page.text, page.url)
    if not content.snippet:
        return []
    return [
        Evidence(
            id=_evidence_id(page.url),
            subtask_id=subtask_id,
            title=content.title,
            source_url=page.url,
            snippet=content.snippet,
            source_type=infer_source_type(page.url),
            verified=True,
        )
    ]


def infer_source_type(url: str) -> SourceType:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    if domain == "github.com" or domain.endswith(".github.com"):
        return "github"
    if domain.startswith("docs.") or "/docs" in path:
        return "docs"
    return "unknown"


def _evidence_id(url: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}".strip("/") or url
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return slug or "fetched-url"
```

- [ ] **Step 4: Run fetch URL tests**

Run: `python -m pytest tests/test_fetch_url.py -v`

Expected: 3 tests pass.

- [ ] **Step 5: Run lint**

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/tools/fetch_url.py tests/test_fetch_url.py
git commit -m "feat: add URL evidence tool"
```

---

### Task 4: Register Fetch URL Tool

**Files:**
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Create: `tests/test_tools.py`

- [ ] **Step 1: Write failing registry tests**

Create `tests/test_tools.py`:

```python
import pytest

from insight_graph.tools import ToolRegistry
from insight_graph.tools.http_client import FetchedPage


def test_registry_runs_fetch_url_tool(monkeypatch) -> None:
    def fake_fetch_text(url: str):
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html",
            text="<html><head><title>Tool Page</title></head><body><p>Tool evidence.</p></body></html>",
        )

    monkeypatch.setattr("insight_graph.tools.fetch_url.fetch_text", fake_fetch_text)

    evidence = ToolRegistry().run("fetch_url", "https://example.com/tool", "s1")

    assert len(evidence) == 1
    assert evidence[0].title == "Tool Page"
    assert evidence[0].verified is True


def test_registry_unknown_tool_still_raises_key_error() -> None:
    with pytest.raises(KeyError, match="Unknown tool"):
        ToolRegistry().run("missing_tool", "query", "s1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tools.py -v`

Expected: FAIL because `ToolRegistry` does not know `fetch_url`.

- [ ] **Step 3: Register fetch URL tool**

Modify `src/insight_graph/tools/registry.py`:

```python
from collections.abc import Callable

from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.mock_search import mock_search

ToolFn = Callable[[str, str], list[Evidence]]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolFn] = {"mock_search": mock_search, "fetch_url": fetch_url}

    def run(self, name: str, query: str, subtask_id: str) -> list[Evidence]:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name](query, subtask_id)
```

Modify `src/insight_graph/tools/__init__.py`:

```python
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.registry import ToolRegistry

__all__ = ["ToolRegistry", "fetch_url"]
```

- [ ] **Step 4: Run registry tests**

Run: `python -m pytest tests/test_tools.py -v`

Expected: 2 tests pass.

- [ ] **Step 5: Run full test suite and lint**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/insight_graph/tools/registry.py src/insight_graph/tools/__init__.py tests/test_tools.py
git commit -m "feat: register URL evidence tool"
```

---

### Task 5: Documentation And Final Verification

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-04-25-evidence-acquisition-design.md`
- Create: `docs/superpowers/plans/2026-04-25-evidence-acquisition.md`

- [ ] **Step 1: Update README current MVP section**

In `README.md`, update the current MVP capability table row for evidence chain from:

```markdown
| 证据链 | 已实现 deterministic `mock_search`，所有报告引用仅来自 verified evidence |
```

to:

```markdown
| 证据链 | 已实现 deterministic `mock_search` 和 direct URL `fetch_url`；报告引用仅来自 verified evidence |
```

Update the note below that table from:

```markdown
> MVP 阶段的 Collector 使用固定 mock evidence，适合验证架构闭环；它不会根据任意查询实时联网搜索。真实 web/news/GitHub 搜索、FastAPI、PostgreSQL、pgvector、LLM 路由和可观测性属于后续路线图。
```

to:

```markdown
> MVP 阶段默认 CLI 仍使用固定 mock evidence，适合验证架构闭环；工具层已支持 direct URL 抓取和 HTML evidence 提取。真实 web/news/GitHub 搜索、FastAPI、PostgreSQL、pgvector、LLM 路由和可观测性属于后续路线图。
```

- [ ] **Step 2: Run final verification**

Run: `python -m pytest -v`

Expected: all tests pass.

Run: `python -m ruff check .`

Expected: no lint errors.

Run: `python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"`

Expected: output includes `# InsightGraph Research Report`, `## Key Findings`, and `## References`.

- [ ] **Step 3: Commit docs and plan/spec**

```bash
git add README.md docs/superpowers/specs/2026-04-25-evidence-acquisition-design.md docs/superpowers/plans/2026-04-25-evidence-acquisition.md
git commit -m "docs: add evidence acquisition plan"
```

- [ ] **Step 4: Push if requested by user**

Do not push automatically. Ask the user whether to push after final verification.

---

## Self-Review

- Spec coverage: The plan implements direct URL fetching, HTML extraction, verified Evidence conversion, ToolRegistry registration, no live-network tests, and no default CLI/Planner behavior change.
- Deferred scope: Search APIs, Playwright, PDF extraction, LLM relevance, URL revalidation, FastAPI, PostgreSQL, and pgvector are explicitly excluded.
- Placeholder scan: No placeholders remain; every task includes file paths, code, commands, and expected results.
- Type consistency: The plan consistently uses `FetchedPage`, `FetchError`, `ExtractedContent`, `fetch_text`, `extract_page_content`, `fetch_url`, `infer_source_type`, `Evidence`, and `ToolRegistry`.
