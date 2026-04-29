# CI Eval Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upload Eval Bench JSON and Markdown reports from CI.

**Architecture:** Keep the existing single GitHub Actions `test` job. Generate both report formats before the blocking gate, then upload `reports/eval.*` with `if: always()` so artifacts are retained when the gate fails.

**Tech Stack:** GitHub Actions YAML, `actions/upload-artifact`, `insight-graph-eval`, pytest, Ruff.

---

## File Structure

- Modify `.github/workflows/ci.yml`: add eval report generation and artifact upload.
- Modify `README.md`: mention CI eval artifacts.
- Modify `docs/demo.md`: mention downloadable CI eval artifacts.
- Modify `CHANGELOG.md`: add Unreleased entry for eval artifacts.

## Task 1: CI Artifacts

- [ ] Modify `.github/workflows/ci.yml` after `Test` to add:

```yaml
      - name: Generate Eval Reports
        run: |
          mkdir -p reports
          insight-graph-eval --case-file docs/evals/default.json --output reports/eval.json
          insight-graph-eval --case-file docs/evals/default.json --markdown --output reports/eval.md
```

- [ ] Keep the existing `Eval Gate` step after report generation.

- [ ] Add after `Eval Gate`:

```yaml
      - name: Upload Eval Reports
        if: always()
        uses: actions/upload-artifact@v6
        with:
          name: eval-reports
          path: reports/eval.*
```

## Task 2: Docs

- [ ] Update `README.md` near Eval Bench examples to state CI uploads `eval-reports` with `reports/eval.json` and `reports/eval.md`.
- [ ] Update `docs/demo.md` Eval Bench section with the same artifact note.
- [ ] Update `CHANGELOG.md` Unreleased with `Added CI Eval Bench report artifacts.`

## Task 3: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m insight_graph.eval --case-file docs/evals/default.json --output reports/eval.json`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m insight_graph.eval --case-file docs/evals/default.json --markdown --output reports/eval.md`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m insight_graph.eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.
- [ ] Delete local `reports/eval.json` and `reports/eval.md` so generated artifacts are not committed.

## Self-Review

- Spec coverage: report generation, artifact upload, existing gate, docs, changelog, and cleanup are covered.
- Placeholder scan: no placeholders.
- Type consistency: artifact name, report paths, and eval commands match the design.
