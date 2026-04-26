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


def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]:
    parsed_query = _parse_document_reader_query(query)
    if parsed_query is None:
        return []

    root = Path.cwd().resolve()
    path = _resolve_inside_root(root, parsed_query.path)
    if path is None or not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return []

    try:
        text = _read_document_text(path)
    except (OSError, UnicodeDecodeError, PdfReadError):
        return []

    normalized_text = _normalize_snippet(_extract_text(text, path.suffix.lower()))
    snippets = _select_snippets(normalized_text, parsed_query.retrieval_query)
    if not snippets:
        return []

    return [
        _build_evidence(root, path, subtask_id, snippet, index)
        for snippet, index in snippets
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


def _read_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_SUFFIXES:
        return _read_pdf_text(path)
    return path.read_text(encoding="utf-8")


def _select_snippets(text: str, retrieval_query: str | None) -> list[tuple[str, int]]:
    candidates = _chunk_snippets(text)
    if not retrieval_query:
        return candidates[:MAX_DOCUMENT_EVIDENCE]
    ranked = _rank_snippets(candidates, retrieval_query)
    return ranked[:MAX_DOCUMENT_EVIDENCE] if ranked else candidates[:MAX_DOCUMENT_EVIDENCE]


def _chunk_snippets(text: str) -> list[tuple[str, int]]:
    if not text:
        return []
    if len(text) <= MAX_SNIPPET_CHARS:
        return [(text, 0)]
    step = MAX_SNIPPET_CHARS - SNIPPET_OVERLAP_CHARS
    return [
        (text[start : start + MAX_SNIPPET_CHARS], index)
        for index, start in enumerate(range(0, len(text), step))
        if text[start : start + MAX_SNIPPET_CHARS]
    ]


def _rank_snippets(
    candidates: list[tuple[str, int]],
    retrieval_query: str,
) -> list[tuple[str, int]]:
    query_tokens = set(_tokenize(retrieval_query))
    if not query_tokens:
        return []

    scored = []
    for snippet, index in candidates:
        tokens = _tokenize(snippet)
        score = sum(1 for token in tokens if token in query_tokens)
        distinct_matches = len({token for token in tokens if token in query_tokens})
        if score > 0:
            scored.append((score, distinct_matches, -index, snippet, index))

    scored.sort(reverse=True)
    return [(snippet, index) for _, _, _, snippet, index in scored]


def _tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 3]


def _build_evidence(
    root: Path,
    path: Path,
    subtask_id: str,
    snippet: str,
    index: int,
) -> Evidence:
    base_id = _evidence_id(root, path)
    chunk_number = index + 1
    return Evidence(
        id=base_id if index == 0 else f"{base_id}-chunk-{chunk_number}",
        subtask_id=subtask_id,
        title=path.name if index == 0 else f"{path.name} (chunk {chunk_number})",
        source_url=path.as_uri(),
        snippet=snippet,
        source_type="docs",
        verified=True,
    )


def _read_pdf_text(path: Path) -> str:
    logger = logging.getLogger("pypdf")
    previous_level = logger.level
    logger.setLevel(logging.CRITICAL + 1)
    try:
        with path.open("rb") as handle:
            reader = PdfReader(handle)
            if reader.is_encrypted:
                return ""
            return "\n".join(page.extract_text() or "" for page in reader.pages)
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


def _evidence_id(root: Path, path: Path) -> str:
    relative_path = path.relative_to(root)
    relative_path_text = relative_path.as_posix()
    digest = hashlib.sha1(relative_path_text.encode("utf-8")).hexdigest()[:8]
    return f"document-{_slugify(relative_path_text)}-{digest}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "document"
