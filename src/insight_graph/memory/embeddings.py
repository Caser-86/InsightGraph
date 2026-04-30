import hashlib
import json
import math
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from dataclasses import replace
from typing import Callable
from typing import Literal

from insight_graph.memory.store import ResearchMemoryRecord

EmbeddingProvider = Literal["deterministic", "openai_compatible", "local_http"]
EmbeddingTransport = Callable[[str, dict[str, object], dict[str, str]], object]
_HTTP_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class EmbeddingConfig:
    provider: EmbeddingProvider = "deterministic"
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    dimensions: int | None = None


class EmbeddingProviderError(RuntimeError):
    pass


def resolve_embedding_config(
    *,
    provider: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
    dimensions: int | None = None,
) -> EmbeddingConfig:
    resolved_provider = _env_or_value(provider, "INSIGHT_GRAPH_EMBEDDING_PROVIDER", "deterministic")
    normalized_provider = resolved_provider.strip().lower()
    if normalized_provider not in {"deterministic", "openai_compatible", "local_http"}:
        raise ValueError(f"Unsupported embedding provider: {resolved_provider}")

    resolved_base_url = _env_or_value_allow_empty(base_url, "INSIGHT_GRAPH_EMBEDDING_BASE_URL", None)
    resolved_api_key = _env_or_value_allow_empty(api_key, "INSIGHT_GRAPH_EMBEDDING_API_KEY", None)
    if normalized_provider == "openai_compatible":
        if resolved_base_url is None:
            resolved_base_url = _env_or_value(None, "INSIGHT_GRAPH_LLM_BASE_URL", None)
        if resolved_api_key is None:
            resolved_api_key = _env_or_value(None, "INSIGHT_GRAPH_LLM_API_KEY", None)

    return EmbeddingConfig(
        provider=normalized_provider,  # type: ignore[arg-type]
        base_url=resolved_base_url,
        api_key=resolved_api_key,
        model=_env_or_value(model, "INSIGHT_GRAPH_EMBEDDING_MODEL", None),
        dimensions=_resolve_dimensions(dimensions),
    )


def get_embedding_provider() -> EmbeddingProvider:
    provider = os.environ.get("INSIGHT_GRAPH_EMBEDDING_PROVIDER", "deterministic").strip().lower()
    if provider in {"deterministic", "openai_compatible", "local_http"}:
        return provider  # type: ignore[return-value]
    return "deterministic"


def embed_text(
    text: str,
    *,
    config: EmbeddingConfig | None = None,
    transport: EmbeddingTransport | None = None,
) -> list[float]:
    config = config or resolve_embedding_config()
    if config.provider == "deterministic":
        return deterministic_text_embedding(text, dimensions=config.dimensions or 64)

    if not config.base_url:
        raise EmbeddingProviderError("Embedding provider requires base_url")

    transport = transport or _default_http_transport
    if config.provider == "openai_compatible":
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        response = _send_embedding_request(
            transport,
            url=f"{config.base_url.rstrip('/')}/embeddings",
            payload={"model": config.model, "input": text},
            headers=headers,
        )
        return _parse_openai_embedding_response(response, dimensions=config.dimensions)

    if config.provider == "local_http":
        response = _send_embedding_request(
            transport,
            url=config.base_url,
            payload={"text": text, "model": config.model, "dimensions": config.dimensions},
            headers={},
        )
        return _parse_local_embedding_response(response, dimensions=config.dimensions)

    raise EmbeddingProviderError(f"Unsupported embedding provider: {config.provider}")


def build_memory_record(
    *,
    memory_id: str,
    text: str,
    metadata: dict[str, object] | None = None,
    dimensions: int = 64,
) -> ResearchMemoryRecord:
    config = resolve_embedding_config()
    if config.dimensions is None and config.provider != "openai_compatible":
        config = replace(config, dimensions=dimensions)
    merged_metadata = dict(metadata or {})
    merged_metadata["embedding_provider"] = config.provider
    return ResearchMemoryRecord(
        memory_id=memory_id,
        text=text,
        embedding=embed_text(text, config=config),
        metadata=merged_metadata,
    )


def deterministic_text_embedding(text: str, *, dimensions: int = 64) -> list[float]:
    dimensions = max(dimensions, 1)
    vector = [0.0] * dimensions
    tokens = _tokenize(text)
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 2]


def _env_or_value(value: str | None, env_name: str, default: str | None) -> str | None:
    if value is not None:
        return value
    env_value = os.environ.get(env_name)
    if env_value is None:
        return default
    stripped = env_value.strip()
    return stripped or default


def _env_or_value_allow_empty(value: str | None, env_name: str, default: str | None) -> str | None:
    if value is not None:
        return value
    env_value = os.environ.get(env_name)
    if env_value is None:
        return default
    return env_value.strip()


def _resolve_dimensions(dimensions: int | None) -> int | None:
    if dimensions is not None:
        return dimensions
    env_value = os.environ.get("INSIGHT_GRAPH_EMBEDDING_DIMENSIONS")
    if env_value is None or not env_value.strip():
        return None
    return int(env_value)


def _default_http_transport(url: str, payload: dict[str, object], headers: dict[str, str]) -> object:
    try:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **headers},
            method="POST",
        )
    except Exception:
        raise EmbeddingProviderError("Embedding provider request could not be created") from None

    try:
        with urllib.request.urlopen(request, timeout=_HTTP_TIMEOUT_SECONDS) as response:
            body_bytes = response.read()
    except (urllib.error.HTTPError, urllib.error.URLError, OSError, TimeoutError):
        raise EmbeddingProviderError("Embedding provider HTTP request failed") from None

    try:
        body = body_bytes.decode("utf-8")
        return json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise EmbeddingProviderError("Embedding provider JSON response was invalid") from None


def _send_embedding_request(
    transport: EmbeddingTransport,
    *,
    url: str,
    payload: dict[str, object],
    headers: dict[str, str],
) -> object:
    try:
        return transport(url, payload, headers)
    except EmbeddingProviderError:
        raise
    except Exception:
        raise EmbeddingProviderError("Embedding provider request failed") from None


def _parse_openai_embedding_response(response: object, *, dimensions: int | None) -> list[float]:
    if not isinstance(response, dict) or not isinstance(response.get("data"), list) or not response["data"]:
        raise EmbeddingProviderError("Embedding response missing data[0].embedding")
    first = response["data"][0]
    if not isinstance(first, dict) or "embedding" not in first:
        raise EmbeddingProviderError("Embedding response missing data[0].embedding")
    return _validate_embedding_vector(first["embedding"], dimensions=dimensions)


def _parse_local_embedding_response(response: object, *, dimensions: int | None) -> list[float]:
    if isinstance(response, dict) and "embedding" in response:
        return _validate_embedding_vector(response["embedding"], dimensions=dimensions)
    return _parse_openai_embedding_response(response, dimensions=dimensions)


def _validate_embedding_vector(embedding: object, *, dimensions: int | None) -> list[float]:
    if not isinstance(embedding, list):
        raise EmbeddingProviderError("Embedding response must contain a list")
    if not embedding:
        raise EmbeddingProviderError("Embedding response contains empty vector")

    vector: list[float] = []
    for value in embedding:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise EmbeddingProviderError("Embedding response contains non-finite numeric value")
        vector.append(float(value))

    if dimensions is not None and len(vector) != dimensions:
        raise EmbeddingProviderError(
            f"Embedding response dimension mismatch: expected {dimensions}, got {len(vector)}"
        )
    return vector
