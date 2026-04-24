from insight_graph.graph import run_research


def test_run_research_executes_full_graph() -> None:
    result = run_research("Compare Cursor, OpenCode, and GitHub Copilot")

    assert result.critique is not None
    assert result.critique.passed is True
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "https://cursor.com/pricing" in result.report_markdown
