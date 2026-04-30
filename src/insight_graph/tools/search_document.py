import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from insight_graph.report_quality.document_index import (
    DocumentIndexChunk,
    DocumentVectorIndex,
    rank_document_chunks,
)
from insight_graph.state import Evidence
from insight_graph.tools.document_reader import (
    MAX_DOCUMENT_EVIDENCE,
    SUPPORTED_SUFFIXES,
    DocumentChunk,
    _build_evidence,
    _document_chunks_from_index,
    _document_index_chunks,
    _read_document_chunks,
    _resolve_inside_root,
    _usable_document_index_path,
)

SearchDocumentMode = Literal["deterministic", "vector"]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchDocumentQuery:
    path: str
    paths: tuple[str, ...] = ()
    query: str | None = None
    limit: int = MAX_DOCUMENT_EVIDENCE
    mode: SearchDocumentMode | None = None
    page: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    section: str | None = None


def search_document(query: str, subtask_id: str = "collect") -> list[Evidence]:
    parsed_query = _parse_search_document_query(query)
    if parsed_query is None:
        return []

    root = Path.cwd().resolve()
    document_chunks = _load_search_documents(root, parsed_query)
    candidates: list[tuple[Path, DocumentChunk]] = []
    for path, chunks in document_chunks:
        for chunk in _filter_chunks(chunks, parsed_query):
            candidates.append((path, chunk))
    if not candidates:
        return []

    selected_chunks = _select_document_chunks(candidates, parsed_query)
    return [
        _build_evidence(root, path, subtask_id, chunk)
        for path, chunk in selected_chunks
    ]


def _parse_search_document_query(query: str) -> SearchDocumentQuery | None:
    try:
        parsed = json.loads(query)
    except json.JSONDecodeError:
        return SearchDocumentQuery(path=query)

    if not isinstance(parsed, dict):
        return None

    path = parsed.get("path")
    paths = parsed.get("paths")
    parsed_paths: tuple[str, ...] = ()
    if isinstance(paths, list):
        parsed_paths = tuple(
            item.strip() for item in paths if isinstance(item, str) and item.strip()
        )
    if parsed_paths:
        path = parsed_paths[0]
    if not isinstance(path, str) or not path.strip():
        return None

    retrieval_query = parsed.get("query")
    if not isinstance(retrieval_query, str) or not retrieval_query.strip():
        retrieval_query = None

    limit = parsed.get("limit", MAX_DOCUMENT_EVIDENCE)
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        limit = MAX_DOCUMENT_EVIDENCE

    mode = parsed.get("mode")
    if mode not in {"deterministic", "vector"}:
        mode = None

    page = parsed.get("page")
    if page is not None and (
        not isinstance(page, int) or isinstance(page, bool) or page < 1
    ):
        page = None

    page_start = _parse_positive_int(parsed.get("page_start"))
    page_end = _parse_positive_int(parsed.get("page_end"))
    if page_start is not None and page_end is not None and page_start > page_end:
        page_start, page_end = page_end, page_start

    section = parsed.get("section")
    if not isinstance(section, str) or not section.strip():
        section = None

    return SearchDocumentQuery(
        path=path.strip(),
        paths=parsed_paths,
        query=retrieval_query.strip() if retrieval_query else None,
        limit=limit,
        mode=mode,
        page=page,
        page_start=page_start,
        page_end=page_end,
        section=section.strip() if section else None,
    )


def _parse_positive_int(value) -> int | None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        return None
    return value


def _load_search_documents(
    root: Path,
    parsed_query: SearchDocumentQuery,
) -> list[tuple[Path, list[DocumentChunk]]]:
    documents = []
    for query_path in parsed_query.paths or (parsed_query.path,):
        path = _resolve_inside_root(root, query_path)
        if (
            path is None
            or not path.is_file()
            or path.suffix.lower() not in SUPPORTED_SUFFIXES
        ):
            continue
        chunks = _load_document_chunks(path)
        if chunks:
            documents.append((path, chunks))
    return documents


def _load_document_chunks(path: Path) -> list[DocumentChunk]:
    index_path = _usable_document_index_path(path)
    if index_path is None:
        return _read_document_chunks(path)

    try:
        index = DocumentVectorIndex.load(index_path)
        fresh_chunks = index.get_fresh_chunks(path)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as error:
        LOGGER.debug("Falling back after document index read failed: %s", error)
        return _read_document_chunks(path)

    if fresh_chunks:
        return _document_chunks_from_index(fresh_chunks)

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
    return chunks


def _filter_chunks(
    chunks: list[DocumentChunk],
    parsed_query: SearchDocumentQuery,
) -> list[DocumentChunk]:
    filtered_chunks = chunks
    if parsed_query.page is not None:
        filtered_chunks = [
            chunk for chunk in filtered_chunks if chunk.page == parsed_query.page
        ]
    if parsed_query.page_start is not None:
        filtered_chunks = [
            chunk
            for chunk in filtered_chunks
            if chunk.page is not None and chunk.page >= parsed_query.page_start
        ]
    if parsed_query.page_end is not None:
        filtered_chunks = [
            chunk
            for chunk in filtered_chunks
            if chunk.page is not None and chunk.page <= parsed_query.page_end
        ]
    if parsed_query.section is not None:
        section_query = parsed_query.section.casefold()
        filtered_chunks = [
            chunk
            for chunk in filtered_chunks
            if chunk.section_heading is not None
            and section_query in chunk.section_heading.casefold()
        ]
    return filtered_chunks


def _select_document_chunks(
    candidates: list[tuple[Path, DocumentChunk]],
    parsed_query: SearchDocumentQuery,
) -> list[tuple[Path, DocumentChunk]]:
    if not parsed_query.query:
        return candidates[: parsed_query.limit]

    index_chunks = [
        DocumentIndexChunk(
            text=chunk.snippet,
            index=chunk.index,
            document_index=document_index,
            page=chunk.page,
            section_heading=chunk.section_heading,
        )
        for document_index, (_path, chunk) in enumerate(candidates)
    ]
    ranked = rank_document_chunks(index_chunks, parsed_query.query, mode=parsed_query.mode)
    chunks_by_key = {
        (document_index, chunk.index): (path, chunk)
        for document_index, (path, chunk) in enumerate(candidates)
    }
    selected = [
        chunks_by_key[(chunk.document_index, chunk.index)]
        for chunk in ranked
        if (chunk.document_index, chunk.index) in chunks_by_key
    ]
    return (selected if selected else candidates)[: parsed_query.limit]


def _select_chunks(
    candidates: list[DocumentChunk],
    parsed_query: SearchDocumentQuery,
) -> list[DocumentChunk]:
    if not parsed_query.query:
        return candidates[: parsed_query.limit]

    ranked = _rank_chunks(candidates, parsed_query.query, parsed_query.mode)
    return (ranked if ranked else candidates)[: parsed_query.limit]


def _rank_chunks(
    candidates: list[DocumentChunk],
    query: str,
    mode: SearchDocumentMode | None,
) -> list[DocumentChunk]:
    index_chunks = [
        DocumentIndexChunk(
            text=chunk.snippet,
            index=chunk.index,
            page=chunk.page,
            section_heading=chunk.section_heading,
        )
        for chunk in candidates
    ]
    ranked = rank_document_chunks(index_chunks, query, mode=mode)
    chunks_by_index = {chunk.index: chunk for chunk in candidates}
    return [chunks_by_index[chunk.index] for chunk in ranked if chunk.index in chunks_by_index]
