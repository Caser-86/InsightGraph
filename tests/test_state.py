from insight_graph import __version__
from insight_graph.cli import app
from insight_graph.state import Evidence, GraphState, Subtask


def test_package_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_cli_app_is_importable() -> None:
    assert app.info.help == "InsightGraph research workflow CLI"


def test_subtask_defaults_to_research_type() -> None:
    subtask = Subtask(id="s1", description="Compare Cursor and GitHub Copilot")

    assert subtask.subtask_type == "research"
    assert subtask.dependencies == []
    assert subtask.suggested_tools == []


def test_evidence_requires_source_url() -> None:
    evidence = Evidence(
        id="e1",
        subtask_id="s1",
        title="Cursor pricing",
        source_url="https://cursor.com/pricing",
        snippet="Cursor publishes pricing tiers on its pricing page.",
        source_type="official_site",
    )

    assert evidence.verified is False
    assert evidence.source_domain == "cursor.com"


def test_graph_state_starts_with_empty_collections() -> None:
    state = GraphState(user_request="Analyze AI coding agents")

    assert state.user_request == "Analyze AI coding agents"
    assert state.subtasks == []
    assert state.evidence_pool == []
    assert state.findings == []
    assert state.report_markdown is None
