import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from insight_graph.state import Evidence

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm", ".pdf"}
HTML_SUFFIXES = {".html", ".htm"}
PDF_SUFFIXES = {".pdf"}
MAX_SNIPPET_CHARS = 500
SNIPPET_OVERLAP_CHARS = 100
MAX_DOCUMENT_EVIDENCE = 5


@dataclass(frozen=True)
class DocumentReaderQuery:
    path: str
    retrieval_query: str | None = None


@dataclass(frozen=True)
class DocumentText:
    text: str
    page_starts: list[tuple[int, int]]


@dataclass(frozen=True)
class DocumentChunk:
    snippet: str
    index: int
    page: int | None = None
    section_heading: str | None = None


def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]:
    parsed_query = _parse_document_reader_query(query)
    if parsed_query is None:
        return []

    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, parsed_query.path)
    if path is None or not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return []

    try:
        document_text = _read_document_text(path)
    except (OSError, UnicodeDecodeError, PdfReadError):
        return []

    normalized_text = _normalize_snippet(
        _extract_text(document_text.text, path.suffix.lower())
    )
    snippets = _select_snippets(
        normalized_text,
        parsed_query.retrieval_query,
        page_starts=document_text.page_starts,
        section_headings=_extract_section_headings(document_text.text, normalized_text),
    )
    if not snippets:
        return []

    return [
        _build_evidence(root, path, subtask_id, chunk)
        for chunk in snippets
    ]


def _parse_document_reader_query(query: str) -> DocumentReaderQuery | None:
    try:
        parsed = json.loads(query)
    except json.JSONDecodeError:
        return DocumentReaderQuery(path=query)
    if not isinstance(parsed, dict):
        return DocumentReaderQuery(path=query)

    path = parsed.get("path")
    if not isinstance(path, str) or not path.strip():
        return None

    retrieval_query = parsed.get("query")
    if not isinstance(retrieval_query, str) or not retrieval_query.strip():
        retrieval_query = None
    return DocumentReaderQuery(
        path=path.strip(),
        retrieval_query=retrieval_query.strip() if retrieval_query else None,
    )


def _read_document_text(path: Path) -> DocumentText:
    suffix = path.suffix.lower()
    if suffix in PDF_SUFFIXES:
        return _read_pdf_text(path)
    return DocumentText(text=path.read_text(encoding="utf-8"), page_starts=[])


def _select_snippets(
    text: str,
    retrieval_query: str | None,
    *,
    page_starts: list[tuple[int, int]],
    section_headings: list[tuple[int, str]],
) -> list[DocumentChunk]:
    candidates = _chunk_snippets(text, page_starts, section_headings)
    if not retrieval_query:
        return candidates[:MAX_DOCUMENT_EVIDENCE]
    ranked = _rank_snippets(candidates, retrieval_query)
    return ranked[:MAX_DOCUMENT_EVIDENCE] if ranked else candidates[:MAX_DOCUMENT_EVIDENCE]


def _chunk_snippets(
    text: str,
    page_starts: list[tuple[int, int]],
    section_headings: list[tuple[int, str]],
) -> list[DocumentChunk]:
    if not text:
        return []
    if len(text) <= MAX_SNIPPET_CHARS:
        return [
            DocumentChunk(
                snippet=text,
                index=0,
                page=_page_for_start(0, page_starts),
                section_heading=_section_for_start(0, section_headings),
            )
        ]
    step = MAX_SNIPPET_CHARS - SNIPPET_OVERLAP_CHARS
    return [
        DocumentChunk(
            snippet=text[start : start + MAX_SNIPPET_CHARS],
            index=index,
            page=_page_for_start(start, page_starts),
            section_heading=_section_for_start(start, section_headings),
        )
        for index, start in enumerate(range(0, len(text), step))
        if text[start : start + MAX_SNIPPET_CHARS]
    ]


def _rank_snippets(
    candidates: list[DocumentChunk],
    retrieval_query: str,
) -> list[DocumentChunk]:
    query_tokens = set(_tokenize(retrieval_query))
    if not query_tokens:
        return []

    scored = []
    for chunk in candidates:
        tokens = _tokenize(chunk.snippet)
        score = sum(1 for token in tokens if token in query_tokens)
        distinct_matches = len({token for token in tokens if token in query_tokens})
        if score > 0:
            scored.append((score, distinct_matches, -chunk.index, chunk))

    scored.sort(reverse=True)
    return [chunk for _, _, _, chunk in scored]


def _tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 3]


def _build_evidence(
    root: Path,
    path: Path,
    subtask_id: str,
    chunk: DocumentChunk,
) -> Evidence:
    base_id = _evidence_id(root, path)
    index = chunk.index
    chunk_number = index + 1
    return Evidence(
        id=base_id if index == 0 else f"{base_id}-chunk-{chunk_number}",
        subtask_id=subtask_id,
        title=path.name if index == 0 else f"{path.name} (chunk {chunk_number})",
        source_url=path.as_uri(),
        snippet=chunk.snippet,
        source_type="docs",
        verified=True,
        chunk_index=chunk_number,
        document_page=chunk.page,
        section_heading=chunk.section_heading,
    )


def _read_pdf_text(path: Path) -> DocumentText:
    logger = logging.getLogger("pypdf")
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    try:
        with path.open("rb") as handle:
            reader = PdfReader(handle)
            if reader.is_encrypted:
                return DocumentText(text="", page_starts=[])
            parts: list[str] = []
            page_starts: list[tuple[int, int]] = []
            offset = 0
            for page_number, page in enumerate(reader.pages, start=1):
                page_text = page.extract_text() or ""
                if page_text:
                    page_starts.append((offset, page_number))
                parts.append(page_text)
                offset += len(page_text) + 1
            return DocumentText(text="\n".join(parts), page_starts=page_starts)
    finally:
        logger.setLevel(previous_level)


def _extract_text(text: str, suffix: str) -> str:
    if suffix not in HTML_SUFFIXES:
        return text
    soup = BeautifulSoup(text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    body = soup.body or soup
    return body.get_text(" ")


def _resolve_inside_root(root: Path, query: str) -> Path | None:
    try:
        candidate = Path(query)
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve()
    except OSError:
        return None

    if not candidate.is_relative_to(root):
        return None
    return candidate


def _normalize_snippet(text: str) -> str:
    return " ".join(text.split())


def _extract_section_headings(
    raw_text: str,
    normalized_text: str,
) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    search_start = 0
    for line in raw_text.splitlines():
        match = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if match is None:
            continue
        marker = _normalize_snippet(line)
        position = normalized_text.find(marker, search_start)
        if position == -1:
            continue
        headings.append((position, match.group(1).strip()))
        search_start = position + len(marker)
    return headings


def _page_for_start(start: int, page_starts: list[tuple[int, int]]) -> int | None:
    page = None
    for page_start, page_number in page_starts:
        if page_start > start:
            break
        page = page_number
    return page


def _section_for_start(start: int, headings: list[tuple[int, str]]) -> str | None:
    section = None
    for heading_start, heading in headings:
        if heading_start > start:
            break
        section = heading
    return section


def _evidence_id(root: Path, path: Path) -> str:
    relative_path = path.relative_to(root)
    relative_path_text = relative_path.as_posix()
    digest = hashlib.sha1(relative_path_text.encode("utf-8")).hexdigest()[:8]
    return f"document-{_slugify(relative_path_text)}-{digest}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "document"
