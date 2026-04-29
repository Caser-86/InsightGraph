import hashlib
import math
import os
import re
from typing import Literal

from insight_graph.memory.store import ResearchMemoryRecord

EmbeddingProvider = Literal["deterministic"]


def get_embedding_provider() -> EmbeddingProvider:
    provider = os.environ.get("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "deterministic").strip().lower()
    return "deterministic" if provider != "deterministic" else "deterministic"


def build_memory_record(
    *,
    memory_id: str,
    text: str,
    metadata: dict[str, object] | None = None,
    dimensions: int = 64,
) -> ResearchMemoryRecord:
    provider = get_embedding_provider()
    merged_metadata = dict(metadata or {})
    merged_metadata["embedding_provider"] = provider
    return ResearchMemoryRecord(
        memory_id=memory_id,
        text=text,
        embedding=deterministic_text_embedding(text, dimensions=dimensions),
        metadata=merged_metadata,
    )


def deterministic_text_embedding(text: str, *, dimensions: int = 64) -> list[float]:
    dimensions = max(dimensions, 1)
    vector = [0.0] * dimensions
    tokens = _tokenize(text)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 2]
