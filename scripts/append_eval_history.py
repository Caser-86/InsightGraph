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

METADATA_FIELDS = ["run_id", "head_sha", "created_at"]


class EvalHistoryError(ValueError):
    pass


def append_eval_history(
    summary: dict[str, Any],
    history: list[dict[str, Any]],
    metadata: dict[str, str],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if limit < 1:
        raise EvalHistoryError("limit must be at least 1")
    _validate_metadata(metadata)
    _validate_summary(summary)
    _validate_history(history)

    row = {**metadata, **{field: summary[field] for field in SUMMARY_FIELDS}}
    rows = [row]
    rows.extend(item for item in history if item["run_id"] != metadata["run_id"])
    return rows[:limit]


def format_markdown(history: list[dict[str, Any]]) -> str:
    lines = [
        "# Eval History",
        "",
        "| Created | Run | SHA | Average score | Passed | Failed | Failed rules |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in history:
        lines.append(
            "| "
            + " | ".join(
                [
                    _markdown_cell(str(row["created_at"])),
                    _markdown_cell(str(row["run_id"])),
                    _markdown_cell(str(row["head_sha"])[:7]),
                    str(row["average_score"]),
                    str(row["passed_count"]),
                    str(row["failed_count"]),
                    _markdown_cell(_format_failed_rules(row["failed_rules"])),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    parser = argparse.ArgumentParser(description="Append Eval Bench summary history.")
    parser.add_argument("--summary", required=True, help="Eval summary JSON path.")
    parser.add_argument("--history", required=True, help="Eval history JSON path.")
    parser.add_argument("--markdown", help="Optional Eval history Markdown output path.")
    parser.add_argument("--run-id", required=True, help="CI run identifier.")
    parser.add_argument("--head-sha", required=True, help="CI head commit SHA.")
    parser.add_argument("--created-at", required=True, help="CI run timestamp.")
    parser.add_argument("--limit", type=int, default=50, help="Maximum retained history rows.")
    args = parser.parse_args(argv)

    try:
        summary = _read_json_object(Path(args.summary))
        history_path = Path(args.history)
        history = _read_history(history_path)
        updated = append_eval_history(
            summary,
            history,
            {
                "run_id": args.run_id,
                "head_sha": args.head_sha,
                "created_at": args.created_at,
            },
            limit=args.limit,
        )
        history_path.write_text(
            json.dumps(updated, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        if args.markdown:
            Path(args.markdown).write_text(format_markdown(updated), encoding="utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError, EvalHistoryError) as exc:
        stderr.write(f"Failed to append eval history: {exc}\n")
        return 2

    return 0


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise EvalHistoryError("JSON input must be an object")
    return payload


def _read_history(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise EvalHistoryError("history must be a list of objects")
    return payload


def _validate_metadata(metadata: dict[str, str]) -> None:
    for field in METADATA_FIELDS:
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            raise EvalHistoryError(f"{field} is required")


def _validate_summary(summary: dict[str, Any]) -> None:
    missing = [field for field in SUMMARY_FIELDS if field not in summary]
    if missing:
        raise EvalHistoryError(f"eval summary missing field: {missing[0]}")
    if not isinstance(summary["failed_rules"], dict):
        raise EvalHistoryError("failed_rules must be an object")


def _validate_history(history: list[dict[str, Any]]) -> None:
    for row in history:
        for field in [*METADATA_FIELDS, *SUMMARY_FIELDS]:
            if field not in row:
                raise EvalHistoryError(f"history row missing field: {field}")
        if not isinstance(row["failed_rules"], dict):
            raise EvalHistoryError("history failed_rules must be an object")


def _format_failed_rules(failed_rules: dict[str, Any]) -> str:
    if not failed_rules:
        return "none"
    return ", ".join(f"{rule}={count}" for rule, count in sorted(failed_rules.items()))


def _markdown_cell(value: str) -> str:
    return " ".join(value.splitlines()).replace("|", r"\|")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
