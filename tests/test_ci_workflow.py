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
    assert "created_at=\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" in workflow
    assert "python scripts/append_eval_history.py --summary reports/eval-summary.json" in workflow
    assert "--history reports/eval-history.json" in workflow
    assert "--markdown reports/eval-history.md" in workflow
    assert "reports/eval-history.json" in workflow
    assert "reports/eval-history.md" in workflow


def test_ci_validates_deployment_smoke_script_without_network() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "Validate Deployment Smoke Script" in workflow
    assert "insight-graph-smoke --help" in workflow


def test_ci_uses_least_privilege_permissions_and_concurrency() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "permissions:" in workflow
    assert "contents: read" in workflow
    assert "concurrency:" in workflow
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in workflow
    assert "cancel-in-progress: true" in workflow
