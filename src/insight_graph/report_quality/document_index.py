import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

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


def get_document_retrieval_mode() -> DocumentRetrievalMode:
    mode = os.environ.get("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "deterministic").strip().lower()
    return "vector" if mode == "vector" else "deterministic"


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
