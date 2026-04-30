from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from insight_graph.report_quality.source_types import infer_source_type
from insight_graph.state import Evidence, SourceType
from insight_graph.tools.content_extract import extract_page_content
from insight_graph.tools.fetch_cache import (
    FetchCacheEntry,
    load_cached_fetch,
    store_cached_fetch,
)
from insight_graph.tools.http_client import FetchedPage, FetchError, fetch_text
from insight_graph.tools.rendered_fetch import render_page

MAX_FETCHED_EVIDENCE = 5
MAX_SNIPPET_CHARS = 500
SNIPPET_OVERLAP_CHARS = 100
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


@dataclass(frozen=True)
class FetchedChunk:
    snippet: str
    start: int
    page: int | None = None


@dataclass(frozen=True)
class FetchUrlQuery:
    url: str
    retrieval_query: str | None = None


def fetch_url(url: str, subtask_id: str = "collect") -> list[Evidence]:
    parsed_query = _parse_fetch_url_query(url)
    page = _fetch_page(parsed_query.url)
    if _is_pdf_response(page.content_type, page.url):
        return _pdf_evidence(page, subtask_id, parsed_query.retrieval_query)

    content = extract_page_content(page.text, page.url)
    if not content.text:
        return []
    chunks = _chunk_text(content.text)
    headings = _extract_html_section_headings(page.text, content.text)
    chunks = _rank_chunks(chunks, parsed_query.retrieval_query, headings)
    source_type = infer_source_type(page.url)
    base_id = _evidence_id(page.url)
    return [
        Evidence(
            id=base_id if index == 0 else f"{base_id}-chunk-{index + 1}",
            subtask_id=subtask_id,
            title=content.title if index == 0 else f"{content.title} (chunk {index + 1})",
            source_url=page.url,
            snippet=chunk.snippet,
            source_type=source_type,
            verified=True,
            reachable=True,
            source_trusted=_source_type_is_trusted(source_type),
            claim_supported=None,
            chunk_index=index + 1,
            section_heading=_section_for_start(chunk.start, headings),
        )
        for index, chunk in enumerate(chunks[:MAX_FETCHED_EVIDENCE])
    ]


def _fetch_page(url: str) -> FetchedPage:
    cached = load_cached_fetch(url)
    if cached is not None:
        return FetchedPage(
            url=cached.url,
            status_code=cached.status_code,
            content_type=cached.content_type,
            text=cached.body.decode("utf-8", errors="replace"),
            body=cached.body,
        )
    if _is_truthy_env("INSIGHT_GRAPH_FETCH_RENDERED"):
        try:
            return render_page(url)
        except FetchError:
            pass
    page = fetch_text(url)
    if page.body is not None:
        store_cached_fetch(
            FetchCacheEntry(
                url=page.url,
                status_code=page.status_code,
                content_type=page.content_type,
                body=page.body,
            )
        )
    return page


def _is_truthy_env(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}


def _parse_fetch_url_query(query: str) -> FetchUrlQuery:
    try:
        parsed = json.loads(query)
    except json.JSONDecodeError:
        return FetchUrlQuery(url=query)
    if not isinstance(parsed, dict):
        return FetchUrlQuery(url=query)
    url = parsed.get("url")
    if not isinstance(url, str) or not url.strip():
        return FetchUrlQuery(url=query)
    retrieval_query = parsed.get("query")
    if not isinstance(retrieval_query, str) or not retrieval_query.strip():
        retrieval_query = None
    return FetchUrlQuery(url=url.strip(), retrieval_query=retrieval_query)


def _evidence_id(url: str) -> str:
    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}".strip("/") or url
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower()
    return slug or "fetched-url"


