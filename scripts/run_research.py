from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from typing import Any, TextIO

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    ResearchPreset,
    _apply_research_preset,
    _build_research_json_payload,
)
from insight_graph.graph import run_research
from insight_graph.state import GraphState

__all__ = ["LIVE_LLM_PRESET_DEFAULTS", "main"]


class ResearchArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, stderr: TextIO, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stderr = stderr

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._stderr.write(message)
        raise SystemExit(status)

    def error(self, message: str) -> None:
        self.print_usage(self._stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr

    parser = ResearchArgumentParser(
        description="Run an InsightGraph research workflow.",
        stderr=stderr,
    )
    parser.add_argument("query", help="Research query, or '-' to read from stdin.")
    parser.add_argument(
        "--preset",
        choices=[preset.value for preset in ResearchPreset],
        default=ResearchPreset.offline.value,
        help="Runtime preset: offline or live-llm.",
    )
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Print a safe structured JSON summary instead of Markdown.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        query = _read_query(args.query, stdin)
    except OSError:
        stderr.write("Failed to read query.\n")
        return 2

    if not query:
        stderr.write("Research query must not be empty.\n")
        return 2

    _apply_research_preset(ResearchPreset(args.preset))

    try:
        state = run_research_func(query)
    except Exception:
        stderr.write("Research workflow failed.\n")
        return 1

    try:
        if args.output_json:
            json.dump(
                _build_research_json_payload(state),
                stdout,
                indent=2,
                ensure_ascii=False,
            )
            stdout.write("\n")
        else:
            stdout.write(_format_markdown_output(state.report_markdown or ""))
    except OSError:
        stderr.write("Failed to write output.\n")
        return 2

    return 0


def _read_query(query_arg: str, stdin: TextIO) -> str:
    if query_arg == "-":
        return stdin.read().strip()
    return query_arg.strip()


def _format_markdown_output(report_markdown: str) -> str:
    return report_markdown.rstrip() + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
