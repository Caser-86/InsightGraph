# Eval Summary Script Design

## Goal

Add a small offline script that summarizes an existing Eval Bench JSON report for CI logs and future trend collection.

## Scope

In scope:

- Add `scripts/summarize_eval_report.py`.
- Read an Eval Bench JSON file from a path argument.
- Extract a stable summary subset from the top-level `summary` object.
- Print JSON by default.
- Print a compact Markdown table with `--markdown`.
- Return exit code `2` for unreadable, malformed, or invalid eval reports.
- Return exit code `0` for valid reports, even when `failed_count > 0`.

Out of scope:

- Re-running Eval Bench.
- Enforcing eval gates.
- Writing output files.
- CI integration.
- Historical trend storage.

## Summary Fields

The script returns exactly these fields:

```json
{
  "case_count": 3,
  "average_score": 100,
  "passed_count": 3,
  "failed_count": 0,
  "failed_rules": {},
  "total_duration_ms": 23
}
```

## CLI

```bash
python scripts/summarize_eval_report.py reports/eval.json
python scripts/summarize_eval_report.py reports/eval.json --markdown
```

## Markdown Output

```markdown
# Eval Summary

| Cases | Average score | Passed | Failed | Duration ms |
| ---: | ---: | ---: | ---: | ---: |
| 3 | 100 | 3 | 0 | 23 |
```

If failed rules exist, append a `Failed Rules` table.

## Testing

Add tests for:

- `summarize_eval_report()` extracts the summary subset.
- `format_markdown()` prints the compact table.
- `main()` reads a file and prints JSON.
- `main()` returns `2` for malformed JSON.

Verification:

- `python -m pytest tests/test_summarize_eval_report.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
