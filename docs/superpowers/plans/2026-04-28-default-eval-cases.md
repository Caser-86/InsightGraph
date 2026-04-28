# Default Eval Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-standard default eval case file for the Eval Bench CLI gate.

**Architecture:** Store default cases as JSON under `docs/evals/default.json` and rely on the existing `load_eval_cases()` parser. Tests validate the checked-in file instead of duplicating parser logic.

**Tech Stack:** JSON, pytest, existing `insight_graph.eval` loader.

---

## File Structure

- Create `docs/evals/default.json`: default deterministic eval case set.
- Modify `tests/test_eval.py`: add validation test for default case file.
- Modify `README.md`: update Eval Bench command examples.
- Modify `docs/demo.md`: update Eval Bench demo command.
- Modify `CHANGELOG.md`: add Unreleased entry.

## Task 1: Failing Test

- [ ] Add a test in `tests/test_eval.py` that loads `docs/evals/default.json` via `load_eval_cases()`.
- [ ] Assert exactly three cases and threshold values `(1, 1, 2)` for findings, matrix rows, and references.
- [ ] Run the new test and confirm it fails because the file does not exist.

## Task 2: Default Case File

- [ ] Create `docs/evals/default.json` with three deterministic offline cases.
- [ ] Run the new test and confirm it passes.

## Task 3: Docs

- [ ] Update README command examples to use `--case-file docs/evals/default.json`.
- [ ] Update demo Eval Bench command to use the default case file.
- [ ] Update changelog Unreleased entry.

## Task 4: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: file creation, test validation, docs, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: `docs/evals/default.json` and `load_eval_cases()` names match implementation.
