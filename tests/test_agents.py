import pytest

from insight_graph.agents.analyst import analyze_evidence, get_analyst_provider
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import get_reporter_provider, write_report
from insight_graph.llm import ChatCompletionResult, ChatMessage
from insight_graph.llm.router import LLMRouterDecision
from insight_graph.state import CompetitiveMatrixRow, Critique, Evidence, Finding, GraphState


class FakeLLMClient:
    def __init__(
        self,
        content: object = None,
        error: Exception | None = None,
        messages: list[list[ChatMessage]] | None = None,
    ) -> None:
        self.content = content
        self.error = error
        self.messages = messages if messages is not None else []

    def complete_json(self, messages: list[ChatMessage]) -> object:
        self.messages.append(messages)
        if self.error is not None:
            raise self.error
        return self.content


class UsageLLMClient(FakeLLMClient):
    def __init__(
        self,
        content: str | None = None,
        result: ChatCompletionResult | None = None,
        error: Exception | None = None,
        messages: list[list[ChatMessage]] | None = None,
    ) -> None:
        super().__init__(content=content, error=error, messages=messages)
        self.result = result

    def complete_json_with_usage(self, messages: list[ChatMessage]) -> ChatCompletionResult:
        self.messages.append(messages)
        if self.error is not None:
            raise self.error
        if self.result is not None:
            return self.result
        return ChatCompletionResult(content=self.content)


class RecordingRouterClient(FakeLLMClient):
    def __init__(
        self,
        content: str,
        *,
        config: object | None = None,
        router_decision: LLMRouterDecision | None = None,
    ) -> None:
        super().__init__(content=content)
        if config is not None:
            self.config = config
        if router_decision is not None:
            self.router_decision = router_decision


class FakeClientConfig:
    def __init__(self, wire_api: str | None = None, model: str | None = None) -> None:
        if wire_api is not None:
            self.wire_api = wire_api
        if model is not None:
            self.model = model


def make_analyst_state() -> GraphState:
    return GraphState(
        user_request="Compare Cursor and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor lists Pro and Business pricing tiers.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Documentation",
                source_url="https://docs.github.com/en/copilot",
                snippet="GitHub Copilot documentation describes coding assistant features.",
                source_type="docs",
                verified=True,
            ),
        ],
    )


def make_matrix_state() -> GraphState:
    return GraphState(
        user_request="Compare Cursor, OpenCode, and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor lists pricing and AI coding features.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="opencode-repo",
                subtask_id="collect",
                title="OpenCode Repository",
                source_url="https://github.com/sst/opencode",
                snippet="OpenCode repository shows developer ecosystem activity.",
                source_type="github",
                verified=True,
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Documentation",
                source_url="https://docs.github.com/en/copilot",
                snippet="GitHub Copilot documentation describes coding assistant features.",
                source_type="docs",
                verified=True,
            ),
            Evidence(
                id="unverified-cursor-blog",
                subtask_id="collect",
                title="Cursor Blog",
                source_url="https://example.com/cursor",
                snippet="Unverified Cursor opinion.",
                source_type="blog",
                verified=False,
            ),
        ],
    )


def make_reporter_state() -> GraphState:
    return GraphState(
        user_request="Compare Cursor and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="cursor-pricing",
                subtask_id="collect",
                title="Cursor Pricing",
                source_url="https://cursor.com/pricing",
                snippet="Cursor lists Pro and Business pricing tiers.",
                source_type="official_site",
                verified=True,
            ),
            Evidence(
                id="copilot-docs",
                subtask_id="collect",
                title="GitHub Copilot Documentation",
                source_url="https://docs.github.com/en/copilot",
                snippet="GitHub Copilot documentation describes coding assistant features.",
                source_type="docs",
                verified=True,
            ),
            Evidence(
                id="unverified-blog",
                subtask_id="collect",
                title="Unverified Blog",
                source_url="https://example.com/blog",
                snippet="Unverified opinion.",
                source_type="blog",
                verified=False,
            ),
        ],
        findings=[
            Finding(
                title="Pricing and packaging differ",
                summary=(
                    "Cursor pricing and Copilot documentation show different packaging "
                    "signals for buyers."
                ),
                evidence_ids=["cursor-pricing", "copilot-docs"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Official product positioning signal",
                strengths=["Official/documented source coverage"],
                evidence_ids=["cursor-pricing"],
            ),
            CompetitiveMatrixRow(
                product="GitHub Copilot",
                positioning="Documented product or local research source",
                strengths=["Official/documented source coverage"],
                evidence_ids=["copilot-docs"],
            ),
        ],
        critique=Critique(passed=True, reason="Findings cite verified evidence."),
    )


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
        "INSIGHT_GRAPH_USE_NEWS_SEARCH",
        "INSIGHT_GRAPH_USE_DOCUMENT_READER",
        "INSIGHT_GRAPH_USE_READ_FILE",
        "INSIGHT_GRAPH_USE_LIST_DIRECTORY",
        "INSIGHT_GRAPH_USE_WRITE_FILE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_planner_creates_core_research_subtasks(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WRITE_FILE", raising=False)
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    descriptions = [task.description for task in updated.subtasks]
    assert len(updated.subtasks) == 4
    assert descriptions == [
        "Identify key products, companies, and scope from the user request",
        "Collect evidence about product positioning, features, pricing, and sources",
        "Analyze competitive patterns, differentiators, risks, and trends",
        "Synthesize findings into a cited research report",
    ]
    assert updated.subtasks[1].suggested_tools == ["mock_search"]


