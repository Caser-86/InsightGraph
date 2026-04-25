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
