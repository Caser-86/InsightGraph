import pytest

from insight_graph.agents.relevance import (
    DeterministicRelevanceJudge,
    EvidenceRelevanceDecision,
    OpenAICompatibleRelevanceJudge,
    filter_relevant_evidence,
    get_relevance_judge,
    is_relevance_filter_enabled,
)
from insight_graph.llm.config import resolve_llm_config
from insight_graph.state import Evidence, LLMCallRecord, Subtask


def make_evidence(**overrides) -> Evidence:
    data = {
        "id": "e1",
        "subtask_id": "collect",
        "title": "Cursor Pricing",
        "source_url": "https://cursor.com/pricing",
        "snippet": "Cursor pricing page.",
        "verified": True,
    }
    data.update(overrides)
    return Evidence(**data)


def test_deterministic_judge_keeps_complete_verified_evidence() -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence()

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="e1",
        relevant=True,
        reason="Evidence is verified and has required content.",
    )


def test_deterministic_judge_rejects_unverified_evidence() -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence(verified=False)

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == "Evidence is not verified."


@pytest.mark.parametrize(
    ("field", "reason"),
    [
        ("title", "Evidence title is empty."),
        ("source_url", "Evidence source URL is empty."),
        ("snippet", "Evidence snippet is empty."),
    ],
)
def test_deterministic_judge_rejects_empty_required_content(field: str, reason: str) -> None:
    judge = DeterministicRelevanceJudge()
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = make_evidence(**{field: "   "})

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == reason


def test_get_relevance_judge_defaults_to_deterministic(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_RELEVANCE_JUDGE", raising=False)

    assert isinstance(get_relevance_judge(), DeterministicRelevanceJudge)


def test_get_relevance_judge_rejects_unknown_name() -> None:
    with pytest.raises(ValueError, match="Unknown relevance judge"):
        get_relevance_judge("unknown")


def test_get_relevance_judge_accepts_openai_compatible() -> None:
    judge = get_relevance_judge("openai_compatible")

    assert isinstance(judge, OpenAICompatibleRelevanceJudge)


def test_openai_compatible_config_prefers_insight_graph_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "ig-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_BASE_URL", "https://relay.example/v1")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    config = resolve_llm_config()

    assert config.api_key == "ig-key"
    assert config.base_url == "https://relay.example/v1"
    assert config.model == "relay-model"


def test_openai_compatible_config_falls_back_to_openai_env(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    config = resolve_llm_config()

    assert config.api_key == "openai-key"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4o-mini"


@pytest.mark.parametrize("value", ["1", "true", "yes", "TRUE"])
def test_relevance_filter_enabled_for_truthy_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", value)

    assert is_relevance_filter_enabled() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_relevance_filter_disabled_for_other_values(monkeypatch, value: str) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_RELEVANCE_FILTER", value)

    assert is_relevance_filter_enabled() is False



def test_filter_relevant_evidence_returns_kept_items_and_filtered_count() -> None:
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = [
        make_evidence(id="kept"),
        make_evidence(id="filtered", verified=False),
    ]

    kept, filtered_count = filter_relevant_evidence(
        "Compare AI coding agents",
        subtask,
        evidence,
        judge=DeterministicRelevanceJudge(),
    )

    assert [item.id for item in kept] == ["kept"]
    assert filtered_count == 1


class FakeOpenAIMessage:
    def __init__(self, content: str | None) -> None:
        self.content = content


class FakeOpenAIChoice:
    def __init__(self, content: str | None) -> None:
        self.message = FakeOpenAIMessage(content)


class FakeOpenAIResponse:
    def __init__(self, content: str | None) -> None:
        self.choices = [FakeOpenAIChoice(content)]


class FakeOpenAICompletions:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return FakeOpenAIResponse(self.content)


class FakeOpenAIChat:
    def __init__(self, completions: FakeOpenAICompletions) -> None:
        self.completions = completions


class FakeOpenAIClient:
    def __init__(self, completions: FakeOpenAICompletions) -> None:
        self.chat = FakeOpenAIChat(completions)


class FakeChatCompletionClient:
    def __init__(self, content: str | None = None, error: Exception | None = None) -> None:
        self.content = content
        self.error = error
        self.messages = []

    def complete_json(self, messages):
        self.messages = messages
        if self.error is not None:
            raise self.error
        return self.content


def test_openai_compatible_judge_uses_client_factory_with_base_url() -> None:
    completions = FakeOpenAICompletions(
        '{"relevant": true, "reason": "Factory client response."}'
    )
    calls = []

    def fake_client_factory(**kwargs):
        calls.append((kwargs["api_key"], kwargs.get("base_url")))
        return FakeOpenAIClient(completions)

    judge = OpenAICompatibleRelevanceJudge(
        api_key="factory-key",
        base_url="https://relay.example/v1",
        model="factory-model",
        client_factory=fake_client_factory,
    )
    evidence = make_evidence(id="factory")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is True
    assert calls == [("factory-key", "https://relay.example/v1")]


def test_filter_relevant_evidence_uses_openai_compatible_judge() -> None:
    client = FakeChatCompletionClient(
        '{"relevant": false, "reason": "LLM filtered this evidence."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
    )
    subtask = Subtask(id="collect", description="Collect pricing evidence")
    evidence = [make_evidence(id="llm-filtered")]

    kept, filtered_count = filter_relevant_evidence(
        "Compare AI coding agents",
        subtask,
        evidence,
        judge=judge,
    )

    assert kept == []
    assert filtered_count == 1


def test_openai_compatible_judge_keeps_relevant_json_response() -> None:
    client = FakeChatCompletionClient(
        '{"relevant": true, "reason": "Evidence directly matches the query."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
        model="relay-model",
    )
    evidence = make_evidence(id="openai-kept")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="openai-kept",
        relevant=True,
        reason="Evidence directly matches the query.",
    )
    assert client.messages[0].role == "system"
    assert client.messages[1].role == "user"
    assert "Compare AI coding agents" in client.messages[1].content
    assert "Cursor Pricing" in client.messages[1].content