def test_planner_sets_competitive_domain_profile() -> None:
    state = GraphState(user_request="Compare Cursor and GitHub Copilot pricing")

    updated = plan_research(state)

    assert updated.domain_profile == "competitive_intel"
    assert len(updated.subtasks) == 4


def test_planner_sets_technology_domain_profile() -> None:
    state = GraphState(user_request="Analyze AI agent architecture trends")

    updated = plan_research(state)

    assert updated.domain_profile == "technology_trends"
    assert len(updated.subtasks) == 4


def test_planner_uses_generic_domain_profile_as_fallback() -> None:
    state = GraphState(user_request="Summarize this research topic")

    updated = plan_research(state)

    assert updated.domain_profile == "generic"
    assert len(updated.subtasks) == 4


def test_planner_uses_web_search_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]


def test_planner_uses_github_search_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["github_search"]


def test_planner_uses_news_search_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["news_search"]


def test_planner_uses_document_reader_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["document_reader"]


def test_planner_uses_read_file_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["read_file"]


def test_planner_uses_list_directory_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request=".")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["list_directory"]


def test_planner_uses_write_file_when_enabled(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request='{"path":"notes.md","content":"Notes."}')

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["write_file"]


def test_planner_prefers_read_file_over_write_file(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["read_file"]


def test_planner_prefers_list_directory_over_write_file(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request=".")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["list_directory"]


def test_planner_prefers_document_reader_over_write_file(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["document_reader"]


def test_planner_prefers_document_reader_over_readonly_file_tools(
    monkeypatch,
) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["document_reader"]


def test_planner_prefers_read_file_over_list_directory(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["read_file"]


def test_planner_prefers_web_search_over_readonly_file_tools(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]


def test_planner_prefers_github_search_over_readonly_file_tools(
    monkeypatch,
) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["github_search"]


def test_planner_prefers_news_search_over_readonly_file_tools(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["news_search"]


def test_planner_prefers_web_search_over_github_search(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]


def test_planner_prefers_github_search_over_news_search(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["github_search"]


def test_planner_prefers_web_search_over_news_search(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]


def test_planner_prefers_news_search_over_document_reader(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["news_search"]


def test_planner_prefers_github_search_over_document_reader(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["github_search"]


def test_planner_prefers_web_search_over_document_reader(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "1")
    state = GraphState(user_request="README.md")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]


def test_planner_ignores_non_truthy_web_search_flag(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_READ_FILE", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WRITE_FILE", "0")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["mock_search"]


def test_collector_adds_verified_mock_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_DOCUMENT_READER", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_READ_FILE", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_LIST_DIRECTORY", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WRITE_FILE", raising=False)
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) >= 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} >= {"official_site", "github"}
    assert updated.global_evidence_pool == updated.evidence_pool
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].tool_name == "mock_search"


def test_collector_adds_verified_github_search_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) == 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} == {"github"}
    assert updated.tool_call_log[0].tool_name == "github_search"


