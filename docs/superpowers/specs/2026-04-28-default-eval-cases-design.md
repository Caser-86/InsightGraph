# Default Eval Cases Design

## Goal

Add a checked-in default Eval Bench case file so the new eval gate has a reusable project-standard case set.

## Scope

In scope:

- Add `docs/evals/default.json`.
- Use the same three deterministic offline prompts as the built-in eval defaults.
- Set explicit thresholds on every case: `min_findings: 1`, `min_matrix_rows: 1`, `min_references: 2`.
- Document `--case-file docs/evals/default.json` in README and demo docs.
- Add tests proving the checked-in file can be loaded and contains valid defaults.

Out of scope:

- Adding eval to CI workflow.
- Generating `reports/eval.json` or `reports/eval.md`.
- Changing scoring logic.
- Adding live-search or LLM eval cases.

## File Format

```json
{
  "cases": [
    {
      "query": "Compare Cursor, OpenCode, and GitHub Copilot",
      "min_findings": 1,
      "min_matrix_rows": 1,
      "min_references": 2
    }
  ]
}
```

## Usage

```bash
insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure
```

## Testing

Add tests for:

- `docs/evals/default.json` exists and loads via `load_eval_cases()`.
- It contains exactly three cases.
- All cases have non-empty queries and expected threshold values.

Verification:

- `python -m pytest tests/test_eval.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
