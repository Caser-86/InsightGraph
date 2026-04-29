from insight_graph.report_quality.document_index import (
    DocumentIndexChunk,
    get_document_retrieval_mode,
    rank_document_chunks,
)


def test_rank_document_chunks_boosts_heading_matches() -> None:
    chunks = [
        DocumentIndexChunk(
            text="Generic implementation notes about product usage.",
            index=0,
            page=None,
            section_heading="Implementation",
        ),
        DocumentIndexChunk(
            text="Pricing plans are described with enterprise packaging details.",
            index=1,
            page=None,
            section_heading="Pricing",
        ),
    ]

    ranked = rank_document_chunks(chunks, "enterprise pricing")

    assert [chunk.index for chunk in ranked] == [1]
    assert ranked[0].score > 100


def test_rank_document_chunks_uses_vector_ranker_only_when_opted_in(monkeypatch) -> None:
    chunks = [
        DocumentIndexChunk(text="alpha evidence", index=0),
        DocumentIndexChunk(text="beta evidence", index=1),
    ]

    def vector_ranker(items, query):
        assert query == "alpha"
        return [items[1]]

    monkeypatch.delenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", raising=False)
    deterministic = rank_document_chunks(chunks, "alpha", vector_ranker=vector_ranker)
    assert [chunk.index for chunk in deterministic] == [0]

    monkeypatch.setenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "vector")
    vector_ranked = rank_document_chunks(chunks, "alpha", vector_ranker=vector_ranker)
    assert [chunk.index for chunk in vector_ranked] == [1]


def test_get_document_retrieval_mode_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", raising=False)
    assert get_document_retrieval_mode() == "deterministic"

    monkeypatch.setenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "unknown")
    assert get_document_retrieval_mode() == "deterministic"

    monkeypatch.setenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "vector")
    assert get_document_retrieval_mode() == "vector"
