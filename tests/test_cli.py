from typer.testing import CliRunner

from insight_graph.cli import app


def test_cli_research_outputs_markdown_report() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# InsightGraph Research Report" in result.output
    assert "## References" in result.output
