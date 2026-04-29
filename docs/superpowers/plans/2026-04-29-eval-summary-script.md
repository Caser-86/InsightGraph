# Eval Summary Script Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a script that summarizes existing Eval Bench JSON reports without re-running evals.

**Architecture:** Implement a standalone script under `scripts/` that reads JSON, validates a small `summary` shape, and writes either JSON or Markdown to stdout. Keep this independent from CI and the Eval Bench runner so it can be reused later for trend collection.

**Tech Stack:** Python stdlib `argparse`, `json`, `pathlib`; pytest; Ruff.

---

## File Structure

- Create `scripts/summarize_eval_report.py`: CLI and summary formatting.
- Create `tests/test_summarize_eval_report.py`: unit and CLI tests.
- Modify `README.md`: add command example.
- Modify `docs/demo.md`: add command example near Eval Bench demo.
- Modify `CHANGELOG.md`: add Unreleased entry.

## Task 1: Failing Tests

- [ ] Create `tests/test_summarize_eval_report.py` with tests for summary extraction, Markdown formatting, JSON CLI output, and malformed JSON exit `2`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_summarize_eval_report.py -v`.
- [ ] Confirm it fails because `scripts.summarize_eval_report` does not exist.

## Task 2: Script Implementation

- [ ] Create `scripts/summarize_eval_report.py`.
- [ ] Implement `summarize_eval_report(payload)` returning only `case_count`, `average_score`, `passed_count`, `failed_count`, `failed_rules`, and `total_duration_ms`.
- [ ] Implement `format_markdown(summary)` with the compact table and optional failed rules table.
- [ ] Implement `main(argv=None, stdout=None, stderr=None)` with safe exit code `2` for input/config errors.
- [ ] Run targeted tests and confirm they pass.

## Task 3: Docs

- [ ] Update `README.md` command examples with `python scripts/summarize_eval_report.py reports/eval.json --markdown`.
- [ ] Update `docs/demo.md` Eval Bench section with the same command.
- [ ] Update `CHANGELOG.md` Unreleased with `Added Eval Bench report summary script.`

## Task 4: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_summarize_eval_report.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: script, JSON output, Markdown output, safe errors, docs, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: function names and summary field names match the design.
