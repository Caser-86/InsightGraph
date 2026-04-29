# Eval Trend History Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build file-based Eval Bench trend history from CI summary artifacts.

**Architecture:** Add an offline script that appends a CI metadata row plus `eval-summary.json` fields to a bounded JSON history file. Generate a Markdown trend table from the same history and upload both generated files as CI artifacts.

**Tech Stack:** Python stdlib, GitHub Actions, pytest, Ruff.

---

## File Structure

- Create `scripts/append_eval_history.py`: append and render eval history.
- Create `tests/test_append_eval_history.py`: unit and CLI tests.
- Modify `.github/workflows/ci.yml`: create timestamp, append history, upload history files.
- Modify `README.md`: document eval history commands/artifacts.
- Modify `docs/demo.md`: document eval history artifacts.
- Modify `CHANGELOG.md`: add release note.

## Task 1: Failing History Tests

- [ ] Create tests covering empty history append, newest-first ordering, dedupe by `run_id`, `--limit`, Markdown formatting, and malformed input exit `2`.
- [ ] Run `pytest tests/test_append_eval_history.py -v` and confirm it fails because the script does not exist.

## Task 2: Script Implementation

- [ ] Create `scripts/append_eval_history.py` with `append_eval_history(summary, history, metadata, limit)`.
- [ ] Add `format_markdown(history)` for a compact trend table.
- [ ] Add CLI flags: `--summary`, `--history`, `--markdown`, `--run-id`, `--head-sha`, `--created-at`, and `--limit`.
- [ ] Return exit `2` for unreadable, malformed, or invalid inputs.
- [ ] Run targeted tests until green.

## Task 3: CI Integration

- [ ] In `.github/workflows/ci.yml`, set a UTC timestamp before eval history append:

```yaml
          created_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

- [ ] Invoke the history script after `eval-summary.*` generation:

```yaml
          python scripts/append_eval_history.py --summary reports/eval-summary.json --history reports/eval-history.json --markdown reports/eval-history.md --run-id "$GITHUB_RUN_ID" --head-sha "$GITHUB_SHA" --created-at "$created_at" --limit 50
```

- [ ] Upload `reports/eval-history.json` and `reports/eval-history.md` in `eval-reports`.

## Task 4: Docs

- [ ] Update README and demo docs with eval history artifact names and local command examples.
- [ ] Update changelog.

## Task 5: Verification

- [ ] Run targeted tests.
- [ ] Run full `pytest`.
- [ ] Run `ruff check .`.
- [ ] Run `git diff --check`.

## Self-Review

- Spec coverage: script behavior, data model, CI integration, artifact upload, tests, docs, and non-goals are covered.
- Placeholder scan: no placeholders.
- Type consistency: field names match `scripts/summarize_eval_report.py` output.
