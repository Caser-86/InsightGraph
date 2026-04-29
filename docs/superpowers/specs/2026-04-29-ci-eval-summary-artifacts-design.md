# CI Eval Summary Artifacts Design

## Goal

Include compact Eval Bench summary artifacts in CI so users can inspect aggregate scores without opening the full eval report.

## Scope

In scope:

- Generate `reports/eval-summary.json` from `reports/eval.json` in CI.
- Generate `reports/eval-summary.md` from `reports/eval.json` in CI.
- Upload both summary files in the existing `eval-reports` artifact.
- Add a lightweight workflow text test to prevent accidentally dropping summary generation.
- Update README, demo docs, and changelog.

Out of scope:

- Changing `scripts/summarize_eval_report.py` behavior.
- Historical trend storage.
- GitHub API artifact download tooling.
- Dashboard trend display.

## CI Flow

The existing `Generate Eval Reports` step writes full reports first:

```bash
insight-graph-eval --case-file docs/evals/default.json --output reports/eval.json
insight-graph-eval --case-file docs/evals/default.json --markdown --output reports/eval.md
```

Then it summarizes `reports/eval.json`:

```bash
python scripts/summarize_eval_report.py reports/eval.json > reports/eval-summary.json
python scripts/summarize_eval_report.py reports/eval.json --markdown > reports/eval-summary.md
```

The artifact upload path lists all four expected files explicitly.

## Testing

Add `tests/test_ci_workflow.py` to read `.github/workflows/ci.yml` as text and assert it contains:

- summary JSON generation command
- summary Markdown generation command
- upload paths for all four eval report files

Verification:

- `python -m pytest tests/test_ci_workflow.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
