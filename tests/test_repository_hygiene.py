from pathlib import Path


def test_gitignore_excludes_local_tool_caches_and_generated_eval_reports() -> None:
    gitignore = (Path(__file__).parents[1] / ".gitignore").read_text(encoding="utf-8")

    assert ".ruff_cache/" in gitignore
    assert "reports/eval.json" in gitignore
    assert "reports/eval.md" in gitignore
    assert "reports/eval-summary.json" in gitignore
    assert "reports/eval-summary.md" in gitignore
    assert "reports/eval-history.json" in gitignore
    assert "reports/eval-history.md" in gitignore
    assert "reports/ai-coding-agents-technical-review.md" in gitignore


def test_report_quality_roadmap_documents_worktree_pythonpath_rule() -> None:
    roadmap = (Path(__file__).parents[1] / "docs" / "report-quality-roadmap.md").read_text(
        encoding="utf-8"
    )

    assert "PYTHONPATH=src" in roadmap
    assert "worktree" in roadmap.lower()
    assert "editable install" in roadmap


def test_historical_superpowers_process_docs_are_not_tracked() -> None:
    root = Path(__file__).parents[1]

    plan_files = sorted((root / "docs" / "superpowers" / "plans").glob("*.md"))
    spec_dir = root / "docs" / "superpowers" / "specs"

    assert [path.name for path in plan_files] == [
        "2026-04-30-remaining-product-roadmap.md"
    ]
    assert not spec_dir.exists()


def test_generated_showcase_report_is_not_tracked() -> None:
    root = Path(__file__).parents[1]

    assert not (root / "reports" / "ai-coding-agents-technical-review.md").exists()
