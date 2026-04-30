# InsightGraph MVP Demo

This guide shows how to reproduce the MVP demo and inspect the generated report, workflow output, and safe LLM metadata.

## Showcase Report

The showcase report is generated locally rather than checked into git. Generate it with the Live LLM command below and save it under `reports/ai-coding-agents-technical-review.md` when needed.

## Offline Smoke Demo

The default path is deterministic/offline and does not call live search providers or LLM APIs:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

Use JSON output when you want to inspect the API-aligned payload shape:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

## Dashboard Demo

Start the API server:

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

Submit an offline query from the dashboard, then watch the job list, status cards,
workflow timeline, report, tool calls, and LLM metadata tabs update as the job
completes. The Live Events tab shows safe stage, tool call, LLM call, and report
events as the worker progresses. The dashboard uses the WebSocket job stream when
available and falls back to REST polling if the stream is unavailable. Completed
jobs expose Markdown and HTML download buttons in the Report tab. If
`INSIGHT_GRAPH_API_KEY` is set, enter that key in the dashboard before using job
actions, downloads, or streams.

## Live LLM Demo

Configure an OpenAI-compatible endpoint first:

```bash
export INSIGHT_GRAPH_LLM_API_KEY="replace-with-your-api-key"
export INSIGHT_GRAPH_LLM_BASE_URL="https://your-provider.example/v1"
export INSIGHT_GRAPH_LLM_MODEL="your-model"
```

Then run the live preset:

```bash
python scripts/run_research.py "Technical review of AI coding agents for an engineering team: compare Cursor, OpenCode, Claude Code, GitHub Copilot, and Codeium/Windsurf across architecture, coding workflow integration, repository understanding, agentic capabilities, enterprise readiness, risks, and recommended adoption strategy. Include an evidence-backed competitive matrix and concise technical recommendations." --preset live-llm
```

To save a refreshed report:

```bash
python scripts/run_research.py "Technical review of AI coding agents for an engineering team: compare Cursor, OpenCode, Claude Code, GitHub Copilot, and Codeium/Windsurf across architecture, coding workflow integration, repository understanding, agentic capabilities, enterprise readiness, risks, and recommended adoption strategy. Include an evidence-backed competitive matrix and concise technical recommendations." --preset live-llm > reports/ai-coding-agents-technical-review.md
```

## Observability Demo

Use `--show-llm-log` to append safe LLM metadata to CLI output:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --show-llm-log
```

Use the script form to write a structured safe metadata log:

```bash
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --log-dir tmp_llm_logs
```

The LLM log includes stage, provider, selected model, wire API, token usage when available, and router metadata when rules routing is enabled. It does not store prompts, completions, raw responses, headers, request bodies, or API keys.

## Eval Bench Demo

Run deterministic offline evaluation to score report structure and citation coverage:

```bash
insight-graph-eval --case-file docs/evals/default.json --markdown --output reports/eval.md
```

For CI-style gating, set a minimum average score and fail when any case fails:

```bash
insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure --output reports/eval.json
```

Use `docs/evals/default.json` for the checked-in default case set, or pass
`--case-file path/to/cases.json` to run a custom JSON case set.

GitHub Actions uploads an `eval-reports` artifact containing `reports/eval.json`,
`reports/eval.md`, `reports/eval-summary.json`, `reports/eval-summary.md`,
`reports/eval-history.json`, and `reports/eval-history.md` for each CI run.

Summarize a downloaded or local eval JSON report:

```bash
python scripts/summarize_eval_report.py reports/eval.json --markdown
```

Append a local eval history row:

```bash
python scripts/append_eval_history.py --summary reports/eval-summary.json --history reports/eval-history.json --markdown reports/eval-history.md --run-id local --head-sha local --created-at 2026-04-29T00:00:00Z
```

The Dashboard Overview tab shows the active Eval Gate case file, threshold,
artifact name, and report paths. The Dashboard Eval tab lists the `eval-reports`
artifact files and local summary/history commands for quick operator reference.

The eval bench clears live search and LLM opt-in environment variables while cases
run. It reports per-case score, pass/fail status, failed rules, references,
findings, matrix rows, tool calls, and LLM calls without using an LLM judge.

Report-quality metrics also appear in Eval Bench JSON and Markdown reports. They track section coverage, report depth, source diversity, citation support, unsupported claims, and duplicate source rate. These metrics are deterministic and offline by default.

## Validate the Showcase Report

Run the offline source validator:

```bash
python scripts/validate_sources.py reports/ai-coding-agents-technical-review.md --markdown
```

The report file is ignored because it is a generated artifact.

## Demo Notes

- Offline mode is the safest default for CI and local smoke tests.
- Live mode quality depends on the configured model and live search results.
- The report is evidence-bounded: if the workflow cannot verify a product-specific claim, it should frame that uncertainty rather than invent detail.
