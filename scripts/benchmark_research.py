import argparse
import json
import sys
from collections.abc import Callable
from typing import Any

from insight_graph import eval as eval_module
from insight_graph.state import GraphState

BENCHMARK_CASES = eval_module.BENCHMARK_CASES
OFFLINE_ENV_VARS = eval_module.OFFLINE_ENV_VARS
SAFE_WORKFLOW_ERROR = eval_module.SAFE_WORKFLOW_ERROR
count_references = eval_module.count_references
offline_environment = eval_module.offline_environment
time = eval_module.time


def build_benchmark_payload(
    cases: list[str] | None = None,
    run_research_func: Callable[[str], GraphState] = eval_module.run_research,
) -> dict[str, Any]:
    return _legacy_payload(
        eval_module.build_eval_payload(cases, run_research_func=run_research_func)
    )


def _legacy_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "cases": [_legacy_case(item) for item in payload["cases"]],
        "summary": _legacy_summary(payload["summary"]),
    }


def _legacy_case(item: dict[str, Any]) -> dict[str, Any]:
    legacy = {
        "query": item["query"],
        "duration_ms": item["duration_ms"],
        "finding_count": item["finding_count"],
        "competitive_matrix_row_count": item["competitive_matrix_row_count"],
        "reference_count": item["reference_count"],
        "tool_call_count": item["tool_call_count"],
        "llm_call_count": item["llm_call_count"],
        "critique_passed": item["critique_passed"],
        "report_has_competitive_matrix": item["report_has_competitive_matrix"],
    }
    if "error" in item:
        legacy["error"] = item["error"]
    return legacy


def _legacy_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_count": summary["case_count"],
        "total_duration_ms": summary["total_duration_ms"],
        "all_critique_passed": summary["all_critique_passed"],
        "total_findings": summary["total_findings"],
        "total_competitive_matrix_rows": summary["total_competitive_matrix_rows"],
        "total_references": summary["total_references"],
        "total_tool_calls": summary["total_tool_calls"],
        "total_llm_calls": summary["total_llm_calls"],
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
                    eval_module._markdown_table_cell(str(item["query"])),
                    str(item["duration_ms"]),
                    str(item["finding_count"]),
                    str(item["competitive_matrix_row_count"]),
                    str(item["reference_count"]),
                    str(item["tool_call_count"]),
                    str(item["llm_call_count"]),
                    eval_module._format_bool(bool(item["critique_passed"])),
                    eval_module._format_bool(bool(item["report_has_competitive_matrix"])),
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
                    eval_module._format_bool(bool(summary["all_critique_passed"])),
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
    error_lines = eval_module._format_error_lines(payload["cases"])
    if error_lines:
        lines.extend(error_lines)
    return "\n".join(lines) + "\n"


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
