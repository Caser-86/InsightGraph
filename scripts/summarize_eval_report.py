import argparse
import json
import sys
from pathlib import Path
from typing import Any, TextIO

SUMMARY_FIELDS = [
    "case_count",
    "average_score",
    "passed_count",
    "failed_count",
    "failed_rules",
    "total_duration_ms",
]
QUALITY_SUMMARY_FIELDS = [
    "average_section_coverage_score",
    "average_report_depth_score",
    "average_source_diversity_score",
    "average_citation_support_score",
    "total_unsupported_claims",
    "average_duplicate_source_rate",
]


class EvalSummaryError(ValueError):
    pass


def summarize_eval_report(payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise EvalSummaryError("eval report must contain a summary object")

    missing = [field for field in SUMMARY_FIELDS if field not in summary]
    if missing:
        raise EvalSummaryError(f"eval summary missing field: {missing[0]}")

    result = {field: summary[field] for field in SUMMARY_FIELDS}
    if not isinstance(result["failed_rules"], dict):
        raise EvalSummaryError("failed_rules must be an object")
    for field in QUALITY_SUMMARY_FIELDS:
        result[field] = summary.get(field, 0)
    return result


def format_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Eval Summary",
        "",
        "| Cases | Average score | Passed | Failed | Duration ms |",
        "| ---: | ---: | ---: | ---: | ---: |",
        (
            f"| {summary['case_count']} | {summary['average_score']} | "
            f"{summary['passed_count']} | {summary['failed_count']} | "
            f"{summary['total_duration_ms']} |"
        ),
    ]

    lines.extend(
        [
            "",
            "## Report Quality",
            "",
            "| Avg section coverage | Avg report depth | Avg source diversity "
            "| Avg citation support | Unsupported claims | Avg duplicate source rate |",
            "| ---: | ---: | ---: | ---: | ---: | ---: |",
            (
                f"| {summary['average_section_coverage_score']} | "
                f"{summary['average_report_depth_score']} | "
                f"{summary['average_source_diversity_score']} | "
                f"{summary['average_citation_support_score']} | "
                f"{summary['total_unsupported_claims']} | "
                f"{summary['average_duplicate_source_rate']} |"
            ),
        ]
    )

    failed_rules = summary["failed_rules"]
    if failed_rules:
        lines.extend(
            [
                "",
                "## Failed Rules",
                "",
                "| Rule | Count |",
                "| --- | ---: |",
            ]
        )
        for rule, count in sorted(failed_rules.items()):
            lines.append(f"| {_markdown_cell(str(rule))} | {count} |")

    return "\n".join(lines) + "\n"


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    parser = argparse.ArgumentParser(description="Summarize an Eval Bench JSON report.")
    parser.add_argument("path", help="Eval Bench JSON report path.")
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Write GitHub-flavored Markdown instead of JSON.",
    )
    args = parser.parse_args(argv)

    try:
        payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise EvalSummaryError("eval report must be an object")
        summary = summarize_eval_report(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, EvalSummaryError) as exc:
        stderr.write(f"Failed to read eval report: {exc}\n")
        return 2

    if args.markdown:
        stdout.write(format_markdown(summary))
    else:
        json.dump(summary, stdout, indent=2, ensure_ascii=False)
        stdout.write("\n")
    return 0


def _markdown_cell(value: str) -> str:
    return " ".join(value.splitlines()).replace("|", r"\|")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
