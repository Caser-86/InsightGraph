# Eval Bench Design

## Goal

Add a deterministic offline evaluation bench that scores InsightGraph research outputs for structural quality and regression tracking.

## Scope

In scope:

- Add package module `insight_graph.eval` with benchmark cases, scoring rules, JSON output, Markdown output, and CLI entrypoint.
- Add console script `insight-graph-eval`.
- Keep `scripts/benchmark_research.py` compatible by delegating to the package module.
- Support `--markdown` and `--output PATH`.
- Keep offline environment isolation and safe generic errors.

Out of scope:

- LLM-as-judge scoring.
- CI workflow enforcement of score thresholds.
- Network/live search evaluation by default.
- Dashboard integration.

## Eval Cases

Default cases remain deterministic offline prompts:

- Compare Cursor, OpenCode, and GitHub Copilot.
- Analyze AI coding agents market positioning.
- Compare Claude Code, Codeium, and Windsurf.

Each case has thresholds:

- minimum findings: 1
- minimum competitive matrix rows: 1
- minimum references: 2

## Scoring

Each case gets `score` from 0 to 100. Rules are equally weighted:

- `critique_passed`
- `has_report`
- `has_competitive_matrix_section`
- `references_meet_minimum`
- `findings_meet_minimum`
- `matrix_rows_meet_minimum`
- `findings_cite_evidence`
- `matrix_rows_cite_evidence`

`passed` is true when score is at least 80 and no workflow error occurred.

## Output Shape

JSON default:

```json
{
  "cases": [
    {
      "query": "Compare Cursor, OpenCode, and GitHub Copilot",
      "duration_ms": 25,
      "score": 100,
      "passed": true,
      "rules": [{"id":"critique_passed","passed":true,"points":12.5}],
      "finding_count": 2,
      "competitive_matrix_row_count": 3,
      "reference_count": 3,
      "tool_call_count": 1,
      "llm_call_count": 0,
      "critique_passed": true,
      "report_has_competitive_matrix": true
    }
  ],
  "summary": {
    "case_count": 1,
    "average_score": 100,
    "passed_count": 1,
    "failed_count": 0,
    "failed_rules": {}
  }
}
```

Markdown output includes case table, summary table, failed rule summary, and errors section when present.

## CLI

```bash
insight-graph-eval
insight-graph-eval --markdown
insight-graph-eval --output reports/eval.json
insight-graph-eval --markdown --output reports/eval.md
```

`--output` writes UTF-8 text and still returns exit code 0 on successful command execution. Workflow case failures are represented in the payload, not as process failures.

## Compatibility

`scripts/benchmark_research.py` re-exports the new module functions used by existing tests and delegates its `main()` to `insight_graph.eval.main()`.

## Testing

Add tests for:

- Case scoring and rule breakdown.
- Summary average score and failed rules.
- Markdown output includes score/pass columns.
- `--output` writes JSON/Markdown.
- Console script is registered in `pyproject.toml`.
- Existing benchmark script tests continue to pass.

Verification:

- `python -m pytest tests/test_eval.py tests/test_benchmark_research.py -v`
- full `pytest`
- `ruff check .`
- `git diff --check`
