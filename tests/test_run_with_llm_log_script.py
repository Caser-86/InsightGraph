import io
import json
import os
from datetime import UTC, datetime
from typing import Any

import scripts.run_with_llm_log as llm_log_script
from insight_graph.state import (
    CompetitiveMatrixRow,
    Critique,
    Finding,
    GraphState,
    LLMCallRecord,
    ToolCallRecord,
)

FIXED_NOW = datetime(2026, 4, 26, 12, 0, tzinfo=UTC)


class BadStdout:
    def write(self, value: str) -> int:
        raise OSError("cannot write")


class BadStdin:
    def read(self) -> str:
        raise OSError("cannot read")


def make_state(query: str, *, wire_api: str = "responses") -> GraphState:
    return GraphState(
        user_request=query,
        report_markdown="# InsightGraph Research Report\n\n## References\n",
        findings=[
            Finding(
                title="Sensitive finding title should not be logged",
                summary="Sensitive finding summary should not be logged",
                evidence_ids=["evidence-1"],
            )
        ],
        competitive_matrix=[
            CompetitiveMatrixRow(
                product="Cursor",
                positioning="Sensitive matrix positioning should not be logged",
                strengths=["Sensitive matrix strength should not be logged"],
                evidence_ids=["evidence-1"],
            )
        ],
        critique=Critique(passed=True, reason="Citations present."),
        tool_call_log=[
            ToolCallRecord(
                subtask_id="collect",
                tool_name="mock_search",
                query=query,
                evidence_count=3,
                filtered_count=0,
                success=True,
            )
        ],
        llm_call_log=[
            LLMCallRecord(
                stage="reporter",
                provider="llm",
                model="relay-model",
                wire_api=wire_api,
                success=True,
                duration_ms=12,
                input_tokens=10,
                output_tokens=20,
                total_tokens=30,
            )
        ],
        iterations=2,
    )


def clear_live_defaults(monkeypatch) -> None:
    for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS:
        monkeypatch.delenv(name, raising=False)


def fixed_now() -> datetime:
    return FIXED_NOW


def collect_json_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(collect_json_keys(child))
        return keys
    if isinstance(value, list):
        keys: set[str] = set()
        for child in value:
            keys.update(collect_json_keys(child))
        return keys
    return set()


def test_build_log_payload_contains_only_safe_metadata():
    state = make_state("Compare Cursor")

    payload = llm_log_script.build_log_payload(state, preset="offline")

    assert payload == {
        "query": "Compare Cursor",
        "preset": "offline",
        "report_markdown_length": len(state.report_markdown or ""),
        "finding_count": 1,
        "competitive_matrix_row_count": 1,
        "tool_call_log": [state.tool_call_log[0].model_dump(mode="json")],
        "llm_call_log": [state.llm_call_log[0].model_dump(mode="json")],
        "iterations": 2,
    }


def test_build_log_payload_omits_sensitive_fields():
    state = make_state("Compare Cursor", wire_api="chat_completions")
    payload = llm_log_script.build_log_payload(state, preset="offline")

    payload_keys = collect_json_keys(payload)
    payload_text = str(payload).lower()

    assert "report_markdown" not in payload
    assert payload["llm_call_log"][0]["wire_api"] == "chat_completions"
    assert "# insightgraph research report" not in payload_text
    assert "sensitive finding" not in payload_text
    assert "sensitive matrix" not in payload_text
    assert "evidence_pool" not in payload_keys
    assert "prompt" not in payload_keys
    assert "completion" not in payload_keys
    assert "api_key" not in payload_keys


def test_slugify_query_limits_and_normalizes_filename_component():
    slug = llm_log_script.slugify_query("  Cursor + OpenCode / GitHub Copilot!!!  ")

    assert slug == "cursor-opencode-github-copilot"
    assert len(llm_log_script.slugify_query("a" * 200)) == 60
    assert llm_log_script.slugify_query("!!!") == "research"


def test_build_log_path_uses_utc_timestamp_slug_and_collision_suffix(tmp_path):
    first = llm_log_script.build_log_path(
        log_dir=tmp_path,
        query="Compare Cursor, OpenCode, and GitHub Copilot",
        now=FIXED_NOW,
    )
    first.write_text("existing", encoding="utf-8")
    second = llm_log_script.build_log_path(
        log_dir=tmp_path,
        query="Compare Cursor, OpenCode, and GitHub Copilot",
        now=FIXED_NOW,
    )

    assert first.name == "20260426T120000Z-compare-cursor-opencode-and-github-copilot.json"
    assert second.name == "20260426T120000Z-compare-cursor-opencode-and-github-copilot-2.json"


