import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from insight_graph.state import GraphState


class CheckpointStore(Protocol):
    def ensure_schema(self) -> None: ...

    def save_checkpoint(self, record: "CheckpointRecord") -> None: ...

    def load_checkpoint(self, run_id: str) -> "CheckpointRecord | None": ...


@dataclass(frozen=True)
class CheckpointRecord:
    run_id: str
    node_name: str
    state_payload: dict[str, Any]

    @classmethod
    def from_state(cls, run_id: str, node_name: str, state: GraphState) -> "CheckpointRecord":
        return cls(
            run_id=run_id,
            node_name=node_name,
            state_payload=state.model_dump(mode="json"),
        )

    def to_state(self) -> GraphState:
        return GraphState.model_validate(self.state_payload)


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._records: dict[str, CheckpointRecord] = {}

    def ensure_schema(self) -> None:
        return None

    def save_checkpoint(self, record: CheckpointRecord) -> None:
        self._records[record.run_id] = record

    def load_checkpoint(self, run_id: str) -> CheckpointRecord | None:
        return self._records.get(run_id)


class PostgresCheckpointStore:
    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connection_factory = connection_factory

    def ensure_schema(self) -> None:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS insight_graph_checkpoints (
                    run_id TEXT PRIMARY KEY,
                    node_name TEXT NOT NULL,
                    state_payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """
            )
        connection.commit()

    def save_checkpoint(self, record: CheckpointRecord) -> None:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO insight_graph_checkpoints (run_id, node_name, state_payload)
                VALUES (%s, %s, %s)
                ON CONFLICT (run_id) DO UPDATE SET
                    node_name = EXCLUDED.node_name,
                    state_payload = EXCLUDED.state_payload,
                    updated_at = now()
                """,
                (record.run_id, record.node_name, record.state_payload),
            )
        connection.commit()

    def load_checkpoint(self, run_id: str) -> CheckpointRecord | None:
        connection = self._connection_factory()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT run_id, node_name, state_payload
                FROM insight_graph_checkpoints
                WHERE run_id = %s
                """,
                (run_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        loaded_run_id, node_name, state_payload = row
        return CheckpointRecord(
            run_id=loaded_run_id,
            node_name=node_name,
            state_payload=dict(state_payload),
        )


def get_checkpoint_store() -> CheckpointStore:
    backend = os.environ.get("INSIGHT_GRAPH_CHECKPOINT_BACKEND", "memory").strip().lower()
    if backend != "postgres":
        return InMemoryCheckpointStore()

    dsn = os.environ.get("INSIGHT_GRAPH_POSTGRES_DSN", "").strip()
    if not dsn:
        return InMemoryCheckpointStore()
    return PostgresCheckpointStore(lambda: _connect_postgres(dsn))


def _connect_postgres(dsn: str) -> Any:
    try:
        import psycopg  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "PostgreSQL checkpoints require installing the optional psycopg dependency."
        ) from exc
    return psycopg.connect(dsn)
