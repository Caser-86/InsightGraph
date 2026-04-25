import json
import os
import sys
from enum import StrEnum
from typing import Annotated

import typer

from insight_graph.graph import run_research
from insight_graph.state import GraphState, LLMCallRecord

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
    lines.extend(
        [
            "| Stage | Provider | Model | Success | Duration ms | "
            "Input tokens | Output tokens | Total tokens | Error |",
            "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    if not records:
        lines.append("")
        lines.append("No LLM calls were recorded.")
        return "\n".join(lines)

    for record in records:
        lines.append(
            "| "
            f"{_markdown_table_cell(record.stage)} | "
            f"{_markdown_table_cell(record.provider)} | "
            f"{_markdown_table_cell(record.model)} | "
            f"{str(record.success).lower()} | "
            f"{record.duration_ms} | "
            f"{_format_optional_int(record.input_tokens)} | "
            f"{_format_optional_int(record.output_tokens)} | "
            f"{_format_optional_int(record.total_tokens)} | "
            f"{_markdown_table_cell(record.error or '')} |"
        )
    return "\n".join(lines)


def _format_optional_int(value: int | None) -> str:
    return "" if value is None else str(value)


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())


def _build_research_json_payload(state: GraphState) -> dict[str, object]:
    return {
        "user_request": state.user_request,
        "report_markdown": state.report_markdown or "",
        "findings": [finding.model_dump(mode="json") for finding in state.findings],
        "critique": state.critique.model_dump(mode="json")
        if state.critique is not None
        else None,
        "tool_call_log": [
            record.model_dump(mode="json") for record in state.tool_call_log
        ],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
    }


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
    output_json: Annotated[
        bool,
        typer.Option(
            "--output-json",
            help="Print a safe structured JSON summary instead of Markdown.",
        ),
    ] = False,
) -> None:
    """Run a research workflow and print a Markdown report."""
    _apply_research_preset(preset)
    state = run_research(query)
    if output_json:
        typer.echo(
            json.dumps(
                _build_research_json_payload(state),
                indent=2,
                ensure_ascii=False,
            )
        )
        return

    output = state.report_markdown or ""
    if show_llm_log:
        output = f"{output.rstrip()}\n\n{_format_llm_call_log(state.llm_call_log)}\n"
    typer.echo(output)


if __name__ == "__main__":
    app()
