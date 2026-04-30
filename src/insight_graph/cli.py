import json
import os
import sys
from enum import StrEnum
from typing import Annotated

import typer

from insight_graph.eval import build_report_quality_metrics
from insight_graph.graph import run_research
from insight_graph.state import GraphState, LLMCallRecord

app = typer.Typer(help="InsightGraph research workflow CLI")


class ResearchPreset(StrEnum):
    offline = "offline"
    live_llm = "live-llm"
    live_research = "live-research"


LIVE_LLM_PRESET_DEFAULTS = {
    "INSIGHT_GRAPH_USE_WEB_SEARCH": "1",
    "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
    "INSIGHT_GRAPH_RELEVANCE_FILTER": "1",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE": "openai_compatible",
    "INSIGHT_GRAPH_ANALYST_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORTER_PROVIDER": "llm",
}

LIVE_RESEARCH_PRESET_DEFAULTS = {
    "INSIGHT_GRAPH_USE_WEB_SEARCH": "1",
    "INSIGHT_GRAPH_SEARCH_PROVIDER": "duckduckgo",
    "INSIGHT_GRAPH_SEARCH_LIMIT": "5",
    "INSIGHT_GRAPH_USE_GITHUB_SEARCH": "1",
    "INSIGHT_GRAPH_GITHUB_PROVIDER": "live",
    "INSIGHT_GRAPH_USE_SEC_FILINGS": "1",
    "INSIGHT_GRAPH_USE_SEC_FINANCIALS": "1",
    "INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION": "1",
    "INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS": "3",
    "INSIGHT_GRAPH_REPORTER_VALIDATE_URLS": "1",
    "INSIGHT_GRAPH_RELEVANCE_FILTER": "1",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE": "openai_compatible",
    "INSIGHT_GRAPH_ANALYST_PROVIDER": "llm",
    "INSIGHT_GRAPH_REPORTER_PROVIDER": "llm",
}


def _apply_research_preset(preset: ResearchPreset) -> None:
    if preset == ResearchPreset.offline:
        return

    defaults = (
        LIVE_RESEARCH_PRESET_DEFAULTS
        if preset == ResearchPreset.live_research
        else LIVE_LLM_PRESET_DEFAULTS
    )
    for name, value in defaults.items():
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
            "| Stage | Provider | Model | Router | Tier | Reason | Wire API | Success | "
            "Duration ms | Input tokens | Output tokens | Total tokens | Error |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
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
            f"{_markdown_table_cell(record.router or '-')} | "
            f"{_markdown_table_cell(record.router_tier or '-')} | "
            f"{_markdown_table_cell(record.router_reason or '-')} | "
            f"{_markdown_table_cell(record.wire_api or '')} | "
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
    quality = build_report_quality_metrics(state, state.report_markdown or "")
    return {
        "user_request": state.user_request,
        "trace_id": state.trace_id,
        "report_markdown": state.report_markdown or "",
        "findings": [finding.model_dump(mode="json") for finding in state.findings],
        "competitive_matrix": [
            row.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
            for row in state.competitive_matrix
        ],
        "critique": state.critique.model_dump(mode="json")
        if state.critique is not None
        else None,
        "tool_call_log": [
            record.model_dump(mode="json") for record in state.tool_call_log
        ],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
        "quality": quality,
        "quality_cards": _build_quality_cards(state, quality),
    }


def _build_quality_cards(state: GraphState, quality: dict[str, object]) -> dict[str, object]:
    return {
        "section_coverage_score": quality.get("section_coverage_score", 0),
        "citation_support_score": quality.get("citation_support_score", 0),
        "source_diversity_score": quality.get("source_diversity_score", 0),
        "unsupported_claim_count": quality.get("unsupported_claim_count", 0),
        "url_validation_rate": _url_validation_rate(state),
        "total_tokens": sum(record.total_tokens or 0 for record in state.llm_call_log),
        "runtime_seconds": None,
    }


def _url_validation_rate(state: GraphState) -> int:
    if not state.url_validation:
        return 100
    valid_count = sum(1 for item in state.url_validation if item.get("valid") is True)
    return round(valid_count / len(state.url_validation) * 100)


@app.callback()
def main() -> None:
    """InsightGraph research workflow CLI."""
    _configure_output_encoding()


@app.command()
def research(
    query: str,
    preset: Annotated[
        ResearchPreset,
        typer.Option("--preset", help="Runtime preset: offline, live-llm, or live-research."),
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
