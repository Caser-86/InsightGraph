from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Migration:
    version: str
    apply: Callable[[Any], None]


def _create_document_pgvector_tables(cursor: Any) -> None:
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS insight_graph_document_chunks (
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            source_url TEXT NOT NULL,
            source_type TEXT,
            section_heading TEXT,
            document_page INTEGER,
            snippet_start INTEGER,
            snippet_end INTEGER,
            text TEXT NOT NULL,
            embedding vector,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (document_id, chunk_index)
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS insight_graph_document_chunks_embedding_idx
        ON insight_graph_document_chunks
        USING ivfflat (embedding vector_cosine_ops)
        """
    )


DOCUMENT_PGVECTOR_MIGRATIONS = [
    Migration("001_document_pgvector_chunks", _create_document_pgvector_tables)
]


def run_migrations(connection: Any, migrations: list[Migration]) -> None:
    with connection.cursor() as cursor:
        _ensure_migration_table(cursor)
        for migration in sorted(migrations, key=lambda item: item.version):
            if _migration_applied(cursor, migration.version):
                continue
            migration.apply(cursor)
            cursor.execute(
                """
                INSERT INTO insight_graph_schema_migrations (version)
                VALUES (%s)
                """,
                (migration.version,),
            )
    connection.commit()


def _ensure_migration_table(cursor: Any) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS insight_graph_schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def _migration_applied(cursor: Any, version: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM insight_graph_schema_migrations
        WHERE version = %s
        """,
        (version,),
    )
    return cursor.fetchone() is not None
