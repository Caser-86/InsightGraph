from insight_graph.report_quality.budgeting import (
    ResearchBudgets,
    can_start_llm_call,
    get_research_budgets,
    used_llm_tokens,
)
from insight_graph.report_quality.intensity import (
    apply_report_intensity_defaults,
    get_report_intensity_config,
)
from insight_graph.state import GraphState, LLMCallRecord


def test_get_research_budgets_uses_defaults(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_MAX_TOOL_CALLS",
        "INSIGHT_GRAPH_MAX_STEPS",
        "INSIGHT_GRAPH_MAX_FETCHES",
        "INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN",
        "INSIGHT_GRAPH_MAX_TOKENS",
        "INSIGHT_GRAPH_REPORT_INTENSITY",
    ]:
        monkeypatch.delenv(name, raising=False)

    assert get_research_budgets() == ResearchBudgets(
        max_tool_calls=200,
        max_steps=10,
        max_fetches=80,
        max_evidence_per_run=120,
        max_tokens=500_000,
    )


def test_get_research_budgets_reads_positive_env_values(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_CALLS", "7")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_STEPS", "8")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_FETCHES", "9")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN", "11")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOKENS", "123")

    assert get_research_budgets() == ResearchBudgets(
        max_tool_calls=7,
        max_steps=8,
        max_fetches=9,
        max_evidence_per_run=11,
        max_tokens=123,
    )


def test_get_research_budgets_ignores_invalid_env_values(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_CALLS", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_STEPS", "-1")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_FETCHES", "invalid")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN", "")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOKENS", "0")

    assert get_research_budgets() == ResearchBudgets(
        max_tool_calls=200,
        max_steps=10,
        max_fetches=80,
        max_evidence_per_run=120,
        max_tokens=500_000,
    )


def test_report_intensity_configs_define_budget_profiles() -> None:
    concise = get_report_intensity_config("concise")
    standard = get_report_intensity_config("standard")
    deep = get_report_intensity_config("deep")
    deep_plus = get_report_intensity_config("deep-plus")

    assert concise.max_tokens < standard.max_tokens < deep.max_tokens < deep_plus.max_tokens
    assert (
        concise.max_evidence_per_run
        < standard.max_evidence_per_run
        < deep.max_evidence_per_run
        < deep_plus.max_evidence_per_run
    )
    assert standard.name == "standard"


def test_apply_report_intensity_defaults_can_override_budget_env(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOKENS", "123")

    apply_report_intensity_defaults("deep", overwrite=True)

    assert get_research_budgets().max_tokens == 2_000_000
    assert get_research_budgets().max_tool_calls == 320
    assert get_research_budgets().max_fetches == 140


def test_used_llm_tokens_sums_known_total_tokens() -> None:
    state = GraphState(
        user_request="q",
        llm_call_log=[
            LLMCallRecord(
                stage="analyst",
                provider="p",
                model="m",
                success=True,
                duration_ms=1,
                total_tokens=7,
            ),
            LLMCallRecord(
                stage="reporter",
                provider="p",
                model="m",
                success=True,
                duration_ms=1,
                total_tokens=None,
            ),
            LLMCallRecord(
                stage="critic",
                provider="p",
                model="m",
                success=True,
                duration_ms=1,
                total_tokens=5,
            ),
        ],
    )

    assert used_llm_tokens(state) == 12


def test_can_start_llm_call_respects_token_budget(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOKENS", "10")
    state = GraphState(
        user_request="q",
        llm_call_log=[
            LLMCallRecord(
                stage="analyst",
                provider="p",
                model="m",
                success=True,
                duration_ms=1,
                total_tokens=10,
            )
        ],
    )

    assert can_start_llm_call(state) is False

    state.llm_call_log[0].total_tokens = 9
    assert can_start_llm_call(state) is True