def test_collector_adds_verified_news_search_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_GITHUB_SEARCH", raising=False)
    monkeypatch.setenv("INSIGHT_GRAPH_USE_NEWS_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) == 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} == {"news"}
    assert updated.tool_call_log[0].tool_name == "news_search"


def test_get_analyst_provider_defaults_to_deterministic(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    assert get_analyst_provider() == "deterministic"


def test_get_analyst_provider_rejects_unknown_name(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="Unknown analyst provider: unknown"):
        get_analyst_provider()


def test_analyze_evidence_uses_llm_provider_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    messages: list[list[ChatMessage]] = []
    client = FakeLLMClient(
        content=(
            '{"findings": [{"title": "Pricing differentiation", '
            '"summary": "Cursor pricing and Copilot docs expose different packaging signals.", '
            '"evidence_ids": ["cursor-pricing", "copilot-docs"]}]}'
        ),
        messages=messages,
    )
    state = make_analyst_state()

    updated = analyze_evidence(state, llm_client=client)

    assert [finding.title for finding in updated.findings] == ["Pricing differentiation"]
    assert updated.findings[0].evidence_ids == ["cursor-pricing", "copilot-docs"]
    assert len(messages) == 1
    prompt = messages[0][-1].content
    assert "Compare Cursor and GitHub Copilot" in prompt
    assert "cursor-pricing" in prompt
    assert "copilot-docs" in prompt


def test_analyze_evidence_records_successful_llm_call(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")
    client = FakeLLMClient(
        content=(
            '{"findings": [{"title": "Pricing differs", '
            '"summary": "Cursor and Copilot differ.", '
            '"evidence_ids": ["cursor-pricing"]}]}'
        )
    )

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "analyst"
    assert record.provider == "llm"
    assert record.model == "relay-model"
    assert record.success is True
    assert record.duration_ms >= 0
    assert record.error is None


def test_llm_analyst_log_records_router_metadata(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_DEFAULT", "default-model")

    def fake_get_llm_client(config=None, *, purpose="default", messages=None):
        return RecordingRouterClient(
            '{"findings": [{"title": "Pricing differs", '
            '"summary": "Cursor and Copilot differ.", '
            '"evidence_ids": ["cursor-pricing"]}]}',
            config=FakeClientConfig(model="default-model"),
            router_decision=LLMRouterDecision(
                router="rules",
                tier="default",
                reason="default",
                message_chars=123,
            ),
        )

    monkeypatch.setattr("insight_graph.agents.analyst.get_llm_client", fake_get_llm_client)

    updated = analyze_evidence(make_analyst_state())

    record = updated.llm_call_log[0]
    assert record.model == "default-model"
    assert record.router == "rules"
    assert record.router_tier == "default"
    assert record.router_reason == "default"
    assert record.router_message_chars is not None


def test_llm_analyst_creates_client_with_routing_context(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    calls: list[dict] = []

    def fake_get_llm_client(config=None, *, purpose="default", messages=None):
        calls.append({"config": config, "purpose": purpose, "messages": messages})
        return RecordingRouterClient(
            '{"findings": [{"title": "Pricing differs", '
            '"summary": "Cursor and Copilot differ.", '
            '"evidence_ids": ["cursor-pricing"]}]}'
        )

    monkeypatch.setattr("insight_graph.agents.analyst.get_llm_client", fake_get_llm_client)

    updated = analyze_evidence(make_analyst_state())

    assert updated.findings[0].title == "Pricing differs"
    assert len(calls) == 1
    assert calls[0]["purpose"] == "analyst"
    assert calls[0]["messages"] is not None
    assert "cursor-pricing" in calls[0]["messages"][-1].content


def test_analyze_evidence_records_llm_wire_api(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = FakeLLMClient(
        content=(
            '{"findings": [{"title": "Pricing differs", '
            '"summary": "Cursor and Copilot differ.", '
            '"evidence_ids": ["cursor-pricing"]}]}'
        )
    )
    client.config = FakeClientConfig(wire_api="responses")

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert updated.llm_call_log[0].wire_api == "responses"


def test_analyze_evidence_records_llm_token_usage(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = UsageLLMClient(
        result=ChatCompletionResult(
            content=(
                '{"findings": [{"title": "Pricing differs", '
                '"summary": "Cursor and Copilot differ.", '
                '"evidence_ids": ["cursor-pricing"]}]}'
            ),
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
    )

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert updated.llm_call_log[0].input_tokens == 10
    assert updated.llm_call_log[0].output_tokens == 5
    assert updated.llm_call_log[0].total_tokens == 15


def test_analyze_evidence_records_tokens_for_parse_failure(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    client = UsageLLMClient(
        result=ChatCompletionResult(
            content="not json",
            input_tokens=10,
            output_tokens=5,
            total_tokens=15,
        )
    )

    updated = analyze_evidence(make_analyst_state(), llm_client=client)

    assert updated.llm_call_log[0].success is False
    assert updated.llm_call_log[0].input_tokens == 10
    assert updated.llm_call_log[0].output_tokens == 5
    assert updated.llm_call_log[0].total_tokens == 15


def test_analyze_evidence_records_failed_llm_call_without_prompt_or_response(
    monkeypatch,
) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")

    updated = analyze_evidence(
        make_analyst_state(), llm_client=FakeLLMClient(content="not json")
    )

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "analyst"
    assert record.success is False
    assert record.error == "ValueError: LLM call failed."
    serialized = record.model_dump_json()
    assert "not json" not in serialized
    assert "Cursor Pricing" not in serialized


def test_analyze_evidence_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    state = make_analyst_state()

    updated = analyze_evidence(state)

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]


def test_deterministic_analyst_builds_competitive_matrix() -> None:
    state = make_matrix_state()

    updated = analyze_evidence(state)

    products = [row.product for row in updated.competitive_matrix]
    assert products == ["Cursor", "OpenCode", "GitHub Copilot"]
    cursor: CompetitiveMatrixRow = updated.competitive_matrix[0]
    opencode = updated.competitive_matrix[1]
    copilot = updated.competitive_matrix[2]
    assert cursor.positioning == "Official product positioning signal"
    assert opencode.positioning == "Open-source or developer ecosystem signal"
    assert copilot.positioning == "Documented product or local research source"
    assert cursor.evidence_ids == ["cursor-pricing"]
    assert opencode.evidence_ids == ["opencode-repo"]
    assert copilot.evidence_ids == ["copilot-docs"]
    assert "unverified-cursor-blog" not in cursor.evidence_ids


def test_deterministic_analyst_matrix_uses_evidence_products_with_generic_request() -> None:
    state = make_matrix_state()
    state.user_request = "Compare AI coding agents"

    updated = analyze_evidence(state)

    assert [row.product for row in updated.competitive_matrix] == [
        "Cursor",
        "OpenCode",
        "GitHub Copilot",
    ]


def test_deterministic_analyst_matrix_does_not_match_unrelated_copilot() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        evidence_pool=[
            Evidence(
                id="security-copilot",
                subtask_id="collect",
                title="Security Copilot overview",
                source_url="https://example.com/security-copilot",
                snippet="Security Copilot helps security teams triage incidents.",
                source_type="official_site",
                verified=True,
            )
        ],
    )

    updated = analyze_evidence(state)

    assert [row.product for row in updated.competitive_matrix] == [
        "General market evidence"
    ]


def test_deterministic_analyst_matrix_does_not_treat_github_repo_copilot_mention_as_github_copilot(
) -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        evidence_pool=[
            Evidence(
                id="opencode-repo",
                subtask_id="collect",
                title="OpenCode Repository",
                source_url="https://github.com/sst/opencode",
                snippet="OpenCode repository mentions copilot integrations.",
                source_type="github",
                verified=True,
            )
        ],
    )

    updated = analyze_evidence(state)

    assert [row.product for row in updated.competitive_matrix] == ["OpenCode"]
    assert updated.competitive_matrix[0].evidence_ids == ["opencode-repo"]


def test_deterministic_analyst_matrix_uses_general_row_without_product_match() -> None:
    state = GraphState(
        user_request="Analyze developer tool market",
        evidence_pool=[
            Evidence(
                id="market-news",
                subtask_id="collect",
                title="AI developer tools funding",
                source_url="https://example.com/news",
                snippet="Developer tool market activity increased.",
                source_type="news",
                verified=True,
            )
        ],
    )

    updated = analyze_evidence(state)

    assert len(updated.competitive_matrix) == 1
    assert updated.competitive_matrix[0].product == "General market evidence"
    assert updated.competitive_matrix[0].evidence_ids == ["market-news"]


def test_deterministic_analyst_matrix_empty_without_verified_evidence() -> None:
    state = GraphState(
        user_request="Compare Cursor and GitHub Copilot",
        evidence_pool=[
            Evidence(
                id="unverified",
                subtask_id="collect",
                title="Cursor Blog",
                source_url="https://example.com/cursor",
                snippet="Unverified Cursor opinion.",
                source_type="blog",
                verified=False,
            )
        ],
    )

    updated = analyze_evidence(state)

    assert updated.competitive_matrix == []


def test_llm_analyst_parses_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}],'
            '"competitive_matrix":[{"product":"Cursor",'
            '"positioning":"Official product positioning signal",'
            '"strengths":["Official/documented source coverage"],'
            '"evidence_ids":["cursor-pricing"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert updated.competitive_matrix == [
        CompetitiveMatrixRow(
            product="Cursor",
            positioning="Official product positioning signal",
            strengths=["Official/documented source coverage"],
            evidence_ids=["cursor-pricing"],
        )
    ]


def test_llm_analyst_prompt_requests_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    messages: list[list[ChatMessage]] = []
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}]}'
        ),
        messages=messages,
    )

    analyze_evidence(state, llm_client=client)

    prompt = messages[0][-1].content
    assert "competitive_matrix" in prompt
    assert "product" in prompt
    assert "positioning" in prompt
    assert "strengths" in prompt
    assert "evidence_ids" in prompt


