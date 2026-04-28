import argparse
import json
import os
import re
import sys
import time
from collections.abc import Callable, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from insight_graph.graph import run_research
from insight_graph.state import GraphState

OFFLINE_ENV_VARS = [
    "INSIGHT_GRAPH_ANALYST_PROVIDER",
    "INSIGHT_GRAPH_REPORTER_PROVIDER",
    "INSIGHT_GRAPH_LLM_API_KEY",
    "INSIGHT_GRAPH_LLM_BASE_URL",
    "INSIGHT_GRAPH_LLM_MODEL",
    "INSIGHT_GRAPH_LLM_WIRE_API",
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
PASSING_SCORE = 80
RULE_IDS = [
    "critique_passed",
    "has_report",
    "has_competitive_matrix_section",
    "references_meet_minimum",
    "findings_meet_minimum",
    "matrix_rows_meet_minimum",
    "findings_cite_evidence",
    "matrix_rows_cite_evidence",
]


@dataclass(frozen=True)
class EvalCase:
    query: str
    min_findings: int = 1
    min_matrix_rows: int = 1
    min_references: int = 2


BENCHMARK_CASES = [
    "Compare Cursor, OpenCode, and GitHub Copilot",
    "Analyze AI coding agents market positioning",
    "Compare Claude Code, Codeium, and Windsurf",
]
DEFAULT_EVAL_CASES = [EvalCase(query=query) for query in BENCHMARK_CASES]


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


def build_eval_payload(
    cases: list[EvalCase | str] | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    eval_cases = [_coerce_eval_case(case) for case in (cases or DEFAULT_EVAL_CASES)]
    case_results = [_run_case(case, run_research_func) for case in eval_cases]
    return {"cases": case_results, "summary": _build_summary(case_results)}


def build_benchmark_payload(
    cases: list[str] | None = None,
    run_research_func: Callable[[str], GraphState] = run_research,
) -> dict[str, Any]:
    return build_eval_payload(cases, run_research_func=run_research_func)


def _coerce_eval_case(case: EvalCase | str) -> EvalCase:
    if isinstance(case, EvalCase):
        return case
    return EvalCase(query=case)


def _run_case(
    case: EvalCase,
    run_research_func: Callable[[str], GraphState],
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with offline_environment():
            state = run_research_func(case.query)
    except Exception:
        duration_ms = _duration_ms_since(started)
        return _error_case_result(case.query, duration_ms)

    duration_ms = _duration_ms_since(started)
    return _case_result_from_state(case, duration_ms, state)


def _duration_ms_since(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _case_result_from_state(case: EvalCase, duration_ms: int, state: GraphState) -> dict[str, Any]:
    report_markdown = state.report_markdown or ""
    rules = _score_rules(case, state, report_markdown)
    score = _score_from_rules(rules)
    return {
        "query": case.query,
        "duration_ms": duration_ms,
        "score": score,
        "passed": score >= PASSING_SCORE,
        "rules": rules,
        "finding_count": len(state.findings),
        "competitive_matrix_row_count": len(state.competitive_matrix),
        "reference_count": count_references(report_markdown),
        "tool_call_count": len(state.tool_call_log),
        "llm_call_count": len(state.llm_call_log),
        "critique_passed": bool(state.critique and state.critique.passed),
        "report_has_competitive_matrix": "## Competitive Matrix" in report_markdown,
    }


def _score_rules(case: EvalCase, state: GraphState, report_markdown: str) -> list[dict[str, Any]]:
    checks = {
        "critique_passed": bool(state.critique and state.critique.passed),
        "has_report": bool(report_markdown.strip()),
        "has_competitive_matrix_section": "## Competitive Matrix" in report_markdown,
        "references_meet_minimum": count_references(report_markdown) >= case.min_references,
        "findings_meet_minimum": len(state.findings) >= case.min_findings,
        "matrix_rows_meet_minimum": len(state.competitive_matrix) >= case.min_matrix_rows,
        "findings_cite_evidence": all(item.evidence_ids for item in state.findings),
        "matrix_rows_cite_evidence": all(item.evidence_ids for item in state.competitive_matrix),
    }
    points = 100 / len(RULE_IDS)
    return [
        {"id": rule_id, "passed": checks[rule_id], "points": points if checks[rule_id] else 0}
        for rule_id in RULE_IDS
    ]


def _score_from_rules(rules: list[dict[str, Any]]) -> int:
    return round(sum(float(rule["points"]) for rule in rules))


def _error_case_result(query: str, duration_ms: int) -> dict[str, Any]:
    rules = [{"id": rule_id, "passed": False, "points": 0} for rule_id in RULE_IDS]
    return {
        "query": query,
        "duration_ms": duration_ms,
        "score": 0,
        "passed": False,
        "rules": rules,
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
    failed_rules = _failed_rule_counts(case_results)
    total_score = sum(int(item["score"]) for item in case_results)
    case_count = len(case_results)
    return {
        "case_count": case_count,
        "average_score": round(total_score / case_count) if case_count else 0,
        "passed_count": sum(1 for item in case_results if item["passed"]),
        "failed_count": sum(1 for item in case_results if not item["passed"]),
        "failed_rules": failed_rules,
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


def _failed_rule_counts(case_results: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in case_results:
        for rule in item.get("rules", []):
            if not rule["passed"]:
                counts[rule["id"]] = counts.get(rule["id"], 0) + 1
    return counts


def format_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# InsightGraph Eval Bench",
        "",
        "| Query | Score | Passed | Duration ms | Findings | Matrix rows | References "
        "| Tool calls | LLM calls | Critique passed | Matrix section |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for item in payload["cases"]:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_table_cell(str(item["query"])),
                    str(item["score"]),
                    _format_bool(bool(item["passed"])),
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
            "| Cases | Average score | Passed | Failed | Total duration ms | Total findings "
            "| Total matrix rows | Total references | Total tool calls | Total LLM calls |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
            "| "
            + " | ".join(
                [
                    str(summary["case_count"]),
                    str(summary["average_score"]),
                    str(summary["passed_count"]),
                    str(summary["failed_count"]),
                    str(summary["total_duration_ms"]),
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
    lines.extend(_format_failed_rule_lines(summary["failed_rules"]))
    error_lines = _format_error_lines(payload["cases"])
    if error_lines:
        lines.extend(error_lines)
    return "\n".join(lines) + "\n"


def _format_failed_rule_lines(failed_rules: dict[str, int]) -> list[str]:
    if not failed_rules:
        return []
    lines = ["", "## Failed Rules", "", "| Rule | Count |", "| --- | ---: |"]
    for rule_id, count in sorted(failed_rules.items()):
        lines.append(f"| {rule_id} | {count} |")
    return lines


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
    parser = argparse.ArgumentParser(description="Run offline InsightGraph eval bench.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown instead of JSON.")
    parser.add_argument("--output", help="Write output to a file instead of stdout.")
    args = parser.parse_args(argv)
    payload = build_eval_payload()
    output = (
        format_markdown(payload)
        if args.markdown
        else json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    )
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
