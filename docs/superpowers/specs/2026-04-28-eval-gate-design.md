# Eval Gate Design

## Goal

Make `insight-graph-eval` usable as a CI gate by supporting external case files and threshold-based exit codes.

## Scope

In scope:

- Add `--case-file PATH` for JSON case configuration.
- Add `--min-score FLOAT` for average score threshold gating.
- Add `--fail-on-case-failure` for case-level gating.
- Write JSON or Markdown output before returning a gate failure exit code.
- Return safe non-zero codes for malformed case files and gate failures.

Out of scope:

- YAML case files.
- Enabling eval gate in GitHub Actions by default.
- LLM judge scoring.
- Dashboard integration.

## Case File

Format:

```json
{
  "cases": [
    {
      "query": "Compare Cursor and GitHub Copilot",
      "min_findings": 1,
      "min_matrix_rows": 1,
      "min_references": 2
    }
  ]
}
```

Validation:

- Top-level payload must be an object with `cases` list.
- Each case must include non-empty string `query`.
- Thresholds must be non-negative integers when provided.
- Malformed files return exit code `2` and a safe stderr message.

## Gate Behavior

- Default behavior remains exit code `0` if command execution succeeds.
- `--min-score N` returns exit code `1` when `summary.average_score < N`.
- `--fail-on-case-failure` returns exit code `1` when `summary.failed_count > 0`.
- Multiple gate failures can be reported together on stderr.
- `--output` writes the report before returning exit code `1`, so CI artifacts can be retained.

## CLI Examples

```bash
insight-graph-eval --case-file docs/evals/default.json --min-score 85
insight-graph-eval --markdown --output reports/eval.md --fail-on-case-failure
```

## Testing

Add tests for:

- Loading valid JSON case files.
- Rejecting malformed case files with exit code `2` and safe error.
- Returning `1` when average score is below `--min-score`.
- Returning `1` when `--fail-on-case-failure` sees failed cases.
- Writing `--output` before returning gate failure.

Verification:

- `python -m pytest tests/test_eval.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