def test_llm_analyst_uses_deterministic_matrix_when_matrix_missing(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert [row.product for row in updated.competitive_matrix] == [
        "Cursor",
        "GitHub Copilot",
    ]


def test_llm_analyst_preserves_empty_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}],'
            '"competitive_matrix":[]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert updated.competitive_matrix == []


def test_llm_analyst_falls_back_for_invalid_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}],'
            '"competitive_matrix":[{"product":"Cursor",'
            '"positioning":"Official product positioning signal",'
            '"strengths":["Official/documented source coverage"],'
            '"evidence_ids":["missing-evidence"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert [row.product for row in updated.competitive_matrix] == [
        "Cursor",
        "GitHub Copilot",
    ]
    assert updated.findings[0].title == "Official sources establish baseline product positioning"


def test_llm_analyst_falls_back_when_matrix_strengths_missing(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    client = UsageLLMClient(
        content=(
            '{"findings":[{"title":"Packaging differs",'
            '"summary":"Cursor and Copilot use different packaging signals.",'
            '"evidence_ids":["cursor-pricing"]}],'
            '"competitive_matrix":[{"product":"Cursor",'
            '"positioning":"Official product positioning signal",'
            '"evidence_ids":["cursor-pricing"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert [row.product for row in updated.competitive_matrix] == [
        "Cursor",
        "GitHub Copilot",
    ]
    assert updated.findings[0].title == "Official sources establish baseline product positioning"


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        {},
        {"findings": []},
        {
            "findings": [
                {
                    "title": "Unsupported",
                    "summary": "Missing citation.",
                    "evidence_ids": ["missing"],
                }
            ]
        },
        {
            "findings": [
                {
                    "title": "Bad",
                    "summary": "Empty evidence id.",
                    "evidence_ids": [""],
                }
            ]
        },
    ],
)
def test_analyze_evidence_falls_back_for_invalid_llm_output(monkeypatch, content) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()

    updated = analyze_evidence(state, llm_client=FakeLLMClient(content=content))

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]