def test_openai_compatible_judge_records_successful_llm_call() -> None:
    records: list[LLMCallRecord] = []
    client = FakeChatCompletionClient(
        '{"relevant": true, "reason": "Evidence directly matches."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
        model="relay-model",
        llm_call_log=records,
    )
    evidence = make_evidence(id="observed-kept")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is True
    assert len(records) == 1
    assert records[0].stage == "relevance"
    assert records[0].provider == "openai_compatible"
    assert records[0].model == "relay-model"
    assert records[0].success is True
    assert records[0].duration_ms >= 0
    assert records[0].error is None


def test_openai_compatible_judge_records_failed_llm_call_without_prompt_or_key() -> None:
    records: list[LLMCallRecord] = []
    client = FakeChatCompletionClient(error=RuntimeError("boom test-key"))
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
        model="relay-model",
        llm_call_log=records,
    )
    evidence = make_evidence(id="observed-failed")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert len(records) == 1
    record = records[0]
    assert record.stage == "relevance"
    assert record.success is False
    assert record.error == "RuntimeError: LLM call failed."
    serialized = record.model_dump_json()
    assert "test-key" not in serialized
    assert "Cursor Pricing" not in serialized


def test_openai_compatible_judge_filters_false_json_response() -> None:
    client = FakeChatCompletionClient(
        '{"relevant": false, "reason": "Evidence is unrelated."}'
    )
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
    )
    evidence = make_evidence(id="openai-filtered")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="openai-filtered",
        relevant=False,
        reason="Evidence is unrelated.",
    )


def test_openai_compatible_judge_fails_closed_for_missing_api_key(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    judge = OpenAICompatibleRelevanceJudge(api_key=None)
    evidence = make_evidence(id="missing-key")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="missing-key",
        relevant=False,
        reason="OpenAI-compatible relevance judge is missing an API key.",
    )


def test_openai_compatible_judge_fails_closed_for_api_error() -> None:
    client = FakeChatCompletionClient(error=RuntimeError("relay unavailable"))
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
    )
    evidence = make_evidence(id="api-error")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision.relevant is False
    assert decision.reason == "OpenAI-compatible relevance judge failed: relay unavailable"


def test_openai_compatible_judge_fails_closed_for_invalid_json() -> None:
    client = FakeChatCompletionClient("not json")
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
    )
    evidence = make_evidence(id="invalid-json")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="invalid-json",
        relevant=False,
        reason="OpenAI-compatible relevance judge returned invalid JSON.",
    )


def test_openai_compatible_judge_fails_closed_for_invalid_schema() -> None:
    client = FakeChatCompletionClient('{"reason": "Missing relevant field."}')
    judge = OpenAICompatibleRelevanceJudge(
        client=client,
        api_key="test-key",
    )
    evidence = make_evidence(id="invalid-schema")
    subtask = Subtask(id="collect", description="Collect pricing evidence")

    decision = judge.judge("Compare AI coding agents", subtask, evidence)

    assert decision == EvidenceRelevanceDecision(
        evidence_id="invalid-schema",
        relevant=False,
        reason="OpenAI-compatible relevance judge returned invalid JSON.",
    )
