import io
import json

import scripts.append_eval_history as history_module

SUMMARY = {
    "case_count": 3,
    "average_score": 91.5,
    "passed_count": 2,
    "failed_count": 1,
    "failed_rules": {"references_meet_minimum": 1},
    "total_duration_ms": 23,
}

METADATA = {
    "run_id": "run-2",
    "head_sha": "abcdef123456",
    "created_at": "2026-04-29T02:28:00Z",
}


def test_append_eval_history_adds_row_to_empty_history() -> None:
    history = history_module.append_eval_history(SUMMARY, [], METADATA, limit=50)

    assert history == [
        {
            "run_id": "run-2",
            "head_sha": "abcdef123456",
            "created_at": "2026-04-29T02:28:00Z",
            "case_count": 3,
            "average_score": 91.5,
            "passed_count": 2,
            "failed_count": 1,
            "failed_rules": {"references_meet_minimum": 1},
            "total_duration_ms": 23,
        }
    ]


def test_append_eval_history_keeps_newest_rows_first_and_limits() -> None:
    existing = [
        {
            "run_id": "run-1",
            "head_sha": "old-sha",
            "created_at": "2026-04-28T00:00:00Z",
            "case_count": 3,
            "average_score": 100,
            "passed_count": 3,
            "failed_count": 0,
            "failed_rules": {},
            "total_duration_ms": 20,
        }
    ]

    history = history_module.append_eval_history(SUMMARY, existing, METADATA, limit=1)

    assert [row["run_id"] for row in history] == ["run-2"]


def test_append_eval_history_deduplicates_by_run_id() -> None:
    existing = [
        {
            "run_id": "run-2",
            "head_sha": "stale-sha",
            "created_at": "2026-04-29T00:00:00Z",
            "case_count": 1,
            "average_score": 10,
            "passed_count": 0,
            "failed_count": 1,
            "failed_rules": {"has_report": 1},
            "total_duration_ms": 99,
        }
    ]

    history = history_module.append_eval_history(SUMMARY, existing, METADATA, limit=50)

    assert len(history) == 1
    assert history[0]["head_sha"] == "abcdef123456"
    assert history[0]["average_score"] == 91.5


def test_format_markdown_outputs_trend_table() -> None:
    history = history_module.append_eval_history(SUMMARY, [], METADATA, limit=50)

    markdown = history_module.format_markdown(history)

    assert "# Eval History" in markdown
    assert "| Created | Run | SHA | Average score | Passed | Failed | Failed rules |" in markdown
    assert (
        "| 2026-04-29T02:28:00Z | run-2 | abcdef1 | 91.5 | 2 | 1 | "
        "references_meet_minimum=1 |"
        in markdown
    )


def test_main_appends_history_and_writes_markdown(tmp_path) -> None:
    summary_path = tmp_path / "eval-summary.json"
    history_path = tmp_path / "eval-history.json"
    markdown_path = tmp_path / "eval-history.md"
    summary_path.write_text(json.dumps(SUMMARY), encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = history_module.main(
        [
            "--summary",
            str(summary_path),
            "--history",
            str(history_path),
            "--markdown",
            str(markdown_path),
            "--run-id",
            "run-2",
            "--head-sha",
            "abcdef123456",
            "--created-at",
            "2026-04-29T02:28:00Z",
            "--limit",
            "50",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == ""
    assert json.loads(history_path.read_text(encoding="utf-8"))[0]["run_id"] == "run-2"
    assert "# Eval History" in markdown_path.read_text(encoding="utf-8")


def test_main_returns_two_for_malformed_summary(tmp_path) -> None:
    summary_path = tmp_path / "eval-summary.json"
    history_path = tmp_path / "eval-history.json"
    summary_path.write_text("not json", encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = history_module.main(
        [
            "--summary",
            str(summary_path),
            "--history",
            str(history_path),
            "--run-id",
            "run-2",
            "--head-sha",
            "abcdef123456",
            "--created-at",
            "2026-04-29T02:28:00Z",
        ],
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "Failed to append eval history:" in stderr.getvalue()
