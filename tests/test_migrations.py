from insight_graph.persistence.migrations import (
    DOCUMENT_PGVECTOR_MIGRATIONS,
    Migration,
    run_migrations,
)


class FakeCursor:
    def __init__(self, applied_versions=None) -> None:
        self.applied_versions = set(applied_versions or [])
        self.statements: list[tuple[str, tuple | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.statements.append((sql, params))
        if "INSERT INTO insight_graph_schema_migrations" in sql and params:
            self.applied_versions.add(str(params[0]))

    def fetchone(self):
        version = self.statements[-1][1][0]
        return (1,) if version in self.applied_versions else None


class FakeConnection:
    def __init__(self, applied_versions=None) -> None:
        self.cursor_obj = FakeCursor(applied_versions=applied_versions)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1


def test_run_migrations_creates_tracking_table_and_applies_ordered_steps() -> None:
    connection = FakeConnection()
    calls: list[str] = []

    run_migrations(
        connection,
        [
            Migration("002_second", lambda cursor: calls.append("second")),
            Migration("001_first", lambda cursor: calls.append("first")),
        ],
    )

    statements = [statement for statement, _ in connection.cursor_obj.statements]
    assert any(
        "CREATE TABLE IF NOT EXISTS insight_graph_schema_migrations" in sql
        for sql in statements
    )
    assert calls == ["first", "second"]
    assert ("001_first",) in [params for _, params in connection.cursor_obj.statements]
    assert ("002_second",) in [params for _, params in connection.cursor_obj.statements]
    assert connection.commits == 1


def test_run_migrations_skips_already_applied_versions() -> None:
    connection = FakeConnection(applied_versions={"001_first"})
    calls: list[str] = []

    run_migrations(
        connection,
        [
            Migration("001_first", lambda cursor: calls.append("first")),
            Migration("002_second", lambda cursor: calls.append("second")),
        ],
    )

    assert calls == ["second"]
    assert connection.commits == 1


def test_document_pgvector_migration_creates_document_chunk_table() -> None:
    connection = FakeConnection()

    run_migrations(connection, DOCUMENT_PGVECTOR_MIGRATIONS)

    statements = "\n".join(statement for statement, _ in connection.cursor_obj.statements)
    assert "CREATE EXTENSION IF NOT EXISTS vector" in statements
    assert "CREATE TABLE IF NOT EXISTS insight_graph_document_chunks" in statements
    assert "embedding vector" in statements
