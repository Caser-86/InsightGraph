from insight_graph.memory.store import (
    InMemoryResearchMemoryStore,
    PgVectorResearchMemoryStore,
    ResearchMemoryRecord,
    get_research_memory_store,
)
from insight_graph.memory.writeback import write_report_memories
from insight_graph.state import Evidence, Finding, GraphState


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

    def fetchone(self):
        return None


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
            metadata={"source": "pricing", "embedding_provider": "deterministic"},
        )
    )
    store.add_memory(
        ResearchMemoryRecord(
            memory_id="m2",
            text="risk evidence",
            embedding=[0.0, 1.0],
            metadata={"source": "risk", "embedding_provider": "external"},
        )
    )

    results = store.search(
        [0.9, 0.1],
        limit=1,
        metadata_filter={"embedding_provider": "deterministic"},
    )

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
    assert any(
        "CREATE TABLE IF NOT EXISTS insight_graph_schema_migrations" in sql
        for sql in statements
    )
    assert any("CREATE EXTENSION IF NOT EXISTS vector" in sql for sql in statements)
    assert any("CREATE TABLE IF NOT EXISTS insight_graph_memories" in sql for sql in statements)
    assert any("ON CONFLICT (memory_id) DO UPDATE" in sql for sql in statements)
    assert any("vector_dims(embedding) = vector_dims(%s::vector)" in sql for sql in statements)
    assert any("metadata @> %s::jsonb" in sql for sql in statements)
    assert any("embedding <-> %s::vector" in sql for sql in statements)
    assert connection.cursor_obj.statements[-1][1] == ("[0.1,0.2]", "{}", "[0.1,0.2]", 3)
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


def test_write_report_memories_is_disabled_by_default(monkeypatch) -> None:
    store = InMemoryResearchMemoryStore()
    state = GraphState(user_request="Compare tools", report_markdown="# Report")
    monkeypatch.delenv("INSIGHT_GRAPH_MEMORY_WRITEBACK", raising=False)

    assert write_report_memories(state, store=store, run_id="run-1") == 0
    assert store.search([1.0] * 64, limit=10) == []


def test_write_report_memories_stores_summary_claims_references_and_entities(
    monkeypatch,
) -> None:
    store = InMemoryResearchMemoryStore()
    state = GraphState(
        user_request="Compare Cursor and Copilot",
        resolved_entities=[{"id": "cursor", "name": "Cursor"}],
        report_markdown="# InsightGraph Research Report\n\nCursor differs from Copilot.",
        findings=[
            Finding(
                title="Pricing differs",
                summary="Cursor and Copilot package pricing differently.",
                evidence_ids=["ev-1"],
            )
        ],
        grounded_claims=[
            {
                "claim": "Cursor has editor-native positioning.",
                "evidence_ids": ["ev-1"],
                "support_status": "supported",
            },
            {
                "claim": "Unsupported claim.",
                "evidence_ids": ["ev-2"],
                "support_status": "unsupported",
            },
        ],
        evidence_pool=[
            Evidence(
                id="ev-1",
                subtask_id="s1",
                title="Cursor pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor pricing evidence.",
                source_type="official_site",
                verified=True,
            )
        ],
    )
    monkeypatch.setenv("INSIGHT_GRAPH_MEMORY_WRITEBACK", "1")

    count = write_report_memories(state, store=store, run_id="run-1")
    records = list(store._records.values())

    assert count == 5
    assert {record.metadata["memory_type"] for record in records} == {
        "report_summary",
        "entity",
        "supported_claim",
        "reference",
        "source_reliability_note",
    }
    assert all(record.metadata["run_id"] == "run-1" for record in records)
    assert all(record.metadata["refresh_after_days"] == 90 for record in records)
    assert all(record.metadata["expires_after_days"] == 365 for record in records)
    assert any("Cursor has editor-native positioning" in record.text for record in records)
    assert not any("Unsupported claim" in record.text for record in records)


def test_write_report_memories_adds_refresh_metadata_and_source_reliability_notes(
    monkeypatch,
) -> None:
    store = InMemoryResearchMemoryStore()
    state = GraphState(
        user_request="Compare Cursor and Copilot",
        domain_profile="competitive_intel",
        report_markdown="# InsightGraph Research Report\n\nCursor differs from Copilot.",
        evidence_pool=[
            Evidence(
                id="ev-1",
                subtask_id="s1",
                title="Cursor pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor pricing evidence.",
                source_type="official_site",
                verified=True,
                source_trusted=True,
            )
        ],
    )
    monkeypatch.setenv("INSIGHT_GRAPH_MEMORY_WRITEBACK", "1")

    count = write_report_memories(state, store=store, run_id="run-1")
    records = list(store._records.values())

    assert count == 3
    assert {record.metadata["memory_type"] for record in records} == {
        "report_summary",
        "reference",
        "source_reliability_note",
    }
    for record in records:
        assert record.metadata["domain_profile"] == "competitive_intel"
        assert record.metadata["refresh_after_days"] == 90
        assert record.metadata["expires_after_days"] == 365
        assert record.metadata["support_status"] in {"summary", "fresh_evidence"}
    reliability = [
        record
        for record in records
        if record.metadata["memory_type"] == "source_reliability_note"
    ][0]
    assert reliability.metadata["source_reliability"] == "trusted"
    assert "official_site source trusted" in reliability.text
