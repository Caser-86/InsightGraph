# CI Eval Gate Design

## Goal

Run the checked-in default Eval Bench gate in GitHub Actions so structure-quality regressions fail CI.

## Scope

In scope:

- Add an `Eval Gate` step to `.github/workflows/ci.yml` after pytest.
- Use `docs/evals/default.json` as the checked-in case set.
- Gate on `--min-score 85 --fail-on-case-failure`.
- Update `CHANGELOG.md` Unreleased entry.

Out of scope:

- Creating a separate GitHub Actions job.
- Uploading eval artifacts.
- Generating `reports/eval.json` or `reports/eval.md` in CI.
- Changing Eval Bench scoring or case file schema.

## CI Command

```bash
insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure
```

## Placement

The step runs after lint and pytest in the existing `test` job. This keeps the workflow minimal and avoids duplicate dependency installation.

## Verification

- Run the same eval gate command locally.
- Run full pytest.
- Run Ruff.
- Run `git diff --check`.
