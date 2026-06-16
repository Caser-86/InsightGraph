import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from bs4 import BeautifulSoup
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from insight_graph.report_quality.document_index import (
    DocumentIndexChunk,
    DocumentVectorIndex,
    IndexedDocumentChunk,
    get_document_index_path,
    rank_document_chunks,
)
from insight_graph.state import Evidence

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm", ".pdf"}
HTML_SUFFIXES = {".html", ".htm"}
PDF_SUFFIXES = {".pdf"}
MAX_SNIPPET_CHARS = 500
SNIPPET_OVERLAP_CHARS = 100
MAX_DOCUMENT_EVIDENCE = 5
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DocumentReaderQuery:
    path: str
    retrieval_query: str | None = None


@dataclass(frozen=True)
class DocumentText:
    text: str
    page_starts: list[tuple[int, int]]
    section_headings: list[tuple[int, str]] | None = None


@dataclass(frozen=True)
class DocumentChunk:
    snippet: str
    index: int
    page: int | None = None
    section_heading: str | None = None
    start: int = 0
    end: int = 0


def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]:
    parsed_query = _parse_document_reader_query(query)
    if parsed_query is None:
        return []

    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, parsed_query.path)
    if path is None or not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return []

    index_path = _usable_document_index_path(path)
    if index_path is not None:
        try:
            index = DocumentVectorIndex.load(index_path)
            fresh_chunks = index.get_fresh_chunks(path)
        except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
            LOGGER.debug("Falling back after document index read failed: %s", error)
            return _read_evidence(root, path, parsed_query, subtask_id)

        if fresh_chunks:
            snippets = _select_chunks(
                _document_chunks_from_index(fresh_chunks),
                parsed_query.retrieval_query,
            )
            return [
                _build_evidence(root, path, subtask_id, chunk)
                for chunk in snippets
            ]

        chunks = _read_document_chunks(path)
        if not chunks:
            return []
        try:
            index.store_document(path, _document_index_chunks(chunks))
            index.save()
        except (OSError, ValueError, TypeError) as error:
            LOGGER.warning(
                "Document index write failed; using in-memory chunks: %s",
                error,
            )
        snippets = _select_chunks(chunks, parsed_query.retrieval_query)
        return [
            _build_evidence(root, path, subtask_id, chunk)
            for chunk in snippets
        ]

    return _read_evidence(root, path, parsed_query, subtask_id)


def _read_evidence(
    root: Path,
    path: Path,
    parsed_query: DocumentReaderQuery,
    subtask_id: str,
) -> list[Evidence]:
    chunks = _read_document_chunks(path)
    if not chunks:
        return []
    snippets = _select_chunks(chunks, parsed_query.retrieval_query)
    if not snippets:
        return []

    return [
        _build_evidence(root, path, subtask_id, chunk)
        for chunk in snippets
    ]


def _read_document_chunks(path: Path) -> list[DocumentChunk]:
    try:
        document_text = _read_document_text(path)
    except (OSError, UnicodeDecodeError, PdfReadError):
        return []

    extracted_text = _extract_text(document_text.text, path.suffix.lower())
    normalized_text = _normalize_snippet(extracted_text)
    return _chunk_snippets(
        normalized_text,
        _normalize_page_starts(extracted_text, document_text.page_starts),
        _normalize_section_starts(
            extracted_text,
            document_text.section_headings or [],
        )
        + _extract_section_headings(document_text.text, normalized_text),
    )


def _usable_document_index_path(document_path: Path) -> Path | None:
    index_path = get_document_index_path()
    if index_path is None:
        return None
    try:
        resolved_index_path = index_path.resolve()
        resolved_document_path = document_path.resolve()
    except OSError as error:
        LOGGER.debug("Ignoring document index path that could not resolve: %s", error)
        return None
    if resolved_index_path == resolved_document_path:
        LOGGER.warning(
            "Ignoring document index path because it matches the document path"
        )
        return None
    if not resolved_index_path.exists():
        return resolved_index_path
    if _has_document_index_schema(resolved_index_path):
        return resolved_index_path
    LOGGER.warning("Ignoring existing file without document index schema")
    return None


