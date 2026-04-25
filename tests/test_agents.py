import pytest

from insight_graph.agents.analyst import analyze_evidence, get_analyst_provider
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import get_reporter_provider, write_report
from insight_graph.llm import ChatCompletionResult, ChatMessage
from insight_graph.state import Critique, Evidence, Finding, GraphState


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
        critique=Critique(passed=True, reason="Findings cite verified evidence."),
    )


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
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
