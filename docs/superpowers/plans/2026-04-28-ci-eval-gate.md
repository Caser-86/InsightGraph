# CI Eval Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the default Eval Bench gate to GitHub Actions CI.

**Architecture:** Reuse the existing `.github/workflows/ci.yml` `test` job and append one deterministic offline eval command after pytest. The gate reads `docs/evals/default.json` and fails CI if the average score is below 85 or any case fails.

**Tech Stack:** GitHub Actions YAML, `insight-graph-eval`, pytest, Ruff.

---

## File Structure

- Modify `.github/workflows/ci.yml`: add `Eval Gate` step after `Test`.
- Modify `CHANGELOG.md`: describe CI eval gate in Unreleased.

## Task 1: CI Workflow

- [ ] Modify `.github/workflows/ci.yml` to append:

```yaml
      - name: Eval Gate
        run: insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure
```

- [ ] Keep the step inside the existing `test` job after `Test`.

## Task 2: Changelog

- [ ] Update `CHANGELOG.md` Unreleased entry to include that CI now runs the default Eval Gate.

## Task 3: Verification

- [ ] Run `insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: CI step, default case file, threshold, changelog, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: command and file paths match the design.
