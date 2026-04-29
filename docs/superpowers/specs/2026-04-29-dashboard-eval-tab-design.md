# Dashboard Eval Tab Design

## Goal

Make CI Eval Bench artifacts discoverable from the dashboard without adding GitHub API integration or server-side artifact storage.

## Scope

In scope:

- Add an `Eval` tab to the existing dashboard tab bar.
- Render a static Eval Ops panel in the dashboard.
- Show the default case file, gate command, artifact name, full report files, summary files, history files, and local commands.
- Explain that the dashboard does not automatically fetch GitHub Actions artifacts.
- Update dashboard HTML tests and docs.

Out of scope:

- Fetching GitHub Actions artifacts from the dashboard.
- Adding a backend endpoint for CI artifacts.
- Rendering live trend charts.
- Running Eval Bench from the dashboard.

## Dashboard Content

The tab should include:

- Case file: `docs/evals/default.json`
- Gate: `insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure`
- Artifact: `eval-reports`
- Full reports: `reports/eval.json`, `reports/eval.md`
- Summary reports: `reports/eval-summary.json`, `reports/eval-summary.md`
- History reports: `reports/eval-history.json`, `reports/eval-history.md`
- Local commands for summary/history scripts
- Note: artifacts are downloaded from GitHub Actions, not fetched by the dashboard.

## Testing

Extend `tests/test_api.py::test_dashboard_returns_html` to assert the dashboard contains the new tab and key marker strings.

Verification:

- `python -m pytest tests/test_api.py::test_dashboard_returns_html -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
