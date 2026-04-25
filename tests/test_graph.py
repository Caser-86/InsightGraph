from insight_graph.graph import run_research
from insight_graph.state import GraphState


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


def clear_planner_tool_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_USE_WEB_SEARCH",
        "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
        "INSIGHT_GRAPH_USE_NEWS_SEARCH",
        "INSIGHT_GRAPH_USE_DOCUMENT_READER",
        "INSIGHT_GRAPH_USE_READ_FILE",
        "INSIGHT_GRAPH_USE_LIST_DIRECTORY",
    ]:
        monkeypatch.delenv(name, raising=False)


def test_run_research_executes_full_graph(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)

    result = run_research("Compare Cursor, OpenCode, and GitHub Copilot")

    assert result.critique is not None
    assert result.critique.passed is True
    assert result.report_markdown is not None
    assert "# InsightGraph Research Report" in result.report_markdown
    assert "https://cursor.com/pricing" in result.report_markdown
    assert result.llm_call_log == []


def test_run_research_stops_after_failed_retry(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    clear_planner_tool_env(monkeypatch)
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
