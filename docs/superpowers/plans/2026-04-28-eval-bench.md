# Eval Bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic offline evaluation CLI that scores InsightGraph research output quality.

**Architecture:** Move benchmark logic into `src/insight_graph/eval.py` and keep `scripts/benchmark_research.py` as a compatibility wrapper. The eval module runs offline cases, computes rule-based quality scores, formats JSON/Markdown, and writes optional output files.

**Tech Stack:** Python argparse, dataclasses, existing `GraphState`, pytest, package console scripts.

---

## File Structure

- Create `src/insight_graph/eval.py`: eval cases, scoring, formatting, CLI.
- Modify `scripts/benchmark_research.py`: delegate/re-export package eval functions.
- Modify `pyproject.toml`: add `insight-graph-eval = "insight_graph.eval:main"`.
- Create `tests/test_eval.py`: scoring, output, CLI tests.
- Modify `tests/test_benchmark_research.py`: only if compatibility expectations need score fields.
- Modify `README.md`, `docs/demo.md`, and `CHANGELOG.md`: document Eval Bench usage.

## Task 1: Failing Eval Tests

- [ ] Add `tests/test_eval.py` with scoring, summary, Markdown, output file, and script registration tests.
- [ ] Run targeted tests and confirm failures are due to missing `insight_graph.eval` and console script.

## Task 2: Eval Module Implementation

- [ ] Create `src/insight_graph/eval.py` by moving current benchmark behavior from `scripts/benchmark_research.py`.
- [ ] Add case threshold model and scoring rules.
- [ ] Add `score`, `passed`, and `rules` to each case result.
- [ ] Add `average_score`, `passed_count`, `failed_count`, and `failed_rules` to summary.
- [ ] Preserve safe errors and offline environment isolation.
- [ ] Run `tests/test_eval.py` and confirm it passes.

## Task 3: CLI and Compatibility

- [ ] Add `--output PATH` to eval CLI.
- [ ] Register `insight-graph-eval` in `pyproject.toml`.
- [ ] Replace `scripts/benchmark_research.py` with a compatibility wrapper re-exporting package eval names.
- [ ] Run `tests/test_benchmark_research.py` and update assertions only for intentional added fields.

## Task 4: Docs

- [ ] Update `README.md` with Eval Bench command examples.
- [ ] Update `docs/demo.md` with an offline eval command.
- [ ] Add `CHANGELOG.md` Unreleased entry.

## Task 5: Verification

- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_eval.py tests/test_benchmark_research.py -v`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest`.
- [ ] Run `& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: scoring, CLI, output, wrapper compatibility, docs, and verification are covered.
- Placeholder scan: no placeholders.
- Type consistency: `score`, `passed`, `rules`, and summary names match the spec.
