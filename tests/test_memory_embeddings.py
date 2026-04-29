from insight_graph.memory.embeddings import (
    build_memory_record,
    deterministic_text_embedding,
    get_embedding_provider,
)
from insight_graph.memory.store import ResearchMemoryRecord


def test_deterministic_text_embedding_is_stable_and_normalized() -> None:
    first = deterministic_text_embedding("Pricing roadmap pricing", dimensions=8)
    second = deterministic_text_embedding("Pricing roadmap pricing", dimensions=8)

    assert first == second
    assert len(first) == 8
    assert abs(sum(value * value for value in first) - 1.0) < 0.000001


def test_deterministic_text_embedding_distinguishes_text() -> None:
    pricing = deterministic_text_embedding("pricing packaging enterprise", dimensions=8)
    risk = deterministic_text_embedding("security risk compliance", dimensions=8)

    assert pricing != risk


def test_build_memory_record_generates_embedding_and_metadata() -> None:
    record = build_memory_record(
        memory_id="m1",
        text="Grounded finding about pricing.",
        metadata={"run_id": "run-1"},
        dimensions=8,
    )

    assert isinstance(record, ResearchMemoryRecord)
    assert record.memory_id == "m1"
    assert record.text == "Grounded finding about pricing."
    assert record.metadata == {"run_id": "run-1", "embedding_provider": "deterministic"}
    assert len(record.embedding) == 8


def test_get_embedding_provider_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", raising=False)
    assert get_embedding_provider() == "deterministic"

    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "unknown")
    assert get_embedding_provider() == "deterministic"
