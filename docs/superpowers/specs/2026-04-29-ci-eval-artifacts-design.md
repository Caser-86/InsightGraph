# CI Eval Artifacts Design

## Goal

Upload Eval Bench JSON and Markdown reports from GitHub Actions so CI eval results are inspectable even when the gate fails.

## Scope

In scope:

- Generate `reports/eval.json` in CI using `docs/evals/default.json`.
- Generate `reports/eval.md` in CI using the same default case file.
- Upload both files with `actions/upload-artifact` as `eval-reports`.
- Keep the existing blocking Eval Gate step.
- Update README, demo docs, and changelog.

Out of scope:

- Changing Eval Bench CLI behavior.
- Adding multi-output CLI support.
- Committing generated `reports/eval.*` files.
- Adding historical trend storage.

## CI Flow

The existing `test` job remains a single job:

1. Install dependencies.
2. Run Ruff.
3. Run pytest.
4. Create `reports/`.
5. Write `reports/eval.json`.
6. Write `reports/eval.md`.
7. Run the blocking Eval Gate.
8. Upload `reports/eval.*` with `if: always()`.

Uploading after the gate with `if: always()` ensures reports are available when the gate fails after report generation.

## Verification

- Locally generate `reports/eval.json`.
- Locally generate `reports/eval.md`.
- Run the local eval gate via module entry.
- Run full pytest.
- Run Ruff.
- Run `git diff --check`.
- Remove locally generated eval reports before finishing.
