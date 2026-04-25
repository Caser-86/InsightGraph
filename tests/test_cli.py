import os

from typer.testing import CliRunner

import insight_graph.cli as cli_module
from insight_graph.cli import app


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
        monkeypatch.delenv(name, raising=False)


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
