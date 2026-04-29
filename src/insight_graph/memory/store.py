import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from insight_graph.persistence.checkpoints import _connect_postgres


class ResearchMemoryStore(Protocol):
    def ensure_schema(self) -> None: ...

    def add_memory(self, record: "ResearchMemoryRecord") -> None: ...

    def search(self, embedding: list[float], *, limit: int = 5) -> list["ResearchMemoryRecord"]: ...

    def delete_memory(self, memory_id: str) -> bool: ...

    def delete_by_metadata(self, key: str, value: str) -> int: ...


@dataclass(frozen=True)
class ResearchMemoryRecord:
    memory_id: str
    text: str
    embedding: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)


class InMemoryResearchMemoryStore:
    def __init__(self) -> None:
        self._records: dict[str, ResearchMemoryRecord] = {}

    def ensure_schema(self) -> None:
        return None

    def add_memory(self, record: ResearchMemoryRecord) -> None:
        self._records[record.memory_id] = record

    def search(self, embedding: list[float], *, limit: int = 5) -> list[ResearchMemoryRecord]:
        scored = [
            (_cosine_similarity(record.embedding, embedding), record.memory_id, record)
            for record in self._records.values()
        ]
        scored.sort(reverse=True)
        return [record for score, _, record in scored[:limit] if score > 0]

    def delete_memory(self, memory_id: str) -> bool:
        return self._records.pop(memory_id, None) is not None

    def delete_by_metadata(self, key: str, value: str) -> int:
        matching_ids = [
            memory_id
            for memory_id, record in self._records.items()
            if record.metadata.get(key) == value
        ]
        for memory_id in matching_ids:
            del self._records[memory_id]
        return len(matching_ids)


class PgVectorResearchMemoryStore:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS insight_graph_memories (
                    memory_id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    embedding vector NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        connection.commit()

    def add_memory(self, record: ResearchMemoryRecord) -> None:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO insight_graph_memories (memory_id, text, embedding, metadata)
                VALUES (%s, %s, %s::vector, %s)
                ON CONFLICT (memory_id) DO UPDATE SET
                    text = EXCLUDED.text,
                    embedding = EXCLUDED.embedding,
                    metadata = EXCLUDED.metadata,
                    updated_at = now()
                """,
                (
                    record.memory_id,
                    record.text,
                    _vector_literal(record.embedding),
                    record.metadata,
                ),
            )
        connection.commit()

    def search(self, embedding: list[float], *, limit: int = 5) -> list[ResearchMemoryRecord]:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT memory_id, text, embedding, metadata
                FROM insight_graph_memories
                ORDER BY embedding <-> %s::vector
                LIMIT %s
                """,
                (_vector_literal(embedding), limit),
            )
            rows = cursor.fetchall()
        return [
            ResearchMemoryRecord(
                memory_id=row[0],
                text=row[1],
                embedding=list(row[2]),
                metadata=dict(row[3]),
            )
            for row in rows
        ]

    def delete_memory(self, memory_id: str) -> bool:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM insight_graph_memories WHERE memory_id = %s",
                (memory_id,),
            )
        connection.commit()
        return True

    def delete_by_metadata(self, key: str, value: str) -> int:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM insight_graph_memories WHERE metadata ->> %s = %s",
                (key, value),
            )
        connection.commit()
        return 0


def get_research_memory_store() -> ResearchMemoryStore:
    backend = os.environ.get("INSIGHT_GRAPH_MEMORY_BACKEND", "memory").strip().lower()
    if backend != "pgvector":
        return InMemoryResearchMemoryStore()

    dsn = os.environ.get("INSIGHT_GRAPH_POSTGRES_DSN", "").strip()
    if not dsn:
        return InMemoryResearchMemoryStore()
    return PgVectorResearchMemoryStore(lambda: _connect_postgres(dsn))


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _vector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(value) for value in values) + "]"
