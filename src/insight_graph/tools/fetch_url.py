from __future__ import annotations

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from insight_graph.state import Evidence, SourceType
from insight_graph.tools.content_extract import extract_page_content
from insight_graph.tools.http_client import fetch_text

MAX_FETCHED_EVIDENCE = 5
MAX_SNIPPET_CHARS = 500
SNIPPET_OVERLAP_CHARS = 100


def fetch_url(url: str, subtask_id: str = "collect") -> list[Evidence]:
    page = fetch_text(url)
    content = extract_page_content(page.text, page.url)
    if not content.text:
        return []
    chunks = _chunk_text(content.text)
    headings = _extract_html_section_headings(page.text, content.text)
    source_type = infer_source_type(page.url)
    base_id = _evidence_id(page.url)
    return [
        Evidence(
            id=base_id if index == 0 else f"{base_id}-chunk-{index + 1}",
            subtask_id=subtask_id,
            title=content.title if index == 0 else f"{content.title} (chunk {index + 1})",
            source_url=page.url,
            snippet=snippet,
            source_type=source_type,
            verified=True,
            chunk_index=index + 1,
            section_heading=_section_for_start(start, headings),
        )
        for index, (snippet, start) in enumerate(chunks[:MAX_FETCHED_EVIDENCE])
    ]


def infer_source_type(url: str) -> SourceType:
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    if domain.startswith("docs.") or "/docs" in path:
        return "docs"
    if domain == "github.com" or domain.endswith(".github.com"):
        return "github"
    return "unknown"


def _evidence_id(url: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}".strip("/") or url
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return slug or "fetched-url"


def _chunk_text(text: str) -> list[tuple[str, int]]:
    if len(text) <= MAX_SNIPPET_CHARS:
        return [(text, 0)]
    step = MAX_SNIPPET_CHARS - SNIPPET_OVERLAP_CHARS
    return [
        (text[start : start + MAX_SNIPPET_CHARS], start)
        for start in range(0, len(text), step)
        if text[start : start + MAX_SNIPPET_CHARS]
    ]


def _extract_html_section_headings(html: str, normalized_text: str) -> list[tuple[int, str]]:
    soup = BeautifulSoup(html, "html.parser")
    headings: list[tuple[int, str]] = []
    search_start = 0
    for tag in soup.find_all(re.compile(r"^h[1-6]$")):
        heading = _normalize_whitespace(tag.get_text(" "))
        if not heading:
            continue
        position = normalized_text.find(heading, search_start)
        if position == -1:
            continue
        headings.append((position, heading))
        search_start = position + len(heading)
    return headings


def _section_for_start(start: int, headings: list[tuple[int, str]]) -> str | None:
    section = None
    for heading_start, heading in headings:
        if heading_start > start:
            break
        section = heading
    return section


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())
