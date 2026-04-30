import json
import urllib.error

import insight_graph.memory.embeddings as embeddings
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
    assert record.embedding == deterministic_text_embedding("Grounded finding about pricing.", dimensions=8)


def test_build_memory_record_uses_configured_embedding_provider(monkeypatch) -> None:
    calls: list[tuple[str, EmbeddingConfig | None]] = []

    def fake_embed_text(text: str, *, config: EmbeddingConfig | None = None) -> list[float]:
        calls.append((text, config))
        return [0.1, 0.2, 0.3]

    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "local_http")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", "http://localhost:8000/embed")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_MODEL", "local-model")
    monkeypatch.setattr(embeddings, "embed_text", fake_embed_text)

    record = build_memory_record(
        memory_id="m2",
        text="Grounded finding about retention.",
        metadata={"run_id": "run-2"},
        dimensions=3,
    )

    assert record.embedding == [0.1, 0.2, 0.3]
    assert record.metadata == {"run_id": "run-2", "embedding_provider": "local_http"}
    assert calls == [
        (
            "Grounded finding about retention.",
            EmbeddingConfig(
                provider="local_http",
                base_url="http://localhost:8000/embed",
                api_key=None,
                model="local-model",
                dimensions=3,
            ),
        )
    ]


def test_build_memory_record_does_not_force_dimensions_for_openai_compatible(monkeypatch) -> None:
    calls: list[EmbeddingConfig | None] = []

    def fake_embed_text(_text: str, *, config: EmbeddingConfig | None = None) -> list[float]:
        calls.append(config)
        return [0.1, 0.2, 0.3, 0.4]

    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", "http://example.test/v1")
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_DIMENSIONS", raising=False)
    monkeypatch.setattr(embeddings, "embed_text", fake_embed_text)

    record = build_memory_record(
        memory_id="m3",
        text="Grounded finding about expansion.",
        dimensions=3,
    )

    assert record.embedding == [0.1, 0.2, 0.3, 0.4]
    assert record.metadata == {"embedding_provider": "openai_compatible"}
    assert calls == [
        EmbeddingConfig(
            provider="openai_compatible",
            base_url="http://example.test/v1",
            api_key=None,
            model=None,
            dimensions=None,
        )
    ]


def test_build_memory_record_uses_configured_dimensions_for_openai_compatible(monkeypatch) -> None:
    calls: list[EmbeddingConfig | None] = []

    def fake_embed_text(_text: str, *, config: EmbeddingConfig | None = None) -> list[float]:
        calls.append(config)
        return [0.1, 0.2]

    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", "http://example.test/v1")
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_DIMENSIONS", "2")
    monkeypatch.setattr(embeddings, "embed_text", fake_embed_text)

    build_memory_record(
        memory_id="m4",
        text="Grounded finding about conversion.",
        dimensions=3,
    )

    assert calls == [
        EmbeddingConfig(
            provider="openai_compatible",
            base_url="http://example.test/v1",
            api_key=None,
            model=None,
            dimensions=2,
        )
    ]


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


def test_openai_compatible_config_falls_back_to_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_EMBEDDING_API_KEY", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "http://llm.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "llm-key")

    assert resolve_embedding_config() == EmbeddingConfig(
        provider="openai_compatible",
        base_url="http://llm.example/v1",
        api_key="llm-key",
        model=None,
        dimensions=None,
    )


def test_embedding_specific_env_takes_precedence_over_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", "http://embedding.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_API_KEY", "embedding-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "http://llm.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "llm-key")

    config = resolve_embedding_config()

    assert config.base_url == "http://embedding.example/v1"
    assert config.api_key == "embedding-key"


def test_empty_explicit_openai_values_do_not_fall_back_to_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "http://llm.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "llm-key")

    config = resolve_embedding_config(provider="openai_compatible", base_url="", api_key="")

    assert config.base_url == ""
    assert config.api_key == ""


def test_empty_embedding_env_values_do_not_fall_back_to_llm_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_BASE_URL", "")
    monkeypatch.setenv("INSIGHT_GRAPH_EMBEDDING_API_KEY", "")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "http://llm.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "llm-key")

    config = resolve_embedding_config()

    assert config.base_url == ""
    assert config.api_key == ""


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


