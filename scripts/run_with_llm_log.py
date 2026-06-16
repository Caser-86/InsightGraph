from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO

from insight_graph.cli import (
    LIVE_LLM_PRESET_DEFAULTS,
    LIVE_RESEARCH_PRESET_DEFAULTS,
    ResearchPreset,
    _apply_research_preset,
    _configure_output_encoding,
)
from insight_graph.graph import run_research
from insight_graph.state import GraphState

MAX_SLUG_LENGTH = 60

__all__ = [
    "LIVE_LLM_PRESET_DEFAULTS",
    "LIVE_RESEARCH_PRESET_DEFAULTS",
    "build_log_payload",
    "build_log_path",
    "build_trace_path",
    "main",
    "slugify_query",
    "summarize_trace_file",
]


class LLMLogArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, stdout: TextIO, stderr: TextIO, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stdout = stdout
        self._stderr = stderr

    def print_help(self, file: TextIO | None = None) -> None:
        super().print_help(file or self._stdout)

    def exit(self, status: int = 0, message: str | None = None) -> None:
        if message:
            self._stderr.write(message)
        raise SystemExit(status)

    def error(self, message: str) -> None:
        self.print_usage(self._stderr)
        self.exit(2, f"{self.prog}: error: {message}\n")


def build_log_payload(
    state: GraphState,
    *,
    preset: str,
    trace_path: Path | None = None,
    trace_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "query": state.user_request,
        "preset": preset,
        "report_markdown_length": len(state.report_markdown or ""),
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "tool_call_log": [record.model_dump(mode="json") for record in state.tool_call_log],
        "llm_call_log": [record.model_dump(mode="json") for record in state.llm_call_log],
        "iterations": state.iterations,
    }
    if trace_path is not None:
        payload["llm_trace_path"] = str(trace_path)
        payload["llm_trace_summary"] = trace_summary or summarize_trace_file(trace_path)
    return payload


def slugify_query(query: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:MAX_SLUG_LENGTH]
    slug = slug.strip("-")
    return slug or "research"


def build_log_path(*, log_dir: Path, query: str, now: datetime) -> Path:
    timestamp = now.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    base_name = f"{timestamp}-{slugify_query(query)}"
    candidate = log_dir / f"{base_name}.json"
    suffix = 2
    while candidate.exists():
        candidate = log_dir / f"{base_name}-{suffix}.json"
        suffix += 1
    return candidate


def build_trace_path(log_path: Path) -> Path:
    return log_path.with_suffix(".jsonl")


def summarize_trace_file(trace_path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "call_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "by_stage": {},
        "by_model": {},
    }
    if not trace_path.exists():
        return summary
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        token_usage = event.get("token_usage", {})
        input_tokens = _int_value(token_usage.get("input_tokens", 0))
        output_tokens = _int_value(token_usage.get("output_tokens", 0))
        total_tokens = _int_value(token_usage.get("total_tokens", 0))
        summary["call_count"] += 1
        summary["input_tokens"] += input_tokens
        summary["output_tokens"] += output_tokens
        summary["total_tokens"] += total_tokens
        _add_group_total(summary["by_stage"], str(event.get("stage", "unknown")), total_tokens)
        _add_group_total(summary["by_model"], str(event.get("model", "unknown")), total_tokens)
    return summary


def _int_value(value: object) -> int:
    return value if isinstance(value, int) else 0


def _add_group_total(groups: dict[str, dict[str, int]], key: str, total_tokens: int) -> None:
    group = groups.setdefault(key, {"call_count": 0, "total_tokens": 0})
    group["call_count"] += 1
    group["total_tokens"] += total_tokens


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
    now_func: Callable[[], datetime] | None = None,
) -> int:
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    now_func = now_func or (lambda: datetime.now(UTC))
    _configure_output_encoding(stdout=stdout, stderr=stderr)

    parser = LLMLogArgumentParser(
        description="Run InsightGraph research and write safe LLM metadata logs.",
        stdout=stdout,
        stderr=stderr,
    )
    parser.add_argument("query", help="Research query, or '-' to read from stdin.")
    parser.add_argument(
        "--preset",
        choices=[preset.value for preset in ResearchPreset],
        default=ResearchPreset.offline.value,
        help="Runtime preset: offline, live-llm, or live-research.",
    )
    parser.add_argument(
        "--log-dir",
        default="llm_logs",
        help="Directory where the safe LLM metadata JSON log will be written.",
    )
    parser.add_argument(
        "--safe-log-only",
        action="store_true",
        help="Write only safe metadata JSON and do not enable full LLM trace logging.",
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

    log_dir = Path(args.log_dir)
    if not _prepare_log_dir(log_dir):
        stderr.write("Failed to prepare LLM log directory.\n")
        return 2

    _apply_research_preset(ResearchPreset(args.preset))
    log_path = build_log_path(log_dir=log_dir, query=query, now=now_func())
    trace_path = None if args.safe_log_only else build_trace_path(log_path)
    if trace_path is not None:
        os.environ["INSIGHT_GRAPH_LLM_TRACE_PATH"] = str(trace_path)

    try:
        state = run_research_func(query)
    except Exception:
        stderr.write("Research workflow failed.\n")
        return 1

    trace_summary = summarize_trace_file(trace_path) if trace_path is not None else None
    try:
        _write_log(
            log_path,
            build_log_payload(
                state,
                preset=args.preset,
                trace_path=trace_path,
                trace_summary=trace_summary,
            ),
        )
    except OSError:
        stderr.write("Failed to write LLM log.\n")
        return 2

    try:
        stdout.write(
            _format_stdout(
                state.report_markdown or "",
                log_path,
                trace_path=trace_path,
                trace_summary=trace_summary,
            )
        )
    except (OSError, UnicodeError):
        stderr.write("Failed to write output.\n")
        return 2

    return 0


def _read_query(query_arg: str, stdin: TextIO) -> str:
    if query_arg == "-":
        return stdin.read().strip()
    return query_arg.strip()


def _prepare_log_dir(log_dir: Path) -> bool:
    try:
        if log_dir.exists() and not log_dir.is_dir():
            return False
        log_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True


def _write_log(log_path: Path, payload: dict[str, Any]) -> None:
    with log_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _format_stdout(
    report_markdown: str,
    log_path: Path,
    *,
    trace_path: Path | None = None,
    trace_summary: dict[str, Any] | None = None,
) -> str:
    report = report_markdown.rstrip("\r\n") + "\n"
    lines = [report, f"LLM log written to: {log_path}"]
    if trace_path is not None:
        summary = trace_summary or summarize_trace_file(trace_path)
        lines.extend(
            [
                f"Full trace written to: {trace_path}",
                f"LLM calls: {summary['call_count']}",
                f"Total tokens: {summary['total_tokens']}",
                f"Input tokens: {summary['input_tokens']}",
                f"Output tokens: {summary['output_tokens']}",
            ]
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
