from insight_graph.report_quality.budgeting import ResearchBudgets, get_research_budgets


def test_get_research_budgets_uses_defaults(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_MAX_TOOL_CALLS",
        "INSIGHT_GRAPH_MAX_STEPS",
        "INSIGHT_GRAPH_MAX_FETCHES",
        "INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN",
    ]:
        monkeypatch.delenv(name, raising=False)

    assert get_research_budgets() == ResearchBudgets(
        max_tool_calls=20,
        max_steps=10,
        max_fetches=10,
        max_evidence_per_run=20,
    )


def test_get_research_budgets_reads_positive_env_values(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_CALLS", "7")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_STEPS", "8")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_FETCHES", "9")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN", "11")

    assert get_research_budgets() == ResearchBudgets(
        max_tool_calls=7,
        max_steps=8,
        max_fetches=9,
        max_evidence_per_run=11,
    )


def test_get_research_budgets_ignores_invalid_env_values(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_TOOL_CALLS", "0")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_STEPS", "-1")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_FETCHES", "invalid")
    monkeypatch.setenv("INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN", "")

    assert get_research_budgets() == ResearchBudgets(
        max_tool_calls=20,
        max_steps=10,
        max_fetches=10,
        max_evidence_per_run=20,
    )
