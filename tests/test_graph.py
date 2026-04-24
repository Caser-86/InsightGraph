from insight_graph.graph import run_research
from insight_graph.state import GraphState


def test_run_research_executes_full_graph() -> None:
    result = run_research("Compare Cursor, OpenCode, and GitHub Copilot")

    assert result.critique is not None
    assert result.critique.passed is True
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "https://cursor.com/pricing" in result.report_markdown


def test_run_research_stops_after_failed_retry(monkeypatch) -> None:
    import insight_graph.graph as graph_module

    def collect_no_evidence(state: GraphState) -> GraphState:
        state.evidence_pool = []
        return state

    monkeypatch.setattr(graph_module, "collect_evidence", collect_no_evidence)

    result = graph_module.run_research("Unknown product")

    assert result.critique is not None
    assert result.critique.passed is False
    assert result.iterations == 1
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "Official sources establish baseline product positioning" not in result.report_markdown
    assert "Evidence, findings, or citation support are insufficient." in result.report_markdown