def _has_document_index_schema(index_path: Path) -> bool:
    try:
        payload = json.loads(index_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return False
    except json.JSONDecodeError:
        return False
    return (
        isinstance(payload, dict)
        and payload.get("version") == 1
        and isinstance(payload.get("documents"), dict)
    )


def _normalize_page_starts(
    text: str,
    page_starts: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    return [
        (len(_normalize_snippet(text[:start])), page_number)
        for start, page_number in page_starts
    ]


def _normalize_section_starts(
    text: str,
    section_starts: list[tuple[int, str]],
) -> list[tuple[int, str]]:
    return [
        (len(_normalize_snippet(text[:start])), heading)
        for start, heading in section_starts
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
    return _select_chunks(candidates, retrieval_query)


def _select_chunks(
    candidates: list[DocumentChunk],
    retrieval_query: str | None,
) -> list[DocumentChunk]:
    if not retrieval_query:
        return candidates[:MAX_DOCUMENT_EVIDENCE]
    ranked = _rank_snippets(candidates, retrieval_query)
    return ranked[:MAX_DOCUMENT_EVIDENCE] if ranked else candidates[:MAX_DOCUMENT_EVIDENCE]


def _document_chunks_from_index(
    chunks: list[IndexedDocumentChunk],
) -> list[DocumentChunk]:
    return [
        DocumentChunk(
            snippet=chunk.text,
            index=chunk.index,
            page=chunk.page,
            section_heading=chunk.section_heading,
            start=0,
            end=len(chunk.text),
        )
        for chunk in chunks
    ]


def _document_index_chunks(chunks: list[DocumentChunk]) -> list[DocumentIndexChunk]:
    return [
        DocumentIndexChunk(
            text=chunk.snippet,
            index=chunk.index,
            page=chunk.page,
            section_heading=chunk.section_heading,
        )
        for chunk in chunks
    ]


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
                start=0,
                end=len(text),
            )
        ]
    step = MAX_SNIPPET_CHARS - SNIPPET_OVERLAP_CHARS
    return [
        DocumentChunk(
            snippet=text[start : start + MAX_SNIPPET_CHARS],
            index=index,
            page=_page_for_start(start, page_starts),
            section_heading=_section_for_start(start, section_headings),
            start=start,
            end=start + len(text[start : start + MAX_SNIPPET_CHARS]),
        )
        for index, start in enumerate(range(0, len(text), step))
        if text[start : start + MAX_SNIPPET_CHARS]
    ]


def _rank_snippets(
    candidates: list[DocumentChunk],
    retrieval_query: str,
) -> list[DocumentChunk]:
    indexed_chunks = [
        DocumentIndexChunk(
            text=chunk.snippet,
            index=chunk.index,
            page=chunk.page,
            section_heading=chunk.section_heading,
        )
        for chunk in candidates
    ]
    ranked = rank_document_chunks(indexed_chunks, retrieval_query)
    chunks_by_index = {chunk.index: chunk for chunk in candidates}
    return [chunks_by_index[chunk.index] for chunk in ranked]


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
        snippet_start=chunk.start,
        snippet_end=chunk.end,
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
            return DocumentText(
                text="\n".join(parts),
                page_starts=page_starts,
                section_headings=_extract_pdf_outline_headings(reader, page_starts),
            )
    finally:
        logger.setLevel(previous_level)


def _extract_pdf_outline_headings(
    reader: PdfReader,
    page_starts: list[tuple[int, int]],
) -> list[tuple[int, str]]:
    page_offsets = {page_number: offset for offset, page_number in page_starts}
    headings: list[tuple[int, str]] = []
    for destination in _iter_pdf_outline_destinations(getattr(reader, "outline", [])):
        title = getattr(destination, "title", None)
        if not isinstance(title, str) or not title.strip():
            continue
        try:
            page_number = reader.get_destination_page_number(destination) + 1
        except (AttributeError, KeyError, ValueError, TypeError):
            continue
        offset = page_offsets.get(page_number)
        if offset is None:
            continue
        headings.append((offset, title.strip()))
    return sorted(headings)


def _iter_pdf_outline_destinations(outline):
    if isinstance(outline, list):
        for item in outline:
            yield from _iter_pdf_outline_destinations(item)
        return
    if isinstance(outline, tuple):
        for item in outline:
            yield from _iter_pdf_outline_destinations(item)
        return
    yield outline


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
