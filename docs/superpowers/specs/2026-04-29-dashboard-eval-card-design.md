# Dashboard Eval Card Design

## Goal

Expose the active Eval Bench gate and CI report artifacts inside the dashboard without adding new APIs or changing job behavior.

## Scope

In scope:

- Add a static Eval Gate card to the Dashboard Overview tab.
- Show the default case file: `docs/evals/default.json`.
- Show the gate policy: `--min-score 85 --fail-on-case-failure`.
- Show the CI artifact name: `eval-reports`.
- Show report paths: `reports/eval.json` and `reports/eval.md`.
- Update dashboard HTML tests and docs.

Out of scope:

- Adding a new Eval API endpoint.
- Reading CI artifacts from GitHub.
- Showing historical eval trends.
- Adding a dedicated Eval tab.
- Running evals from the dashboard.

## Dashboard Behavior

The Overview tab remains the default detail view. Its existing metadata grid gains one static info card labeled `Eval Gate`. The card explains which case file and thresholds CI uses and where to download reports from CI.

This keeps eval visibility close to job health metadata while avoiding a mostly static extra tab.

## Testing

Update `tests/test_api.py::test_dashboard_returns_html` to assert the dashboard includes:

- `Eval Gate`
- `docs/evals/default.json`
- `--min-score 85 --fail-on-case-failure`
- `eval-reports`
- `reports/eval.json`
- `reports/eval.md`

Verification:

- `python -m pytest tests/test_api.py::test_dashboard_returns_html -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
