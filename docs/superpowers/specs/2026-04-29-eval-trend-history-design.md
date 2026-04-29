# Eval Trend History Design

## Goal

Make Eval Bench quality changes observable across CI runs without adding a database, runtime API, or dashboard GitHub integration.

## Current Foundation

The project already has:

- `docs/evals/default.json` as the default case set.
- CI Eval Gate with `--min-score 85 --fail-on-case-failure`.
- CI `eval-reports` artifact containing full and summary Eval Bench reports.
- `scripts/summarize_eval_report.py` for compact summaries.
- Dashboard Overview metadata showing the active Eval Gate configuration.

## Proposed Approach

Use CI-generated `reports/eval-summary.json` as the stable unit for trend history. Add a future offline script that combines multiple summary files into a bounded history file and Markdown table.

This keeps history collection explicit and file-based. It avoids live GitHub API calls from the dashboard, avoids a database, and makes every trend input auditable.

## Data Model

Each history row should contain:

```json
{
  "run_id": "25087921734",
  "head_sha": "287c66a377ef09707ef8e2f8d10837c56c5886f1",
  "created_at": "2026-04-29T02:28:00Z",
  "case_count": 3,
  "average_score": 100,
  "passed_count": 3,
  "failed_count": 0,
  "failed_rules": {},
  "total_duration_ms": 23
}
```

The row combines CI metadata with the eval summary payload. CI metadata is supplied explicitly via CLI flags rather than inferred from GitHub APIs.

## Future CLI

```bash
python scripts/append_eval_history.py \
  --summary reports/eval-summary.json \
  --history reports/eval-history.json \
  --run-id "$GITHUB_RUN_ID" \
  --head-sha "$GITHUB_SHA" \
  --created-at "$GITHUB_RUN_STARTED_AT" \
  --limit 50

python scripts/append_eval_history.py \
  --summary reports/eval-summary.json \
  --history reports/eval-history.json \
  --markdown reports/eval-history.md \
  --run-id "$GITHUB_RUN_ID" \
  --head-sha "$GITHUB_SHA" \
  --created-at "$GITHUB_RUN_STARTED_AT" \
  --limit 50
```

`GITHUB_RUN_STARTED_AT` is not a default GitHub Actions variable, so the workflow should set `created_at` with an explicit UTC timestamp command before invoking the script.

## Storage Policy

- Keep history file generated, not checked in by default.
- Upload `reports/eval-history.json` and `reports/eval-history.md` in CI artifacts.
- Keep at most 50 rows.
- Newest rows first.
- Deduplicate by `run_id`.

## Deferred Dashboard Integration

Dashboard trend display should wait until history artifacts are stable. The dashboard should not call GitHub APIs directly in this project phase.

## Testing Strategy

When implemented, add tests for:

- Appending a row to empty history.
- Keeping newest rows first.
- Deduplicating by `run_id`.
- Enforcing `--limit`.
- Markdown trend table formatting.
- Safe exit code `2` for malformed summary/history input.

## Non-Goals

- Database storage.
- GitHub API download client.
- Dashboard GitHub authentication.
- Live trend fetching.
- Automatic release decisions from eval trends.