def test_embed_text_openai_compatible_requires_data_embedding_shape() -> None:
    def fake_transport(_url: str, _payload: dict[str, object], _headers: dict[str, str]) -> object:
        return {"embedding": [0.1, 0.2]}

    try:
        embed_text(
            "hello",
            config=EmbeddingConfig(
                provider="openai_compatible",
                base_url="http://example.test/v1",
                dimensions=2,
            ),
            transport=fake_transport,
        )
    except EmbeddingProviderError as exc:
        assert "data[0].embedding" in str(exc)
    else:
        raise AssertionError("expected EmbeddingProviderError")


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
        {"embedding": []},
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


def test_embed_text_rejects_empty_embedding_without_dimensions() -> None:
    try:
        embed_text(
            "hello",
            config=EmbeddingConfig(provider="local_http", base_url="http://localhost:8000/embed"),
            transport=lambda _url, _payload, _headers: {"embedding": []},
        )
    except EmbeddingProviderError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("expected EmbeddingProviderError")


def test_embed_text_wraps_transport_errors_safely() -> None:
    def fake_transport(_url: str, _payload: dict[str, object], _headers: dict[str, str]) -> object:
        raise RuntimeError("boom secret-token")

    try:
        embed_text(
            "hello",
            config=EmbeddingConfig(provider="local_http", base_url="http://localhost:8000/embed"),
            transport=fake_transport,
        )
    except EmbeddingProviderError as exc:
        assert "Embedding provider request failed" in str(exc)
        assert "secret-token" not in str(exc)
        assert exc.__cause__ is None
        assert exc.__suppress_context__ is True
    else:
        raise AssertionError("expected EmbeddingProviderError")


def test_default_http_transport_uses_timeout_and_wraps_errors(monkeypatch) -> None:
    calls: list[object] = []

    def fake_urlopen(request: object, *, timeout: float) -> object:
        calls.append(timeout)
        raise urllib.error.URLError("api-key-secret")

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", fake_urlopen)

    try:
        embeddings._default_http_transport("http://example.test/embed", {"text": "hello"}, {})
    except EmbeddingProviderError as exc:
        assert "Embedding provider HTTP request failed" in str(exc)
        assert "api-key-secret" not in str(exc)
        assert exc.__cause__ is None
        assert exc.__suppress_context__ is True
    else:
        raise AssertionError("expected EmbeddingProviderError")

    assert calls == [10.0]


def test_default_http_transport_wraps_invalid_json_safely(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def read(self) -> bytes:
            return b"not json containing secret-token"

    monkeypatch.setattr(
        embeddings.urllib.request,
        "urlopen",
        lambda _request, *, timeout: FakeResponse(),
    )

    try:
        embeddings._default_http_transport("http://example.test/embed", {"text": "hello"}, {})
    except EmbeddingProviderError as exc:
        assert "Embedding provider JSON response was invalid" in str(exc)
        assert "secret-token" not in str(exc)
        assert exc.__cause__ is None
        assert exc.__suppress_context__ is True
    else:
        raise AssertionError("expected EmbeddingProviderError")


def test_default_http_transport_wraps_invalid_utf8_safely(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def read(self) -> bytes:
            return b"\xffsecret-token"

    monkeypatch.setattr(
        embeddings.urllib.request,
        "urlopen",
        lambda _request, *, timeout: FakeResponse(),
    )

    try:
        embeddings._default_http_transport("http://example.test/embed", {"text": "hello"}, {})
    except EmbeddingProviderError as exc:
        assert "Embedding provider JSON response was invalid" in str(exc)
        assert "secret-token" not in str(exc)
        assert exc.__cause__ is None
        assert exc.__suppress_context__ is True
    else:
        raise AssertionError("expected EmbeddingProviderError")


def test_default_http_transport_parses_json_response(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"embedding": [0.1]}'

    captured: dict[str, object] = {}

    def fake_urlopen(request: object, *, timeout: float) -> object:
        captured["timeout"] = timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(embeddings.urllib.request, "urlopen", fake_urlopen)

    assert embeddings._default_http_transport("http://example.test/embed", {"text": "hello"}, {}) == {
        "embedding": [0.1]
    }
    assert captured == {"timeout": 10.0, "payload": {"text": "hello"}}
