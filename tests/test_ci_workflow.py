from pathlib import Path


def test_ci_uploads_eval_summary_artifacts() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert (
        "python scripts/summarize_eval_report.py reports/eval.json > reports/eval-summary.json"
        in workflow
    )
    assert (
        "python scripts/summarize_eval_report.py reports/eval.json --markdown > "
        "reports/eval-summary.md"
        in workflow
    )
    assert "reports/eval.json" in workflow
    assert "reports/eval.md" in workflow
    assert "reports/eval-summary.json" in workflow
    assert "reports/eval-summary.md" in workflow
