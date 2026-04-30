import json
import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from insight_graph.memory.embeddings import deterministic_text_embedding

DocumentRetrievalMode = Literal["deterministic", "vector"]
VectorRanker = Callable[[Sequence["DocumentIndexChunk"], str], list["DocumentIndexChunk"]]


@dataclass(frozen=True)
class DocumentIndexChunk:
    text: str
    index: int
    page: int | None = None
    section_heading: str | None = None
    score: int = 0


@dataclass(frozen=True)
class IndexedDocumentChunk:
    text: str
    index: int
    page: int | None = None
    section_heading: str | None = None
    embedding: list[float] = field(default_factory=list)
    score: int = 0


def get_document_retrieval_mode() -> DocumentRetrievalMode:
    mode = os.environ.get("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "deterministic").strip().lower()
    return "vector" if mode == "vector" else "deterministic"


def get_document_index_path() -> Path | None:
    value = os.environ.get("INSIGHT_GRAPH_DOCUMENT_INDEX_PATH", "").strip()
    return Path(value) if value else None


class DocumentVectorIndex:
    def __init__(self, path: Path, documents: dict[str, Any] | None = None) -> None:
        self.path = path
        self._documents = documents or {}

    @classmethod
    def load(cls, path: Path) -> "DocumentVectorIndex":
        index_path = Path(path)
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls(index_path)

        if not isinstance(payload, dict):
            return cls(index_path)
        documents = payload.get("documents")
        if payload.get("version") != 1 or not isinstance(documents, dict):
            return cls(index_path)
        return cls(index_path, documents)

    def get_fresh_chunks(self, document_path: Path) -> list[IndexedDocumentChunk]:
        path = Path(document_path)
        try:
            stat = path.stat()
        except OSError:
            return []

        entry = self._documents.get(str(path.resolve()))
        if not isinstance(entry, dict):
            return []
        if entry.get("mtime_ns") != stat.st_mtime_ns or entry.get("size") != stat.st_size:
            return []

        chunks = entry.get("chunks")
        if not isinstance(chunks, list):
            return []
        return [_indexed_chunk_from_json(chunk) for chunk in chunks if isinstance(chunk, dict)]

    def store_document(self, document_path: Path, chunks: Sequence[DocumentIndexChunk]) -> None:
        path = Path(document_path)
        stat = path.stat()
        self._documents[str(path.resolve())] = {
            "mtime_ns": stat.st_mtime_ns,
            "size": stat.st_size,
            "chunks": [_indexed_chunk_to_json(chunk) for chunk in build_index_chunks(chunks)],
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "documents": self._documents}
        self.path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def build_index_chunks(chunks: Sequence[DocumentIndexChunk]) -> list[IndexedDocumentChunk]:
    indexed_chunks = []
    for chunk in chunks:
        indexed_chunks.append(
            IndexedDocumentChunk(
                text=chunk.text,
                index=chunk.index,
                page=chunk.page,
                section_heading=chunk.section_heading,
                embedding=deterministic_text_embedding(
                    " ".join([chunk.section_heading or "", chunk.text])
                ),
                score=chunk.score,
            )
        )
    return indexed_chunks


def _indexed_chunk_to_json(chunk: IndexedDocumentChunk) -> dict[str, Any]:
    return {
        "text": chunk.text,
        "index": chunk.index,
        "page": chunk.page,
        "section_heading": chunk.section_heading,
        "embedding": chunk.embedding,
    }


def _indexed_chunk_from_json(payload: dict[str, Any]) -> IndexedDocumentChunk:
    embedding = payload.get("embedding")
    return IndexedDocumentChunk(
        text=str(payload.get("text", "")),
        index=int(payload.get("index", 0)),
        page=payload.get("page") if isinstance(payload.get("page"), int) else None,
        section_heading=payload.get("section_heading")
        if isinstance(payload.get("section_heading"), str)
        else None,
        embedding=embedding if isinstance(embedding, list) else [],
    )


def rank_document_chunks(
    chunks: Sequence[DocumentIndexChunk],
    query: str,
    *,
    vector_ranker: VectorRanker | None = None,
) -> list[DocumentIndexChunk]:
    if get_document_retrieval_mode() == "vector":
        if vector_ranker is not None:
            return vector_ranker(chunks, query)
        return _rank_chunks_by_deterministic_vector(chunks, query)

    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return []

    scored = []
    for chunk in chunks:
        text_tokens = _tokenize(chunk.text)
        heading_tokens = _tokenize(chunk.section_heading or "")
        score = sum(1 for token in text_tokens if token in query_tokens)
        score += 100 * sum(1 for token in heading_tokens if token in query_tokens)
        distinct_matches = len({token for token in text_tokens if token in query_tokens})
        distinct_matches += len({token for token in heading_tokens if token in query_tokens})
        if score > 0:
            scored.append(
                (
                    score,
                    distinct_matches,
                    -chunk.index,
                    DocumentIndexChunk(
                        text=chunk.text,
                        index=chunk.index,
                        page=chunk.page,
                        section_heading=chunk.section_heading,
                        score=score,
                    ),
                )
            )

    scored.sort(reverse=True)
    return [chunk for _, _, _, chunk in scored]


def _rank_chunks_by_deterministic_vector(
    chunks: Sequence[DocumentIndexChunk],
    query: str,
) -> list[DocumentIndexChunk]:
    query_embedding = deterministic_text_embedding(query)
    scored = []
    for chunk in chunks:
        chunk_embedding = deterministic_text_embedding(
            " ".join([chunk.section_heading or "", chunk.text])
        )
        score = _cosine_similarity(query_embedding, chunk_embedding)
        if score > 0:
            scored.append(
                (
                    score,
                    -chunk.index,
                    DocumentIndexChunk(
                        text=chunk.text,
                        index=chunk.index,
                        page=chunk.page,
                        section_heading=chunk.section_heading,
                        score=int(score * 10_000),
                    ),
                )
            )
    scored.sort(reverse=True)
    return [chunk for _, _, chunk in scored]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True))


def _tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 3]
