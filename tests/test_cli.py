import os

from typer.testing import CliRunner

import insight_graph.cli as cli_module
from insight_graph.cli import app
from insight_graph.state import GraphState, LLMCallRecord


def clear_llm_env(monkeypatch) -> None:
    for name in [
        "INSIGHT_GRAPH_ANALYST_PROVIDER",
        "INSIGHT_GRAPH_REPORTER_PROVIDER",
        "INSIGHT_GRAPH_LLM_API_KEY",
        "INSIGHT_GRAPH_LLM_BASE_URL",
        "INSIGHT_GRAPH_LLM_MODEL",
        "INSIGHT_GRAPH_USE_WEB_SEARCH",
        "INSIGHT_GRAPH_SEARCH_PROVIDER",
        "INSIGHT_GRAPH_RELEVANCE_FILTER",
        "INSIGHT_GRAPH_RELEVANCE_JUDGE",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
    ]:
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)


def test_cli_research_outputs_markdown_report(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# InsightGraph Research Report" in result.output
    assert "## References" in result.output


def test_configure_output_encoding_uses_utf8_when_supported() -> None:
    class FakeStream:
        def __init__(self) -> None:
            self.calls: list[dict[str, str]] = []

        def reconfigure(self, **kwargs: str) -> None:
            self.calls.append(kwargs)

    stdout = FakeStream()
    stderr = FakeStream()

    cli_module._configure_output_encoding(stdout=stdout, stderr=stderr)

    assert stdout.calls == [{"encoding": "utf-8"}]
    assert stderr.calls == [{"encoding": "utf-8"}]


def test_configure_output_encoding_ignores_unsupported_streams() -> None:
    class UnsupportedStream:
        def reconfigure(self, **kwargs: str) -> None:
            raise ValueError("unsupported")

    cli_module._configure_output_encoding(
        stdout=UnsupportedStream(), stderr=UnsupportedStream()
    )


def test_apply_live_llm_preset_sets_missing_runtime_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_llm)

    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "duckduckgo"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_FILTER"] == "1"
    assert os.environ["INSIGHT_GRAPH_RELEVANCE_JUDGE"] == "openai_compatible"
    assert os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"
    assert os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "llm"


def test_apply_live_llm_preset_preserves_explicit_env_values(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    monkeypatch.setenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")
    monkeypatch.setenv("INSIGHT_GRAPH_REPORTER_PROVIDER", "deterministic")

    cli_module._apply_research_preset(cli_module.ResearchPreset.live_llm)

    assert os.environ["INSIGHT_GRAPH_SEARCH_PROVIDER"] == "mock"
    assert os.environ["INSIGHT_GRAPH_REPORTER_PROVIDER"] == "deterministic"
    assert os.environ["INSIGHT_GRAPH_USE_WEB_SEARCH"] == "1"
    assert os.environ["INSIGHT_GRAPH_ANALYST_PROVIDER"] == "llm"


def test_apply_offline_preset_does_not_set_live_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)

    cli_module._apply_research_preset(cli_module.ResearchPreset.offline)

    assert "INSIGHT_GRAPH_USE_WEB_SEARCH" not in os.environ
    assert "INSIGHT_GRAPH_SEARCH_PROVIDER" not in os.environ
    assert "INSIGHT_GRAPH_RELEVANCE_FILTER" not in os.environ
    assert "INSIGHT_GRAPH_RELEVANCE_JUDGE" not in os.environ
    assert "INSIGHT_GRAPH_ANALYST_PROVIDER" not in os.environ
    assert "INSIGHT_GRAPH_REPORTER_PROVIDER" not in os.environ


def test_cli_live_llm_preset_applies_defaults_before_workflow(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in cli_module.LIVE_LLM_PRESET_DEFAULTS}
        )
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--preset", "live-llm"]
    )

    assert result.exit_code == 0
    assert observed_env == cli_module.LIVE_LLM_PRESET_DEFAULTS
    assert "# Report" in result.output


def test_cli_offline_preset_does_not_apply_live_defaults(monkeypatch) -> None:
    clear_llm_env(monkeypatch)
    observed_env: dict[str, str | None] = {}

    def fake_run_research(query: str) -> GraphState:
        observed_env.update(
            {name: os.getenv(name) for name in cli_module.LIVE_LLM_PRESET_DEFAULTS}
        )
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--preset", "offline"]
    )

    assert result.exit_code == 0
    assert observed_env == {name: None for name in cli_module.LIVE_LLM_PRESET_DEFAULTS}


def test_cli_rejects_unknown_preset_before_workflow(monkeypatch) -> None:
    def fail_if_called(query: str) -> GraphState:
        raise AssertionError("run_research should not be called")

    monkeypatch.setattr(cli_module, "run_research", fail_if_called)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents", "--preset", "bad"])

    assert result.exit_code != 0
    assert "bad" in result.output


def test_cli_research_does_not_show_llm_log_by_default(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay-model",
                success=True,
                duration_ms=12,
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(app, ["research", "Compare AI coding agents"])

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" not in result.output
    assert "relay-model" not in result.output


def test_cli_research_show_llm_log_appends_metadata_table(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.extend(
            [
                LLMCallRecord(
                    stage="relevance",
                    provider="openai_compatible",
                    model="relay-model",
                    success=True,
                    duration_ms=7,
                ),
                LLMCallRecord(
                    stage="reporter",
                    provider="llm",
                    model="relay-model",
                    success=False,
                    duration_ms=9,
                    error="ReporterFallbackError: LLM call failed.",
                ),
            ]
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" in result.output
    assert "| Stage | Provider | Model | Success | Duration ms | Error |" in result.output
    assert "| relevance | openai_compatible | relay-model | true | 7 |  |" in result.output
    assert (
        "| reporter | llm | relay-model | false | 9 | "
        "ReporterFallbackError: LLM call failed. |"
    ) in result.output


def test_cli_research_show_llm_log_reports_empty_log(monkeypatch) -> None:
    def fake_run_research(query: str) -> GraphState:
        return GraphState(user_request=query, report_markdown="# Report\n")

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "# Report" in result.output
    assert "## LLM Call Log" in result.output
    assert "No LLM calls were recorded." in result.output


def test_cli_research_show_llm_log_escapes_cells_and_omits_raw_payloads(
    monkeypatch,
) -> None:
    def fake_run_research(query: str) -> GraphState:
        state = GraphState(user_request=query, report_markdown="# Report\n")
        state.llm_call_log.append(
            LLMCallRecord(
                stage="analyst",
                provider="llm",
                model="relay|model\nsecond-line",
                success=False,
                duration_ms=3,
                error="RuntimeError: LLM call failed.",
            )
        )
        return state

    monkeypatch.setattr(cli_module, "run_research", fake_run_research)
    runner = CliRunner()

    result = runner.invoke(
        app, ["research", "Compare AI coding agents", "--show-llm-log"]
    )

    assert result.exit_code == 0
    assert "relay\\|model second-line" in result.output
    assert "RuntimeError: LLM call failed." in result.output
    assert "Sensitive prompt" not in result.output
    assert "Raw response" not in result.output
    assert "sk-secret" not in result.output
    assert "Authorization" not in result.output
