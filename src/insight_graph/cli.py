import sys

import typer

from insight_graph.graph import run_research

app = typer.Typer(help="InsightGraph research workflow CLI")


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
