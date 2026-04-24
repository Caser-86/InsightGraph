from insight_graph.agents.analyst import analyze_evidence
from insight_graph.agents.collector import collect_evidence
from insight_graph.agents.critic import critique_analysis
from insight_graph.agents.planner import plan_research
from insight_graph.agents.reporter import write_report
from insight_graph.state import GraphState


def test_planner_creates_core_research_subtasks() -> None:
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


def test_collector_adds_verified_mock_evidence() -> None:
    state = GraphState(user_request="Compare Cursor and GitHub Copilot")
    state = plan_research(state)

    updated = collect_evidence(state)

    assert len(updated.evidence_pool) >= 3
    assert all(item.verified for item in updated.evidence_pool)
    assert {item.source_type for item in updated.evidence_pool} >= {"official_site", "github"}


def test_analysis_critic_and_reporter_create_cited_report() -> None:
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
