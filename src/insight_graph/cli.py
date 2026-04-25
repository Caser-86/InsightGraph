import os
import sys
from enum import StrEnum

import typer

from insight_graph.graph import run_research

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


@app.callback()
def main() -> None:
    """InsightGraph research workflow CLI."""
    _configure_output_encoding()


@app.command()
def research(query: str) -> None:
    """Run a research workflow and print a Markdown report."""
    state = run_research(query)
    typer.echo(state.report_markdown or "")


if __name__ == "__main__":
    app()
