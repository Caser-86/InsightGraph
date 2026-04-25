import pytest

from insight_graph.agents.analyst import analyze_evidence, get_analyst_provider
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import write_report
from insight_graph.llm import ChatMessage
from insight_graph.state import Evidence, Finding, GraphState


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


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_planner_creates_core_research_subtasks(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
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


def test_planner_uses_web_search_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "1")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["web_search"]


def test_planner_ignores_non_truthy_web_search_flag(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "0")
    state = GraphState(user_request="Compare Cursor, OpenCode, and Claude Code")

    updated = plan_research(state)

    assert updated.subtasks[1].suggested_tools == ["mock_search"]


def test_collector_adds_verified_mock_evidence(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_USE_WEB_SEARCH", raising=False)
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) >= 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} >= {"official_site", "github"}
    assert updated.global_evidence_pool == updated.evidence_pool
    assert len(updated.tool_call_log) == 1
    assert updated.tool_call_log[0].tool_name == "mock_search"


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


def test_reporter_excludes_unverified_sources() -> None:
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
