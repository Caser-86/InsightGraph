import os
import sys
from enum import StrEnum
from typing import Annotated

import typer

from insight_graph.graph import run_research
from insight_graph.state import LLMCallRecord

app = typer.Typer(help="InsightGraph research workflow CLI")


class ResearchPreset(StrEnum):
    offline = "offline"
    live_llm = "live-llm"


LIVE_LLM_PRESET_DEFAULTS = {
    "INSIGHT_GRAPH_USE_WEB_SEARCH": "1",
    "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
    "INSIGHT_GRAPH_RELEVANCE_FILTER": "1",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE": "openai_compatible",
    "INSIGHT_GRAPH_ANALYST_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORTER_PROVIDER": "llm",
}


def _apply_research_preset(preset: ResearchPreset) -> None:
    if preset == ResearchPreset.offline:
        return

    for name, value in LIVE_LLM_PRESET_DEFAULTS.items():
        os.environ.setdefault(name, value)


def _configure_output_encoding(stdout=None, stderr=None) -> None:
    for stream in (stdout or sys.stdout, stderr or sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (AttributeError, OSError, ValueError):
                pass


def _format_llm_call_log(records: list[LLMCallRecord]) -> str:
    lines = ["## LLM Call Log", ""]
    if not records:
        lines.append("No LLM calls were recorded.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Stage | Provider | Model | Success | Duration ms | Error |",
            "| --- | --- | --- | --- | ---: | --- |",
        ]
    )
    for record in records:
        lines.append(
            "| "
            f"{_markdown_table_cell(record.stage)} | "
            f"{_markdown_table_cell(record.provider)} | "
            f"{_markdown_table_cell(record.model)} | "
            f"{str(record.success).lower()} | "
            f"{record.duration_ms} | "
            f"{_markdown_table_cell(record.error or '')} |"
        )
    return "\n".join(lines)


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())


@app.callback()
def main() -> None:
    """InsightGraph research workflow CLI."""
    _configure_output_encoding()


@app.command()
def research(
    query: str,
    preset: Annotated[
        ResearchPreset,
        typer.Option("--preset", help="Runtime preset: offline or live-llm."),
    ] = ResearchPreset.offline,
    show_llm_log: Annotated[
        bool,
        typer.Option(
            "--show-llm-log",
            help="Append safe LLM call metadata after the Markdown report.",
        ),
    ] = False,
) -> None:
    """Run a research workflow and print a Markdown report."""
    _apply_research_preset(preset)
    state = run_research(query)
    output = state.report_markdown or ""
    if show_llm_log:
        output = f"{output.rstrip()}\n\n{_format_llm_call_log(state.llm_call_log)}\n"
    typer.echo(output)


if __name__ == "__main__":
    app()
