import io
import json
import os

import scripts.run_research as run_research_script
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


class Cp1252Stdout:
    def write(self, value: str) -> int:
        value.encode("cp1252")
        return len(value)


class BadStdin:
    def read(self) -> str:
        raise OSError("cannot read")


def clear_live_defaults(monkeypatch) -> None:
    for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS:
        monkeypatch.delenv(name, raising=False)
    for name in run_research_script.LIVE_RESEARCH_PRESET_DEFAULTS:
        monkeypatch.delenv(name, raising=False)


def make_state(query: str) -> GraphState:
    return GraphState(
        user_request=query,
        report_markdown="# InsightGraph Research Report\n\n## References\n",
        findings=[
            Finding(
                title="Finding",
                summary="Summary",
                evidence_ids=["evidence-1"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Editor-first AI coding assistant",
                strengths=["IDE integration"],
                evidence_ids=["evidence-1"],
            )
        ],
        critique=Critique(passed=True, reason="Citations present."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=1,
            )
        ],
        llm_call_log=[
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                wire_api="responses",
                success=True,
                duration_ms=8,
            )
        ],
        iterations=1,
    )


def test_main_runs_query_and_writes_markdown():
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["Compare AI coding agents"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare AI coding agents"]
    assert stderr.getvalue() == ""
    assert stdout.getvalue() == "# InsightGraph Research Report\n\n## References\n"


def test_main_passes_document_reader_json_query_unchanged():
    observed_queries: list[str] = []
    query = '{"path":"report.md","query":"enterprise pricing"}'

    def fake_run_research(value: str) -> GraphState:
        observed_queries.append(value)
        return make_state(value)

    exit_code = run_research_script.main(
        [query],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_queries == [query]


def test_main_reads_query_from_stdin_dash():
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["-"],
        stdin=io.StringIO("  Compare from stdin\n"),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare from stdin"]
    assert "# InsightGraph Research Report" in stdout.getvalue()


def test_main_returns_two_for_stdin_read_error_without_running_workflow():
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["-"],
        stdin=BadStdin(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Failed to read query.\n"
    assert "Traceback" not in stderr.getvalue()


def test_main_rejects_empty_query_without_running_workflow():
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["  "],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research query must not be empty.\n"


def test_main_preserves_markdown_trailing_spaces():
    def fake_run_research(query: str) -> GraphState:
        state = make_state(query)
        state.report_markdown = "line  \n"
        return state

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["Compare"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert stdout.getvalue() == "line  \n"


def test_main_outputs_cli_aligned_json_payload(monkeypatch):
    monkeypatch.setenv("INSIGHT_GRAPH_LLM_API_KEY", "test-key")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["Compare AI coding agents", "--output-json"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=make_state,
    )

    assert exit_code == 0
    payload = json.loads(stdout.getvalue())
    assert payload["user_request"] == "Compare AI coding agents"
    assert payload["report_markdown"].startswith("# InsightGraph Research Report")
    assert payload["findings"][0]["title"] == "Finding"
    assert payload["competitive_matrix"][0]["product"] == "Cursor"
    assert payload["critique"]["passed"] is True
    assert payload["tool_call_log"][0]["tool_name"] == "mock_search"
    assert payload["llm_call_log"][0]["wire_api"] == "responses"
    assert payload["iterations"] == 1
    assert payload["runtime_diagnostics"]["tool_call_count"] == 1
    assert payload["runtime_diagnostics"]["llm_call_count"] == 1
    assert payload["runtime_diagnostics"]["successful_llm_call_count"] == 1
    assert payload["runtime_diagnostics"]["llm_configured"] is True


def test_main_offline_preset_does_not_apply_live_defaults(monkeypatch):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = run_research_script.main(
        ["Compare", "--preset", "offline"],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_env == {
        name: None for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS
    }


def test_main_live_llm_preset_applies_defaults(monkeypatch):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in run_research_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = run_research_script.main(
        ["Compare", "--preset", "live-llm"],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_env == run_research_script.LIVE_LLM_PRESET_DEFAULTS


def test_main_live_research_preset_applies_defaults(monkeypatch):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {
                name: os.getenv(name)
                for name in run_research_script.LIVE_RESEARCH_PRESET_DEFAULTS
            }
        )
        return make_state(query)

    exit_code = run_research_script.main(
        ["Compare", "--preset", "live-research"],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_env == run_research_script.LIVE_RESEARCH_PRESET_DEFAULTS


def test_live_research_preset_uses_production_quality_budgets() -> None:
    defaults = run_research_script.LIVE_RESEARCH_PRESET_DEFAULTS

    assert defaults["INSIGHT_GRAPH_SEARCH_LIMIT"] == "20"
    assert defaults["INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS"] == "5"
    assert defaults["INSIGHT_GRAPH_MAX_TOOL_CALLS"] == "200"
    assert defaults["INSIGHT_GRAPH_MAX_FETCHES"] == "80"
    assert defaults["INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN"] == "120"


def test_main_returns_one_for_workflow_exception_without_raw_error():
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret raw provider failure")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research workflow failed.\n"
    assert "secret raw provider failure" not in stderr.getvalue()


def test_main_returns_two_for_stdout_write_error_without_traceback():
    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare"],
        stdin=io.StringIO(),
        stdout=BadStdout(),
        stderr=stderr,
        run_research_func=make_state,
    )

    assert exit_code == 2
    assert stderr.getvalue() == "Failed to write output.\n"
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_markdown_stdout_encoding_error_without_traceback():
    def fake_run_research(query: str) -> GraphState:
        state = make_state(query)
        state.report_markdown = "snowman 雪\n"
        return state

    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare"],
        stdin=io.StringIO(),
        stdout=Cp1252Stdout(),
        stderr=stderr,
        run_research_func=fake_run_research,
    )

    assert exit_code == 2
    assert stderr.getvalue() == "Failed to write output.\n"
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_json_stdout_encoding_error_without_traceback():
    def fake_run_research(query: str) -> GraphState:
        state = make_state(query)
        state.report_markdown = "snowman 雪\n"
        return state

    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare", "--output-json"],
        stdin=io.StringIO(),
        stdout=Cp1252Stdout(),
        stderr=stderr,
        run_research_func=fake_run_research,
    )

    assert exit_code == 2
    assert stderr.getvalue() == "Failed to write output.\n"
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_unknown_option_without_traceback():
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = run_research_script.main(
        ["Compare", "--unknown"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=make_state,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_main_routes_help_to_injected_stdout_without_running_workflow():
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = run_research_script.main(
        ["--help"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
    )

    assert exit_code == 0
    assert "usage:" in stdout.getvalue()
    assert "--output-json" in stdout.getvalue()
    assert stderr.getvalue() == ""
