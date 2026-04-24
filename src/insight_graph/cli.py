import typer

from insight_graph.graph import run_research

app = typer.Typer(help="InsightGraph research workflow CLI")


@app.callback()
def main() -> None:
    """InsightGraph research workflow CLI."""


@app.command()
def research(query: str) -> None:
    """Run a research workflow and print a Markdown report."""
    state = run_research(query)
    typer.echo(state.report_markdown or "")


if __name__ == "__main__":
    app()
