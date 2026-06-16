from insight_graph.persistence.checkpoints import (
    CheckpointRecord,
    InMemoryCheckpointStore,
    PostgresCheckpointStore,
    get_checkpoint_store,
)
from insight_graph.state import GraphState


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

    def fetchone(self):
        return self.row


class FakeConnection:
    def __init__(self, row=None) -> None:
        self.cursor_obj = FakeCursor(row=row)
        self.commits = 0

    def cursor(self):
        return self.cursor_obj

    def commit(self) -> None:
        self.commits += 1


def test_in_memory_checkpoint_store_round_trips_graph_state() -> None:
    store = InMemoryCheckpointStore()
    state = GraphState(user_request="resume this", iterations=2)

    store.save_checkpoint(CheckpointRecord.from_state("run-1", "critic", state))
    restored = store.load_checkpoint("run-1")

    assert restored is not None
    assert restored.run_id == "run-1"
    assert restored.node_name == "critic"
    assert restored.to_state().user_request == "resume this"
    assert restored.to_state().iterations == 2


def test_postgres_checkpoint_store_emits_schema_and_upsert_sql() -> None:
    connection = FakeConnection()
    store = PostgresCheckpointStore(lambda: connection)
    record = CheckpointRecord.from_state("run-1", "collector", GraphState(user_request="q"))

    store.ensure_schema()
    store.save_checkpoint(record)

    statements = [statement for statement, _ in connection.cursor_obj.statements]
    assert any(
        "CREATE TABLE IF NOT EXISTS insight_graph_schema_migrations" in sql
        for sql in statements
    )
    assert any("CREATE TABLE IF NOT EXISTS insight_graph_checkpoints" in sql for sql in statements)
    assert any("ON CONFLICT (run_id) DO UPDATE" in sql for sql in statements)
    assert connection.commits == 2


def test_postgres_checkpoint_store_loads_graph_state() -> None:
    payload = GraphState(user_request="loaded", iterations=1).model_dump(mode="json")
    connection = FakeConnection(row=("run-1", "analyst", payload))
    store = PostgresCheckpointStore(lambda: connection)

    record = store.load_checkpoint("run-1")

    assert record is not None
    assert record.run_id == "run-1"
    assert record.node_name == "analyst"
    assert record.to_state().user_request == "loaded"
    assert record.to_state().iterations == 1


def test_get_checkpoint_store_defaults_to_memory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_CHECKPOINT_BACKEND", raising=False)
    assert isinstance(get_checkpoint_store(), InMemoryCheckpointStore)

    monkeypatch.setenv("INSIGHT_GRAPH_CHECKPOINT_BACKEND", "postgres")
    monkeypatch.setenv("INSIGHT_GRAPH_POSTGRES_DSN", "postgresql://localhost/db")
    assert isinstance(get_checkpoint_store(), PostgresCheckpointStore)
