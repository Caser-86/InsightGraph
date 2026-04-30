from insight_graph.memory.store import (
    InMemoryResearchMemoryStore,
    PgVectorResearchMemoryStore,
    ResearchMemoryRecord,
    get_research_memory_store,
)


class FakeCursor:
    def __init__(self, row=None) -> None:
        self.row = row
        self.statements: list[tuple[str, tuple | None]] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def execute(self, sql: str, params: tuple | None = None) -> None:
        self.statements.append((sql, params))

    def fetchall(self):
        return [] if self.row is None else [self.row]


class FakeConnection:
    def __init__(self, row=None) -> None:
        self.cursor_obj = FakeCursor(row=row)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1


def test_in_memory_research_memory_ranks_by_embedding_similarity() -> None:
    store = InMemoryResearchMemoryStore()
    store.add_memory(
        ResearchMemoryRecord(
            memory_id="m1",
            text="pricing evidence",
            embedding=[1.0, 0.0],
            metadata={"source": "pricing"},
        )
    )
    store.add_memory(
        ResearchMemoryRecord(
            memory_id="m2",
            text="risk evidence",
            embedding=[0.0, 1.0],
            metadata={"source": "risk"},
        )
    )

    results = store.search([0.9, 0.1], limit=1)

    assert [record.memory_id for record in results] == ["m1"]


def test_in_memory_research_memory_deletes_by_id_and_metadata() -> None:
    store = InMemoryResearchMemoryStore()
    store.add_memory(
        ResearchMemoryRecord(
            memory_id="m1",
            text="pricing evidence",
            embedding=[1.0, 0.0],
            metadata={"user_id": "u1", "run_id": "r1"},
        )
    )
    store.add_memory(
        ResearchMemoryRecord(
            memory_id="m2",
            text="risk evidence",
            embedding=[1.0, 0.0],
            metadata={"user_id": "u1", "run_id": "r2"},
        )
    )
    store.add_memory(
        ResearchMemoryRecord(
            memory_id="m3",
            text="market evidence",
            embedding=[1.0, 0.0],
            metadata={"user_id": "u2", "run_id": "r3"},
        )
    )

    assert store.delete_memory("m1") is True
    assert store.delete_memory("missing") is False
    assert store.delete_by_metadata("user_id", "u1") == 1

    assert [record.memory_id for record in store.search([1.0, 0.0], limit=10)] == ["m3"]


def test_pgvector_memory_store_emits_schema_insert_and_search_sql() -> None:
    connection = FakeConnection()
    store = PgVectorResearchMemoryStore(lambda: connection)
    record = ResearchMemoryRecord(
        memory_id="m1",
        text="grounded finding",
        embedding=[0.1, 0.2],
        metadata={"run_id": "run-1"},
    )

    store.ensure_schema()
    store.add_memory(record)
    store.search([0.1, 0.2], limit=3)

    statements = [statement for statement, _ in connection.cursor_obj.statements]
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in statements)
    assert any("CREATE TABLE IF NOT EXISTS insight_graph_memories" in sql for sql in statements)
    assert any("ON CONFLICT (memory_id) DO UPDATE" in sql for sql in statements)
    assert any("vector_dims(embedding) = vector_dims(%s::vector)" in sql for sql in statements)
    assert any("embedding <-> %s::vector" in sql for sql in statements)
    assert connection.cursor_obj.statements[-1][1] == ("[0.1,0.2]", "[0.1,0.2]", 3)
    assert connection.commits == 2


def test_pgvector_memory_store_deletes_by_id_and_metadata() -> None:
    connection = FakeConnection()
    store = PgVectorResearchMemoryStore(lambda: connection)

    store.delete_memory("m1")
    store.delete_by_metadata("user_id", "u1")

    statements = connection.cursor_obj.statements
    assert any(
        "DELETE FROM insight_graph_memories WHERE memory_id = %s" in sql
        for sql, _ in statements
    )
    assert any(
        "DELETE FROM insight_graph_memories WHERE metadata ->> %s = %s" in sql
        for sql, _ in statements
    )
    assert connection.commits == 2


def test_pgvector_memory_store_loads_search_results() -> None:
    connection = FakeConnection(row=("m1", "stored finding", [0.1, 0.2], {"source": "eval"}))
    store = PgVectorResearchMemoryStore(lambda: connection)

    results = store.search([0.1, 0.2], limit=1)

    assert results == [
        ResearchMemoryRecord(
            memory_id="m1",
            text="stored finding",
            embedding=[0.1, 0.2],
            metadata={"source": "eval"},
        )
    ]


def test_get_research_memory_store_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_MEMORY_BACKEND", raising=False)
    assert isinstance(get_research_memory_store(), InMemoryResearchMemoryStore)

    monkeypatch.setenv("INSIGHT_GRAPH_MEMORY_BACKEND", "pgvector")
    monkeypatch.setenv("INSIGHT_GRAPH_POSTGRES_DSN", "postgresql://localhost/db")
    assert isinstance(get_research_memory_store(), PgVectorResearchMemoryStore)
