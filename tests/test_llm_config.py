import pytest

from insight_graph.llm.config import resolve_llm_config


def test_resolve_llm_config_prefers_insight_graph_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "insight-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://insight.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "insight-model")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")

    config = resolve_llm_config()

    assert config.api_key == "insight-key"
    assert config.base_url == "https://insight.example/v1"
    assert config.model == "insight-model"


def test_resolve_llm_config_falls_back_to_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://openai.example/v1")

    config = resolve_llm_config()

    assert config.api_key == "openai-key"
    assert config.base_url == "https://openai.example/v1"
    assert config.model == "gpt-4o-mini"


def test_resolve_llm_config_defaults_to_openai_compatible_provider(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_PROVIDER", raising=False)

    config = resolve_llm_config()

    assert config.provider == "openai_compatible"


def test_resolve_llm_config_qwen_provider_sets_dashscope_defaults(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    config = resolve_llm_config()

    assert config.provider == "qwen"
    assert config.api_key == "dashscope-key"
    assert config.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config.model == "qwen-plus"


def test_resolve_llm_config_qwen_provider_allows_explicit_overrides(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "custom-qwen")

    config = resolve_llm_config(
        api_key="explicit-key",
        base_url="https://explicit.example/v1",
        model="explicit-model",
    )

    assert config.provider == "qwen"
    assert config.api_key == "explicit-key"
    assert config.base_url == "https://explicit.example/v1"
    assert config.model == "explicit-model"


def test_resolve_llm_config_qwen_provider_env_overrides_defaults(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "qwen")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "insight-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "qwen-max")
    monkeypatch.setenv("DASHSCOPE_API_KEY", "dashscope-key")

    config = resolve_llm_config()

    assert config.provider == "qwen"
    assert config.api_key == "insight-key"
    assert config.base_url == "https://relay.example/v1"
    assert config.model == "qwen-max"


def test_resolve_llm_config_rejects_unknown_provider(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_PROVIDER", "not-real")

    with pytest.raises(ValueError, match="provider"):
        resolve_llm_config()


def test_resolve_llm_config_defaults_to_chat_completions(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_WIRE_API", raising=False)

    config = resolve_llm_config()

    assert config.wire_api == "chat_completions"


def test_resolve_llm_config_reads_wire_api_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_WIRE_API", "responses")

    config = resolve_llm_config()
    assert config.wire_api == "responses"


def test_resolve_llm_config_explicit_wire_api_overrides_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_WIRE_API", "responses")

    config = resolve_llm_config(wire_api="chat_completions")

    assert config.wire_api == "chat_completions"


def test_resolve_llm_config_rejects_unknown_wire_api(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_WIRE_API", "not-real")

    with pytest.raises(ValueError, match="wire_api"):
        resolve_llm_config()


def test_resolve_llm_config_explicit_args_override_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "insight-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://insight.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "insight-model")

    config = resolve_llm_config(
        api_key="explicit-key",
        base_url="https://explicit.example/v1",
        model="explicit-model",
    )

    assert config.api_key == "explicit-key"
    assert config.base_url == "https://explicit.example/v1"
    assert config.model == "explicit-model"


def test_resolve_llm_config_explicit_empty_strings_override_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "ig-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")

    config = resolve_llm_config(api_key="", base_url="", model="")

    assert config.api_key == ""
    assert config.base_url == ""
    assert config.model == ""
