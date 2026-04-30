import hashlib
import json
import os

import insight_graph.report_quality.document_index as document_index
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


def test_rank_document_chunks_uses_deterministic_vector_fallback(monkeypatch) -> None:
    chunks = [
        DocumentIndexChunk(text="alpha lexical match", index=0),
        DocumentIndexChunk(text="beta semantic match", index=1),
    ]

    def fake_embedding(text: str, *, dimensions: int = 64):
        if text == "alpha":
            return [0.0, 1.0]
        if "beta" in text:
            return [0.0, 1.0]
        return [1.0, 0.0]

    monkeypatch.setattr(
        document_index,
        "deterministic_text_embedding",
        fake_embedding,
        raising=False,
    )
    monkeypatch.setenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "vector")

    ranked = rank_document_chunks(chunks, "alpha")

    assert [chunk.index for chunk in ranked[:1]] == [1]
    assert ranked[0].score > 0


def test_get_document_retrieval_mode_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", raising=False)
    assert get_document_retrieval_mode() == "deterministic"

    monkeypatch.setenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "unknown")
    assert get_document_retrieval_mode() == "deterministic"

    monkeypatch.setenv("INSIGHT_GRAPH_DOCUMENT_RETRIEVAL", "vector")
    assert get_document_retrieval_mode() == "vector"


def test_get_document_index_path_uses_configured_environment_path(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_DOCUMENT_INDEX_PATH", raising=False)
    assert document_index.get_document_index_path() is None

    index_path = tmp_path / "documents.json"
    monkeypatch.setenv("INSIGHT_GRAPH_DOCUMENT_INDEX_PATH", str(index_path))

    assert document_index.get_document_index_path() == index_path


def test_document_vector_index_saves_and_loads_document_entry_with_chunks(tmp_path) -> None:
    document_path = tmp_path / "report.md"
    document_path.write_text("# Overview\nAlpha evidence", encoding="utf-8")
    index_path = tmp_path / "cache" / "documents.json"
    chunks = [
        DocumentIndexChunk(
            text="Alpha evidence",
            index=0,
            page=3,
            section_heading="Overview",
            score=42,
        )
    ]

    index = document_index.DocumentVectorIndex.load(index_path)
    index.store_document(document_path, chunks)
    index.save()

    payload = json.loads(index_path.read_text(encoding="utf-8"))
    entry = payload["documents"][str(document_path.resolve())]
    assert payload["version"] == 1
    assert entry["chunks"][0]["text"] == "Alpha evidence"
    assert entry["chunks"][0]["embedding"]
    assert entry["chunks"][0]["score"] == 42

    loaded = document_index.DocumentVectorIndex.load(index_path)
    fresh_chunks = loaded.get_fresh_chunks(document_path)

    assert len(fresh_chunks) == 1
    assert fresh_chunks[0].text == "Alpha evidence"
    assert fresh_chunks[0].index == 0
    assert fresh_chunks[0].page == 3
    assert fresh_chunks[0].section_heading == "Overview"
    assert fresh_chunks[0].embedding
    assert fresh_chunks[0].score == 42


def test_document_vector_index_reuses_fresh_entry_when_metadata_matches(tmp_path) -> None:
    document_path = tmp_path / "report.md"
    document_path.write_text("Alpha evidence", encoding="utf-8")
    index_path = tmp_path / "documents.json"

    index = document_index.DocumentVectorIndex.load(index_path)
    index.store_document(document_path, [DocumentIndexChunk(text="Alpha evidence", index=0)])
    index.save()

    loaded = document_index.DocumentVectorIndex.load(index_path)

    assert [chunk.text for chunk in loaded.get_fresh_chunks(document_path)] == ["Alpha evidence"]


def test_document_vector_index_returns_no_fresh_chunks_when_metadata_changes(tmp_path) -> None:
    document_path = tmp_path / "report.md"
    document_path.write_text("Alpha evidence", encoding="utf-8")
    index_path = tmp_path / "documents.json"

    index = document_index.DocumentVectorIndex.load(index_path)
    index.store_document(document_path, [DocumentIndexChunk(text="Alpha evidence", index=0)])
    index.save()
    document_path.write_text("Alpha evidence changed", encoding="utf-8")

    loaded = document_index.DocumentVectorIndex.load(index_path)

    assert loaded.get_fresh_chunks(document_path) == []


def test_document_vector_index_rejects_entry_when_content_hash_changes(tmp_path) -> None:
    document_path = tmp_path / "report.md"
    document_path.write_text("Alpha evidence", encoding="utf-8")
    original_stat = document_path.stat()
    index_path = tmp_path / "documents.json"

    index = document_index.DocumentVectorIndex.load(index_path)
    index.store_document(document_path, [DocumentIndexChunk(text="Alpha evidence", index=0)])
    index.save()
    document_path.write_text("Omega evidence", encoding="utf-8")
    os.utime(
        document_path,
        ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns),
    )

    loaded = document_index.DocumentVectorIndex.load(index_path)

    assert document_path.stat().st_size == original_stat.st_size
    assert document_path.stat().st_mtime_ns == original_stat.st_mtime_ns
    assert loaded.get_fresh_chunks(document_path) == []


def test_document_vector_index_skips_malformed_chunk_payloads(tmp_path) -> None:
    document_path = tmp_path / "report.md"
    document_path.write_text("Alpha evidence", encoding="utf-8")
    stat = document_path.stat()
    index_path = tmp_path / "documents.json"
    chunk = {
        "text": "Alpha evidence",
        "index": 0,
        "page": 1,
        "section_heading": "Overview",
        "embedding": [1, 2.5],
        "score": 7,
    }
    payload = {
        "version": 1,
        "documents": {
            str(document_path.resolve()): {
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "content_hash": hashlib.sha256(document_path.read_bytes()).hexdigest(),
                "chunks": [
                    {**chunk, "text": 123},
                    {**chunk, "index": "bad"},
                    {**chunk, "page": "bad"},
                    {**chunk, "section_heading": 123},
                    {**chunk, "embedding": [1, None]},
                    chunk,
                ],
            }
        },
    }
    index_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = document_index.DocumentVectorIndex.load(index_path)
    fresh_chunks = loaded.get_fresh_chunks(document_path)

    assert len(fresh_chunks) == 1
    assert fresh_chunks[0].embedding == [1.0, 2.5]
    assert fresh_chunks[0].score == 7


def test_document_vector_index_loads_corrupt_json_as_empty_index(tmp_path) -> None:
    document_path = tmp_path / "report.md"
    document_path.write_text("Alpha evidence", encoding="utf-8")
    index_path = tmp_path / "documents.json"
    index_path.write_text("{not json", encoding="utf-8")

    index = document_index.DocumentVectorIndex.load(index_path)

    assert index.get_fresh_chunks(document_path) == []


def test_build_index_chunks_includes_deterministic_embeddings(monkeypatch) -> None:
    calls = []

    def fake_embedding(text: str, *, dimensions: int = 64):
        calls.append(text)
        return [0.25, 0.75]

    monkeypatch.setattr(
        document_index,
        "deterministic_text_embedding",
        fake_embedding,
        raising=False,
    )

    indexed = document_index.build_index_chunks(
        [DocumentIndexChunk(text="Alpha evidence", index=4, section_heading="Overview")]
    )

    assert calls == ["Overview Alpha evidence"]
    assert indexed[0].embedding == [0.25, 0.75]
    assert indexed[0].text == "Alpha evidence"
    assert indexed[0].index == 4
