import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from typing import Any

from insight_graph.graph import run_research
from insight_graph.state import GraphState

BENCHMARK_CASES = [
    "Compare Cursor, OpenCode, and GitHub Copilot",
    "Analyze AI coding agents market positioning",
    "Compare Claude Code, Codeium, and Windsurf",
]

OFFLINE_ENV_VARS = [
    "INSIGHT_GRAPH_ANALYST_PROVIDER",
    "INSIGHT_GRAPH_REPORTER_PROVIDER",
    "INSIGHT_GRAPH_LLM_API_KEY",
    "INSIGHT_GRAPH_LLM_BASE_URL",
    "INSIGHT_GRAPH_LLM_MODEL",
    "INSIGHT_GRAPH_USE_WEB_SEARCH",
    "INSIGHT_GRAPH_USE_GITHUB_SEARCH",
    "INSIGHT_GRAPH_USE_NEWS_SEARCH",
    "INSIGHT_GRAPH_USE_DOCUMENT_READER",
    "INSIGHT_GRAPH_USE_READ_FILE",
    "INSIGHT_GRAPH_USE_LIST_DIRECTORY",
    "INSIGHT_GRAPH_USE_WRITE_FILE",
    "INSIGHT_GRAPH_SEARCH_PROVIDER",
    "INSIGHT_GRAPH_SEARCH_LIMIT",
    "INSIGHT_GRAPH_RELEVANCE_FILTER",
    "INSIGHT_GRAPH_RELEVANCE_JUDGE",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
]

REFERENCE_LINE_PATTERN = re.compile(r"(?m)^\[\d+]\s+")
SAFE_WORKFLOW_ERROR = "Research workflow failed."


@contextmanager
def offline_environment() -> Iterable[None]:
    previous_values = {name: os.environ.get(name) for name in OFFLINE_ENV_VARS}
    try:
        for name in OFFLINE_ENV_VARS:
            os.environ.pop(name, None)
        yield
    finally:
        for name, value in previous_values.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def build_benchmark_payload(
    cases: list[str] | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    case_queries = cases if cases is not None else BENCHMARK_CASES
    case_results = [_run_case(query, run_research_func) for query in case_queries]
    return {"cases": case_results, "summary": _build_summary(case_results)}


def _run_case(
    query: str,
    run_research_func: Callable[[str], GraphState],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with offline_environment():
            state = run_research_func(query)
    except Exception:
        duration_ms = _duration_ms_since(started)
        return _error_case_result(query, duration_ms)

    duration_ms = _duration_ms_since(started)
    return _case_result_from_state(query, duration_ms, state)


def _duration_ms_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _case_result_from_state(query: str, duration_ms: int, state: GraphState) -> dict[str, Any]:
    report_markdown = state.report_markdown or ""
    return {
        "query": query,
        "duration_ms": duration_ms,
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "reference_count": count_references(report_markdown),
        "tool_call_count": len(state.tool_call_log),
        "llm_call_count": len(state.llm_call_log),
        "critique_passed": bool(state.critique and state.critique.passed),
        "report_has_competitive_matrix": "## Competitive Matrix" in report_markdown,
    }


def _error_case_result(query: str, duration_ms: int) -> dict[str, Any]:
    return {
        "query": query,
        "duration_ms": duration_ms,
        "finding_count": 0,
        "competitive_matrix_row_count": 0,
        "reference_count": 0,
        "tool_call_count": 0,
        "llm_call_count": 0,
        "critique_passed": False,
        "report_has_competitive_matrix": False,
        "error": SAFE_WORKFLOW_ERROR,
    }


def count_references(report_markdown: str) -> int:
    references_start = report_markdown.find("## References")
    if references_start == -1:
        return 0
    references_section = report_markdown[references_start:]
    return len(REFERENCE_LINE_PATTERN.findall(references_section))


def _build_summary(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(case_results),
        "total_duration_ms": sum(int(item["duration_ms"]) for item in case_results),
        "all_critique_passed": all(bool(item["critique_passed"]) for item in case_results),
        "total_findings": sum(int(item["finding_count"]) for item in case_results),
        "total_competitive_matrix_rows": sum(
            int(item["competitive_matrix_row_count"]) for item in case_results
        ),
        "total_references": sum(int(item["reference_count"]) for item in case_results),
        "total_tool_calls": sum(int(item["tool_call_count"]) for item in case_results),
        "total_llm_calls": sum(int(item["llm_call_count"]) for item in case_results),
    }


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# InsightGraph Benchmark",
        "",
        "| Query | Duration ms | Findings | Matrix rows | References | Tool calls "
        "| LLM calls | Critique passed | Matrix section |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in payload["cases"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    str(item["duration_ms"]),
                    str(item["finding_count"]),
                    str(item["competitive_matrix_row_count"]),
                    str(item["reference_count"]),
                    str(item["tool_call_count"]),
                    str(item["llm_call_count"]),
                    _format_bool(bool(item["critique_passed"])),
                    _format_bool(bool(item["report_has_competitive_matrix"])),
                ]
            )
            + " |"
        )

    summary = payload["summary"]
    lines.extend(
        [
            "",
            "## Summary",
            "",
            "| Cases | Total duration ms | All critique passed | Total findings "
            "| Total matrix rows | Total references | Total tool calls | Total LLM calls |",
            "| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |",
            "| "
            + " | ".join(
                [
                    str(summary["case_count"]),
                    str(summary["total_duration_ms"]),
                    _format_bool(bool(summary["all_critique_passed"])),
                    str(summary["total_findings"]),
                    str(summary["total_competitive_matrix_rows"]),
                    str(summary["total_references"]),
                    str(summary["total_tool_calls"]),
                    str(summary["total_llm_calls"]),
                ]
            )
            + " |",
        ]
    )
    error_lines = _format_error_lines(payload["cases"])
    if error_lines:
        lines.extend(error_lines)
    return "\n".join(lines) + "\n"


def _format_error_lines(case_results: list[dict[str, Any]]) -> list[str]:
    errors = [item for item in case_results if "error" in item]
    if not errors:
        return []
    lines = ["", "## Errors", "", "| Query | Error |", "| --- | --- |"]
    for item in errors:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    _markdown_table_cell(str(item["error"])),
                ]
            )
            + " |"
        )
    return lines


def _markdown_table_cell(value: str) -> str:
    return " ".join(value.replace("|", r"\|").splitlines())


def _format_bool(value: bool) -> str:
    return "true" if value else "false"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run offline InsightGraph research benchmarks.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown instead of JSON.")
    args = parser.parse_args(argv)
    payload = build_benchmark_payload()
    if args.markdown:
        print(format_markdown(payload), end="")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