def test_analyze_evidence_falls_back_for_unverified_citation(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()
    state.evidence_pool.append(
        Evidence(
            id="unverified-blog",
            subtask_id="collect",
            title="Unverified Blog",
            source_url="https://example.com/blog",
            snippet="Unverified opinion.",
            source_type="blog",
            verified=False,
        )
    )
    client = FakeLLMClient(
        content=(
            '{"findings": [{"title": "Unsupported", "summary": "Cites unverified evidence.", '
            '"evidence_ids": ["unverified-blog"]}]}'
        )
    )

    updated = analyze_evidence(state, llm_client=client)

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]


def test_analyze_evidence_falls_back_for_llm_error(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")
    state = make_analyst_state()

    updated = analyze_evidence(state, llm_client=FakeLLMClient(error=RuntimeError("boom")))

    assert [finding.title for finding in updated.findings] == [
        "Official sources establish baseline product positioning",
        "Open repositories add adoption and roadmap signals",
    ]


def test_analyze_evidence_does_not_fallback_for_unexpected_bug(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_ANALYST_PROVIDER", "llm")

    def broken_build_messages(state) -> list[ChatMessage]:
        raise TypeError("bug")

    monkeypatch.setattr(
        "insight_graph.agents.analyst._build_analyst_messages",
        broken_build_messages,
    )

    with pytest.raises(TypeError, match="bug"):
        analyze_evidence(make_analyst_state(), llm_client=FakeLLMClient(content='{"findings": []}'))


def test_analysis_critic_and_reporter_create_cited_report(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    state = GraphState(user_request="Compare AI coding agents")
    state = collect_evidence(plan_research(state))

    state = analyze_evidence(state)
    state = critique_analysis(state)
    state = write_report(state)

    assert len(state.findings) == 2
    assert state.critique is not None
    assert state.critique.passed is True
    assert state.report_markdown is not None
    assert "# InsightGraph Research Report" in state.report_markdown
    assert "## References" in state.report_markdown
    assert "[1]" in state.report_markdown


def test_get_reporter_provider_defaults_to_deterministic(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    assert get_reporter_provider() == "deterministic"


def test_get_reporter_provider_rejects_unknown_name(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "unknown")

    with pytest.raises(ValueError, match="Unknown reporter provider: unknown"):
        get_reporter_provider()


def test_reporter_renders_competitive_matrix() -> None:
    state = make_reporter_state()

    updated = write_report(state)

    assert "## Competitive Matrix" in updated.report_markdown
    assert "| Product | Positioning | Strengths | Evidence |" in updated.report_markdown
    assert (
        "| Cursor | Official product positioning signal | "
        "Official/documented source coverage | [1] |"
    ) in updated.report_markdown
    assert (
        "| GitHub Copilot | Documented product or local research source | "
        "Official/documented source coverage | [2] |"
    ) in updated.report_markdown
    assert updated.report_markdown.index("## Key Findings") < updated.report_markdown.index(
        "## Competitive Matrix"
    )
    assert updated.report_markdown.index("## Competitive Matrix") < updated.report_markdown.index(
        "## Critic Assessment"
    )


def test_reporter_omits_competitive_matrix_without_citable_rows() -> None:
    state = make_reporter_state()
    state.competitive_matrix = [
        CompetitiveMatrixRow(
            product="Cursor",
            positioning="Official product positioning signal",
            strengths=["Official/documented source coverage"],
            evidence_ids=["missing-evidence"],
        )
    ]

    updated = write_report(state)

    assert "## Competitive Matrix" not in updated.report_markdown


def test_llm_reporter_inserts_competitive_matrix_when_missing(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1]."}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert "## Competitive Matrix" in updated.report_markdown
    assert (
        "| Cursor | Official product positioning signal | "
        "Official/documented source coverage | [1] |"
    ) in updated.report_markdown


def test_llm_reporter_creates_client_with_routing_context(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    calls: list[dict] = []

    def fake_get_llm_client(config=None, *, purpose="default", messages=None):
        calls.append({"config": config, "purpose": purpose, "messages": messages})
        return RecordingRouterClient(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1]."}'
        )

    monkeypatch.setattr("insight_graph.agents.reporter.get_llm_client", fake_get_llm_client)

    updated = write_report(make_reporter_state())

    assert "Cursor differs from Copilot [1]." in updated.report_markdown
    assert len(calls) == 1
    assert calls[0]["purpose"] == "reporter"
    assert calls[0]["messages"] is not None
    assert "allowed_citations" in calls[0]["messages"][-1].content


def test_llm_reporter_does_not_duplicate_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1].\\n\\n## Competitive Matrix\\n\\n'
            '| Product | Positioning | Strengths | Evidence |\\n'
            '| --- | --- | --- | --- |\\n'
            '| Cursor | Existing | Existing | [1] |"}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert updated.report_markdown.count("## Competitive Matrix") == 1
    assert "| Cursor | Existing | Existing | [1] |" in updated.report_markdown


def test_llm_reporter_replaces_uncited_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1].\\n\\n## Competitive Matrix\\n\\n'
            '| Product | Positioning | Strengths | Evidence |\\n'
            '| --- | --- | --- | --- |\\n'
            '| Cursor | Uncited | Uncited | none |"}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert "| Cursor | Uncited | Uncited | none |" not in updated.report_markdown
    assert (
        "| Cursor | Official product positioning signal | "
        "Official/documented source coverage | [1] |"
    ) in updated.report_markdown
    assert updated.report_markdown.count("## Competitive Matrix") == 1


def test_llm_reporter_replaces_mixed_uncited_competitive_matrix(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1].\\n\\n## Competitive Matrix\\n\\n'
            '| Product | Positioning | Strengths | Evidence |\\n'
            '| --- | --- | --- | --- |\\n'
            '| Cursor | Existing | Existing | [1] |\\n'
            '| Fake | Uncited | Uncited | none |"}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert "| Fake | Uncited | Uncited | none |" not in updated.report_markdown
    assert (
        "| Cursor | Official product positioning signal | "
        "Official/documented source coverage | [1] |"
    ) in updated.report_markdown
    assert updated.report_markdown.count("## Competitive Matrix") == 1


def test_llm_reporter_inserts_competitive_matrix_before_later_sections(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1].\\n\\n## Critic Assessment\\n\\n'
            'Initial critic text."}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert updated.report_markdown.index("## Key Findings") < updated.report_markdown.index(
        "## Competitive Matrix"
    )
    assert updated.report_markdown.index("## Competitive Matrix") < updated.report_markdown.index(
        "## Critic Assessment"
    )


def test_llm_reporter_detects_competitive_matrix_heading_variants(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1].\\n\\n##  competitive matrix  \\n\\n'
            '| Product | Positioning | Strengths | Evidence |\\n'
            '| --- | --- | --- | --- |\\n'
            '| Cursor | Existing | Existing | [1] |"}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert updated.report_markdown.lower().count("competitive matrix") == 1
    assert "| Cursor | Existing | Existing | [1] |" in updated.report_markdown


def test_llm_reporter_detects_competitive_matrix_atx_heading_variants(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    state = make_reporter_state()
    client = UsageLLMClient(
        content=(
            '{"markdown":"# InsightGraph Research Report\\n\\n## Key Findings\\n\\n'
            'Cursor differs from Copilot [1].\\n\\n# Competitive Matrix ##\\n\\n'
            '| Product | Positioning | Strengths | Evidence |\\n'
            '| --- | --- | --- | --- |\\n'
            '| Cursor | Existing | Existing | [1] |"}'
        )
    )

    updated = write_report(state, llm_client=client)

    assert updated.report_markdown.count("Competitive Matrix") == 1
    assert "| Cursor | Existing | Existing | [1] |" in updated.report_markdown


def test_write_report_uses_llm_provider_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    messages: list[list[ChatMessage]] = []
    client = FakeLLMClient(
        content=(
            '{"markdown": "# InsightGraph Research Report\\n\\n'
            '## Key Findings\\n\\n'
            '### Pricing and packaging differ\\n\\n'
            'Cursor and Copilot package their assistants differently for buyers [1] [2]."}'
        ),
        messages=messages,
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.report_markdown is not None
    assert "Cursor and Copilot package their assistants differently" in updated.report_markdown
    assert "## Critic Assessment" in updated.report_markdown
    assert "## References" in updated.report_markdown
    assert "[1] Cursor Pricing. https://cursor.com/pricing" in updated.report_markdown
    assert (
        "[2] GitHub Copilot Documentation. https://docs.github.com/en/copilot"
        in updated.report_markdown
    )
    assert "Unverified Blog" not in updated.report_markdown
    assert len(messages) == 1
    prompt = messages[0][-1].content
    assert "Compare Cursor and GitHub Copilot" in prompt
    assert "cursor-pricing" in prompt
    assert "copilot-docs" in prompt
    assert "unverified-blog" not in prompt
    assert "Use ASCII-only punctuation and quotes" in prompt


def test_write_report_records_successful_llm_call(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")
    client = FakeLLMClient(
        content={
            "markdown": (
                "# InsightGraph Research Report\n\n"
                "## Key Findings\n\n"
                "### Pricing and packaging differ\n\n"
                "The verified sources support this comparison [1]."
            )
        }
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "reporter"
    assert record.provider == "llm"
    assert record.model == "relay-model"
    assert record.success is True
    assert record.duration_ms >= 0
    assert record.error is None


def test_llm_reporter_log_records_router_metadata(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_ROUTER", "rules")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL_STRONG", "strong-model")

    def fake_get_llm_client(config=None, *, purpose="default", messages=None):
        return RecordingRouterClient(
            '{"markdown": "# InsightGraph Research Report\\n\\n'
            '## Key Findings\\n\\n'
            '### Pricing and packaging differ\\n\\n'
            'The verified sources support this comparison [1]."}',
            config=FakeClientConfig(model="strong-model"),
            router_decision=LLMRouterDecision(
                router="rules",
                tier="strong",
                reason="reporter_strong",
                message_chars=123,
            ),
        )

    monkeypatch.setattr("insight_graph.agents.reporter.get_llm_client", fake_get_llm_client)

    updated = write_report(make_reporter_state())

    record = updated.llm_call_log[0]
    assert record.model == "strong-model"
    assert record.router == "rules"
    assert record.router_tier == "strong"
    assert record.router_reason == "reporter_strong"
    assert record.router_message_chars is not None


def test_write_report_records_llm_wire_api(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    client = FakeLLMClient(
        content={
            "markdown": (
                "# InsightGraph Research Report\n\n"
                "## Key Findings\n\n"
                "### Pricing and packaging differ\n\n"
                "The verified sources support this comparison [1]."
            )
        }
    )
    client.config = FakeClientConfig(wire_api="responses")

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.llm_call_log[0].wire_api == "responses"


def test_write_report_records_llm_token_usage(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    client = UsageLLMClient(
        result=ChatCompletionResult(
            content=(
                '{"markdown": "# InsightGraph Research Report\\n\\n'
                '## Key Findings\\n\\n'
                '### Pricing and packaging differ\\n\\n'
                'The verified sources support this comparison [1]."}'
            ),
            input_tokens=20,
            output_tokens=8,
            total_tokens=28,
        )
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.llm_call_log[0].input_tokens == 20
    assert updated.llm_call_log[0].output_tokens == 8
    assert updated.llm_call_log[0].total_tokens == 28


def test_write_report_records_failed_llm_call_without_prompt_or_response(
    monkeypatch,
) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_MODEL", "relay-model")

    updated = write_report(make_reporter_state(), llm_client=FakeLLMClient(content="not json"))

    assert len(updated.llm_call_log) == 1
    record = updated.llm_call_log[0]
    assert record.stage == "reporter"
    assert record.success is False
    assert record.error == "ReporterFallbackError: LLM call failed."
    serialized = record.model_dump_json()
    assert "not json" not in serialized
    assert "Cursor Pricing" not in serialized


def test_write_report_strips_llm_references_and_appends_deterministic_references(
    monkeypatch,
) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    client = FakeLLMClient(
        content=(
            '{"markdown": "# InsightGraph Research Report\\n\\n'
            '## Key Findings\\n\\n'
            '### Pricing and packaging differ\\n\\n'
            'The verified sources support this comparison [1].\\n\\n'
            '## References\\n\\n'
            '[1] Fabricated source. https://example.com/fake"}'
        )
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.report_markdown is not None
    assert "Fabricated source" not in updated.report_markdown
    assert updated.report_markdown.count("## References") == 1
    assert "[1] Cursor Pricing. https://cursor.com/pricing" in updated.report_markdown
    assert (
        "[2] GitHub Copilot Documentation. https://docs.github.com/en/copilot"
        in updated.report_markdown
    )


def test_write_report_normalizes_llm_smart_punctuation(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    client = FakeLLMClient(
        content={
            "markdown": (
                "# InsightGraph Research Report\n\n"
                "## Key Findings\n\n"
                "### Pricing and packaging differ\n\n"
                "GitHub\u2019s docs and Cursor\u2019s pricing show "
                "\u201cpackaging\u201d tradeoffs\u2014not parity [1]."
            )
        }
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.report_markdown is not None
    assert "GitHub's docs" in updated.report_markdown
    assert '"packaging" tradeoffs-not parity' in updated.report_markdown
    assert "\u2019" not in updated.report_markdown
    assert "\u201c" not in updated.report_markdown
    assert "\u201d" not in updated.report_markdown
    assert "\u2014" not in updated.report_markdown


@pytest.mark.parametrize(
    "heading",
    [
        "# References",
        "  ## References",
        "### References",
        "## Sources",
        "### Sources",
        "   ### Sources",
    ],
)
def test_write_report_strips_llm_reference_and_source_heading_variants(
    monkeypatch,
    heading,
) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    client = FakeLLMClient(
        content={
            "markdown": (
                "# InsightGraph Research Report\n\n"
                "## Key Findings\n\n"
                "### Pricing and packaging differ\n\n"
                "The verified sources support this comparison [1].\n\n"
                f"{heading}\n\n"
                "[1] Fake Source. https://fake.example"
            )
        }
    )

    updated = write_report(make_reporter_state(), llm_client=client)

    assert updated.report_markdown is not None
    assert "Fake Source" not in updated.report_markdown
    assert "https://fake.example" not in updated.report_markdown
    assert "[1] Cursor Pricing. https://cursor.com/pricing" in updated.report_markdown


@pytest.mark.parametrize(
    "content",
    [
        None,
        "not json",
        {},
        {"markdown": ""},
        {"markdown": "## Key Findings\n\nMissing title [1]."},
        {"markdown": "# InsightGraph Research Report\n\nMissing required section [1]."},
        {"markdown": "# InsightGraph Research Report\n\n## Key Findings\n\nIllegal citation [99]."},
        {"markdown": "# InsightGraph Research Report\n\n## Key Findings\n\nNo citation."},
        {
            "markdown": (
                "# InsightGraph Research Report\n\n"
                "## Key Findings\n\n"
                "No citation here.\n\n"
                "## Appendix\n\n"
                "Citation appears outside key findings [1]."
            )
        },
    ],
)
def test_write_report_falls_back_for_invalid_llm_output(monkeypatch, content) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")

    updated = write_report(make_reporter_state(), llm_client=FakeLLMClient(content=content))

    assert updated.report_markdown is not None
    assert "### Pricing and packaging differ" in updated.report_markdown
    assert (
        "Cursor pricing and Copilot documentation show different packaging signals"
        in updated.report_markdown
    )
    assert "[1] Cursor Pricing. https://cursor.com/pricing" in updated.report_markdown


def test_write_report_falls_back_without_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")
    monkeypatch.delenv("INSIGHT_GRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    updated = write_report(make_reporter_state())

    assert updated.report_markdown is not None
    assert "### Pricing and packaging differ" in updated.report_markdown
    assert "## References" in updated.report_markdown


def test_write_report_falls_back_for_llm_error(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")

    updated = write_report(
        make_reporter_state(), llm_client=FakeLLMClient(error=RuntimeError("boom"))
    )

    assert updated.report_markdown is not None
    assert "### Pricing and packaging differ" in updated.report_markdown
    assert "## References" in updated.report_markdown


def test_write_report_does_not_fallback_for_unexpected_client_value_error(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")

    with pytest.raises(ValueError, match="bug"):
        write_report(make_reporter_state(), llm_client=FakeLLMClient(error=ValueError("bug")))


def test_write_report_does_not_fallback_for_unexpected_client_type_error(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")

    with pytest.raises(TypeError, match="bug"):
        write_report(make_reporter_state(), llm_client=FakeLLMClient(error=TypeError("bug")))


def test_write_report_does_not_fallback_for_unexpected_bug(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")

    def broken_build_messages(state, verified_evidence, reference_numbers) -> list[ChatMessage]:
        raise TypeError("bug")

    monkeypatch.setattr(
        "insight_graph.agents.reporter._build_reporter_messages",
        broken_build_messages,
        raising=False,
    )

    with pytest.raises(TypeError, match="bug"):
        write_report(make_reporter_state(), llm_client=FakeLLMClient(content='{"markdown": ""}'))


def test_write_report_does_not_fallback_for_unexpected_value_error(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "llm")

    def broken_build_messages(state, verified_evidence, reference_numbers) -> list[ChatMessage]:
        raise ValueError("bug")

    monkeypatch.setattr(
        "insight_graph.agents.reporter._build_reporter_messages",
        broken_build_messages,
        raising=False,
    )

    with pytest.raises(ValueError, match="bug"):
        write_report(make_reporter_state(), llm_client=FakeLLMClient(content='{"markdown": ""}'))


def test_reporter_defaults_to_deterministic_when_env_is_clear(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    state = GraphState(
        user_request="Compare AI coding agents",
        evidence_pool=[
            Evidence(
                id="verified-source",
                subtask_id="collect",
                title="Verified Source",
                source_url="https://example.com/verified",
                snippet="Verified evidence snippet.",
                verified=True,
            )
        ],
        findings=[
            Finding(
                title="Verified finding",
                summary="This finding cites verified evidence.",
                evidence_ids=["verified-source"],
            )
        ],
    )

    updated = write_report(state)

    assert updated.report_markdown is not None
    assert "# InsightGraph Research Report" in updated.report_markdown
    assert "### Verified finding" in updated.report_markdown
    assert "[1] Verified Source. https://example.com/verified" in updated.report_markdown


def test_critic_rejects_findings_without_verified_evidence() -> None:
    state = GraphState(
        user_request="Compare AI coding agents",
        evidence_pool=[
            Evidence(
                id="verified-source",
                subtask_id="collect",
                title="Verified Source",
                source_url="https://example.com/source",
                snippet="Verified evidence snippet.",
                verified=True,
            )
        ],
        findings=[
            Finding(
                title="Unsupported finding",
                summary="This finding points at an unknown citation.",
                evidence_ids=["missing-source"],
            )
        ],
    )

    updated = critique_analysis(state)

    assert updated.critique is not None
    assert updated.critique.passed is False
    assert "citation support" in updated.critique.missing_topics


def test_reporter_excludes_unverified_sources(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    state = GraphState(
        user_request="Compare AI coding agents",
        evidence_pool=[
            Evidence(
                id="verified-source",
                subtask_id="collect",
                title="Verified Source",
                source_url="https://example.com/verified",
                snippet="Verified evidence snippet.",
                verified=True,
            ),
            Evidence(
                id="unverified-source",
                subtask_id="collect",
                title="Unverified Source",
                source_url="https://example.com/unverified",
                snippet="Unverified evidence snippet.",
                verified=False,
            ),
        ],
        findings=[
            Finding(
                title="Verified finding",
                summary="This finding cites verified evidence.",
                evidence_ids=["verified-source", "unverified-source"],
            )
        ],
    )

    updated = write_report(state)

    assert updated.report_markdown is not None
    assert "https://example.com/verified" in updated.report_markdown
    assert "https://example.com/unverified" not in updated.report_markdown
    assert "[1]" in updated.report_markdown
    assert "[2]" not in updated.report_markdown
