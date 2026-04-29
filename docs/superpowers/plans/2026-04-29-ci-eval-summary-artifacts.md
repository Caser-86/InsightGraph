# CI Eval Summary Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add compact eval summary JSON and Markdown files to the existing CI `eval-reports` artifact.

**Architecture:** Reuse the existing CI eval JSON report as the single source of truth. Run `scripts/summarize_eval_report.py` inside the existing `Generate Eval Reports` step, then upload all four files explicitly with `actions/upload-artifact`.

**Tech Stack:** GitHub Actions YAML, Python script redirect output, pytest text assertions, Ruff.

---

## File Structure

- Modify `.github/workflows/ci.yml`: generate and upload eval summary artifacts.
- Create `tests/test_ci_workflow.py`: assert CI workflow contains eval summary artifact commands.
- Modify `README.md`: mention eval summary artifacts.
- Modify `docs/demo.md`: mention eval summary artifacts.
- Modify `CHANGELOG.md`: add Unreleased entry.

## Task 1: Failing Workflow Test

- [ ] Create `tests/test_ci_workflow.py`:

```python
from pathlib import Path


def test_ci_uploads_eval_summary_artifacts() -> None:
    workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )

    assert "python scripts/summarize_eval_report.py reports/eval.json > reports/eval-summary.json" in workflow
    assert "python scripts/summarize_eval_report.py reports/eval.json --markdown > reports/eval-summary.md" in workflow
    assert "reports/eval.json" in workflow
    assert "reports/eval.md" in workflow
    assert "reports/eval-summary.json" in workflow
    assert "reports/eval-summary.md" in workflow
```

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_ci_workflow.py -v`.
- [ ] Confirm it fails because the workflow does not generate eval summary artifacts yet.

## Task 2: CI Workflow

- [ ] Modify `.github/workflows/ci.yml` `Generate Eval Reports` step to add:

```yaml
          python scripts/summarize_eval_report.py reports/eval.json > reports/eval-summary.json
          python scripts/summarize_eval_report.py reports/eval.json --markdown > reports/eval-summary.md
```

- [ ] Modify `Upload Eval Reports` path to list exactly:

```yaml
          path: |
            reports/eval.json
            reports/eval.md
            reports/eval-summary.json
            reports/eval-summary.md
```

- [ ] Run the targeted workflow test and confirm it passes.

## Task 3: Docs

- [ ] Update `README.md` to say CI uploads `reports/eval-summary.json` and `reports/eval-summary.md` in `eval-reports`.
- [ ] Update `docs/demo.md` with the same artifact note.
- [ ] Update `CHANGELOG.md` Unreleased with `Added CI Eval Bench summary artifacts.`

## Task 4: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_ci_workflow.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: CI generation, artifact upload, tests, docs, changelog, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: file paths and commands match the existing summary script.
