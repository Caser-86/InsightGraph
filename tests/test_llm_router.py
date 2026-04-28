import pytest

from insight_graph.llm import ChatMessage, LLMConfig, OpenAICompatibleChatClient, get_llm_client
from insight_graph.llm.router import select_llm_model


def base_config(model: str = "base-model") -> LLMConfig:
    return LLMConfig(
        api_key="test-key",
        base_url="https://relay.example/v1",
        model=model,
        wire_api="responses",
    )


def test_get_llm_client_preserves_model_when_router_disabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_ROUTER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    client = get_llm_client(config=base_config("configured-model"))

    assert isinstance(client, OpenAICompatibleChatClient)
    assert client.config.model == "configured-model"
    assert client.config.api_key == "test-key"
    assert client.config.base_url == "https://relay.example/v1"
    assert client.config.wire_api == "responses"


def test_rules_router_selects_fast_for_short_default_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="short")],
    )

    assert selected == "fast-model"


def test_rules_router_selects_default_for_medium_default_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_FAST_CHAR_THRESHOLD", "3")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "100")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="medium")],
    )

    assert selected == "default-model"


def test_rules_router_selects_strong_for_long_default_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "10")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="default",
        messages=[ChatMessage(role="user", content="x" * 11)],
    )

    assert selected == "strong-model"


def test_rules_router_selects_reporter_strong_without_messages(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    assert select_llm_model(base_config("base-model"), purpose="reporter") == "strong-model"


def test_rules_router_selects_analyst_default_for_short_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_FAST", "fast-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="analyst",
        messages=[ChatMessage(role="user", content="short")],
    )

    assert selected == "default-model"


def test_rules_router_selects_analyst_strong_for_long_prompt(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "10")

    selected = select_llm_model(
        base_config("base-model"),
        purpose="analyst",
        messages=[ChatMessage(role="user", content="x" * 11)],
    )

    assert selected == "strong-model"


def test_rules_router_falls_back_missing_tier_models(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL_FAST", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", raising=False)

    assert select_llm_model(base_config("base-model"), purpose="default") == "base-model"
    assert select_llm_model(base_config("base-model"), purpose="reporter") == "base-model"


def test_get_llm_client_preserves_non_model_config_when_router_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    client = get_llm_client(config=base_config("base-model"), purpose="reporter")

    assert client.config.model == "strong-model"
    assert client.config.api_key == "test-key"
    assert client.config.base_url == "https://relay.example/v1"
    assert client.config.wire_api == "responses"


def test_rules_router_rejects_unknown_router(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "mystery")

    with pytest.raises(ValueError, match="Unsupported LLM router"):
        select_llm_model(base_config("base-model"), purpose="default")


def test_rules_router_rejects_invalid_threshold(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD", "not-an-int")

    with pytest.raises(ValueError, match="INSIGHT_GRAPH_LLM_ROUTER_STRONG_CHAR_THRESHOLD"):
        select_llm_model(base_config("base-model"), purpose="default")