def _pdf_evidence(
    page,
    subtask_id: str,
    retrieval_query: str | None = None,
) -> list[Evidence]:
    document = _extract_pdf_text(page.body)
    if document is None or not document[0]:
        return []
    text, page_starts = document
    chunks = _rank_chunks(
        _chunk_text(text, page_starts=page_starts),
        retrieval_query,
        headings=[],
    )
    base_id = _evidence_id(page.url)
    title = _pdf_title(page.url)
    return [
        Evidence(
            id=base_id if index == 0 else f"{base_id}-chunk-{index + 1}",
            subtask_id=subtask_id,
            title=title if index == 0 else f"{title} (chunk {index + 1})",
            source_url=page.url,
            snippet=chunk.snippet,
            source_type="docs",
            verified=True,
            reachable=True,
            source_trusted=True,
            claim_supported=None,
            chunk_index=index + 1,
            document_page=chunk.page,
        )
        for index, chunk in enumerate(chunks[:MAX_FETCHED_EVIDENCE])
    ]


def _extract_pdf_text(body: bytes | None) -> tuple[str, list[tuple[int, int]]] | None:
    if not body:
        return None
    logger = logging.getLogger("pypdf")
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    try:
        try:
            reader = PdfReader(BytesIO(body))
        except PdfReadError:
            return None
        if reader.is_encrypted:
            return None
        parts: list[str] = []
        page_starts: list[tuple[int, int]] = []
        offset = 0
        for page_number, pdf_page in enumerate(reader.pages, start=1):
            page_text = pdf_page.extract_text() or ""
            if page_text:
                page_starts.append((offset, page_number))
            parts.append(page_text)
            offset += len(page_text) + 1
        return _normalize_whitespace("\n".join(parts)), page_starts
    finally:
        logger.setLevel(previous_level)


def _is_pdf_response(content_type: str, url: str) -> bool:
    media_type = content_type.split(";", maxsplit=1)[0].strip().lower()
    return media_type in PDF_CONTENT_TYPES or urlparse(url).path.lower().endswith(".pdf")


def _source_type_is_trusted(source_type: SourceType) -> bool:
    return source_type in {"official_site", "docs", "github", "news", "sec", "paper"}


def _pdf_title(url: str) -> str:
    path_name = PurePosixPath(urlparse(url).path).name
    return path_name or urlparse(url).netloc.lower() or url


def _chunk_text(
    text: str,
    *,
    page_starts: list[tuple[int, int]] | None = None,
) -> list[FetchedChunk]:
    if len(text) <= MAX_SNIPPET_CHARS:
        return [FetchedChunk(text, 0, _page_for_start(0, page_starts or []))]
    step = MAX_SNIPPET_CHARS - SNIPPET_OVERLAP_CHARS
    return [
        FetchedChunk(
            text[start : start + MAX_SNIPPET_CHARS],
            start,
            _page_for_start(start, page_starts or []),
        )
        for start in range(0, len(text), step)
        if text[start : start + MAX_SNIPPET_CHARS]
    ]


def _rank_chunks(
    chunks: list[FetchedChunk],
    retrieval_query: str | None,
    headings: list[tuple[int, str]],
) -> list[FetchedChunk]:
    if not retrieval_query:
        return chunks
    query_tokens = set(_tokenize(retrieval_query))
    if not query_tokens:
        return chunks
    scored = []
    for index, chunk in enumerate(chunks):
        tokens = _tokenize(chunk.snippet)
        heading_tokens = _tokenize(_section_for_start(chunk.start, headings) or "")
        score = sum(1 for token in tokens if token in query_tokens)
        score += 100 * sum(1 for token in heading_tokens if token in query_tokens)
        distinct_matches = len({token for token in tokens if token in query_tokens})
        distinct_matches += len({token for token in heading_tokens if token in query_tokens})
        if score > 0:
            scored.append((score, distinct_matches, -index, chunk))
    if not scored:
        return chunks
    scored.sort(reverse=True)
    return [chunk for _, _, _, chunk in scored]


def _tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 3]


def _page_for_start(start: int, page_starts: list[tuple[int, int]]) -> int | None:
    page = None
    for page_start, page_number in page_starts:
        if page_start > start:
            break
        page = page_number
    return page


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
