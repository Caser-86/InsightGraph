import os
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

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
    if get_document_retrieval_mode() == "vector" and vector_ranker is not None:
        return vector_ranker(chunks, query)

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


def _tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 3]
