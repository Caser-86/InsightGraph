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
