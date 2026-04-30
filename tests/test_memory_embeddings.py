from insight_graph.memory.embeddings import (
    EmbeddingConfig,
    EmbeddingProviderError,
    build_memory_record,
    deterministic_text_embedding,
    embed_text,
    get_embedding_provider,
    resolve_embedding_config,
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


def test_resolve_embedding_config_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_DIMENSIONS", raising=False)

    assert resolve_embedding_config() == EmbeddingConfig(
        provider="deterministic",
        base_url=None,
        api_key=None,
        model=None,
        dimensions=None,
    )


def test_resolve_embedding_config_uses_env_and_explicit_overrides(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "local_http")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", "http://env.local/embed")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_API_KEY", "env-key")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_MODEL", "env-model")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_DIMENSIONS", "3")

    assert resolve_embedding_config() == EmbeddingConfig(
        provider="local_http",
        base_url="http://env.local/embed",
        api_key="env-key",
        model="env-model",
        dimensions=3,
    )
    assert resolve_embedding_config(
        provider="openai_compatible",
        base_url="http://explicit.local",
        api_key="explicit-key",
        model="explicit-model",
        dimensions=2,
    ) == EmbeddingConfig(
        provider="openai_compatible",
        base_url="http://explicit.local",
        api_key="explicit-key",
        model="explicit-model",
        dimensions=2,
    )


def test_embed_text_deterministic_returns_existing_deterministic_embedding() -> None:
    config = EmbeddingConfig(provider="deterministic", dimensions=8)

    assert embed_text("Pricing roadmap pricing", config=config) == deterministic_text_embedding(
        "Pricing roadmap pricing", dimensions=8
    )


def test_embed_text_openai_compatible_posts_embeddings_request_with_auth() -> None:
    calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def fake_transport(url: str, payload: dict[str, object], headers: dict[str, str]) -> object:
        calls.append((url, payload, headers))
        return {"data": [{"embedding": [0.1, 0.2]}]}

    embedding = embed_text(
        "hello",
        config=EmbeddingConfig(
            provider="openai_compatible",
            base_url="http://example.test/v1/",
            api_key="secret",
            model="text-embedding-3-small",
            dimensions=2,
        ),
        transport=fake_transport,
    )

    assert embedding == [0.1, 0.2]
    assert calls == [
        (
            "http://example.test/v1/embeddings",
            {"model": "text-embedding-3-small", "input": "hello"},
            {"Authorization": "Bearer secret"},
        )
    ]


def test_embed_text_local_http_posts_to_base_url_and_parses_supported_shapes() -> None:
    calls: list[tuple[str, dict[str, object], dict[str, str]]] = []
    responses: list[object] = [
        {"embedding": [0.1, 0.2, 0.3]},
        {"data": [{"embedding": [0.4, 0.5, 0.6]}]},
    ]

    def fake_transport(url: str, payload: dict[str, object], headers: dict[str, str]) -> object:
        calls.append((url, payload, headers))
        return responses.pop(0)

    config = EmbeddingConfig(
        provider="local_http",
        base_url="http://localhost:8000/embed",
        model="local-model",
        dimensions=3,
    )

    assert embed_text("first", config=config, transport=fake_transport) == [0.1, 0.2, 0.3]
    assert embed_text("second", config=config, transport=fake_transport) == [0.4, 0.5, 0.6]
    assert calls == [
        (
            "http://localhost:8000/embed",
            {"text": "first", "model": "local-model", "dimensions": 3},
            {},
        ),
        (
            "http://localhost:8000/embed",
            {"text": "second", "model": "local-model", "dimensions": 3},
            {},
        ),
    ]


def test_resolve_embedding_config_rejects_unsupported_explicit_provider() -> None:
    try:
        resolve_embedding_config(provider="unsupported")  # type: ignore[arg-type]
    except ValueError as exc:
        assert "Unsupported embedding provider" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_embed_text_raises_for_invalid_embedding_response() -> None:
    invalid_responses: list[object] = [
        {},
        {"embedding": [1.0, "not numeric"]},
        {"embedding": [1.0, float("inf")]},
        {"embedding": [1.0]},
    ]

    for response in invalid_responses:
        try:
            embed_text(
                "hello",
                config=EmbeddingConfig(
                    provider="local_http",
                    base_url="http://localhost:8000/embed",
                    dimensions=2,
                ),
                transport=lambda _url, _payload, _headers, response=response: response,
            )
        except EmbeddingProviderError:
            pass
        else:
            raise AssertionError(f"expected EmbeddingProviderError for {response!r}")