def test_main_runs_query_writes_markdown_and_log_file(tmp_path):
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare Cursor", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare Cursor"]
    assert stderr.getvalue() == ""
    assert stdout.getvalue().startswith("# InsightGraph Research Report")
    assert "LLM log written to:" in stdout.getvalue()
    log_files = list(tmp_path.glob("*.json"))
    assert [path.name for path in log_files] == ["20260426T120000Z-compare-cursor.json"]
    payload = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert payload["query"] == "Compare Cursor"
    assert payload["preset"] == "offline"
    assert payload["llm_call_log"][0]["wire_api"] == "responses"


def test_main_passes_document_reader_json_query_and_logs_metadata(tmp_path):
    observed_queries: list[str] = []
    query = '{"path":"report.md","query":"enterprise pricing"}'

    def fake_run_research(value: str) -> GraphState:
        observed_queries.append(value)
        return make_state(value)

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        [query, "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_queries == [query]
    assert stderr.getvalue() == ""
    assert "LLM log written to:" in stdout.getvalue()
    log_files = list(tmp_path.glob("*.json"))
    assert len(log_files) == 1
    payload = json.loads(log_files[0].read_text(encoding="utf-8"))
    assert payload["query"] == query
    assert payload["preset"] == "offline"
    assert "tool_call_log" in payload
    assert "llm_call_log" in payload


def test_main_reads_query_from_stdin_dash(tmp_path):
    observed_queries: list[str] = []

    def fake_run_research(query: str) -> GraphState:
        observed_queries.append(query)
        return make_state(query)

    exit_code = llm_log_script.main(
        ["-", "--log-dir", str(tmp_path)],
        stdin=io.StringIO("  Compare from stdin\n"),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_queries == ["Compare from stdin"]


def test_main_rejects_empty_query_without_running_workflow(tmp_path):
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["  ", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research query must not be empty.\n"
    assert list(tmp_path.glob("*.json")) == []


def test_main_offline_preset_does_not_apply_live_defaults(monkeypatch, tmp_path):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = llm_log_script.main(
        ["Compare", "--preset", "offline", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_env == {name: None for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS}


def test_main_live_llm_preset_applies_defaults(monkeypatch, tmp_path):
    clear_live_defaults(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in llm_log_script.LIVE_LLM_PRESET_DEFAULTS}
        )
        return make_state(query)

    exit_code = llm_log_script.main(
        ["Compare", "--preset", "live-llm", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 0
    assert observed_env == llm_log_script.LIVE_LLM_PRESET_DEFAULTS


def test_main_workflow_exception_returns_one_without_log_or_raw_error(tmp_path):
    def fail_run_research(query: str) -> GraphState:
        raise RuntimeError("secret provider details")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 1
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Research workflow failed.\n"
    assert "secret provider details" not in stderr.getvalue()
    assert list(tmp_path.glob("*.json")) == []


def test_main_log_dir_as_file_returns_two_without_running_workflow(tmp_path):
    log_path = tmp_path / "llm_logs"
    log_path.write_text("not a directory", encoding="utf-8")

    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--log-dir", str(log_path)],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Failed to prepare LLM log directory.\n"


def test_main_stdin_read_failure_returns_two_without_workflow(tmp_path):
    def fail_run_research(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["-", "--log-dir", str(tmp_path)],
        stdin=BadStdin(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=fail_run_research,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "Failed to read query.\n"


def test_main_stdout_write_failure_returns_two_after_log_written(tmp_path):
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--log-dir", str(tmp_path)],
        stdin=io.StringIO(),
        stdout=BadStdout(),
        stderr=stderr,
        run_research_func=make_state,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stderr.getvalue() == "Failed to write output.\n"
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_main_unknown_option_returns_two_without_traceback():
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = llm_log_script.main(
        ["Compare", "--unknown"],
        stdin=io.StringIO(),
        stdout=stdout,
        stderr=stderr,
        run_research_func=make_state,
        now_func=fixed_now,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
