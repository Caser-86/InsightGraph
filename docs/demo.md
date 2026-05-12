# InsightGraph Demo Guide

This guide is for live walkthroughs, internal demos, and local product reviews.

## Demo Goals

Use this guide when you want to show:

- the offline deterministic path
- the dashboard workflow
- the live LLM path
- observability and evaluation outputs

## Recommended Demo Order

1. Offline smoke demo
2. Dashboard demo
3. Live LLM demo
4. Observability demo
5. Eval bench demo

## Showcase Report

The showcase report is generated locally and should not be checked into git.
If you want to regenerate it, write it to:

- `reports/ai-coding-agents-technical-review.md`

## 1. Offline Smoke Demo

The safest default demo path is offline and deterministic.

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot"
```

To inspect the API-aligned payload shape:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --output-json
```

What this shows:

- end-to-end workflow without public network access
- deterministic report generation
- stable baseline behavior for local verification

## 2. Dashboard Demo

Start the API:

```bash
python -m pip install "uvicorn[standard]"
uvicorn insight_graph.api:app --reload
```

Open:

```text
http://127.0.0.1:8000/dashboard
```

Suggested walkthrough:

- submit an offline job
- watch status cards update
- inspect the report tab
- inspect evidence and citation support
- inspect safe tool and LLM metadata
- download Markdown / HTML exports

If `INSIGHT_GRAPH_API_KEY` is set, enter the key in the dashboard before using
job actions or streams.

## 3. Live LLM Demo

Configure an OpenAI-compatible endpoint first:

```bash
export INSIGHT_GRAPH_LLM_API_KEY="replace-with-your-api-key"
export INSIGHT_GRAPH_LLM_BASE_URL="https://your-provider.example/v1"
export INSIGHT_GRAPH_LLM_MODEL="your-model"
```

Then run a live preset:

```bash
python scripts/run_research.py "Technical review of AI coding agents for an engineering team: compare Cursor, OpenCode, Claude Code, GitHub Copilot, and Codeium/Windsurf across architecture, coding workflow integration, repository understanding, agentic capabilities, enterprise readiness, risks, and recommended adoption strategy. Include an evidence-backed competitive matrix and concise technical recommendations." --preset live-llm
```

To save a refreshed report:

```bash
python scripts/run_research.py "Technical review of AI coding agents for an engineering team: compare Cursor, OpenCode, Claude Code, GitHub Copilot, and Codeium/Windsurf across architecture, coding workflow integration, repository understanding, agentic capabilities, enterprise readiness, risks, and recommended adoption strategy. Include an evidence-backed competitive matrix and concise technical recommendations." --preset live-llm > reports/ai-coding-agents-technical-review.md
```

## 4. Observability Demo

Append safe LLM metadata to CLI output:

```bash
python -m insight_graph.cli research "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --show-llm-log
```

Write structured safe metadata logs:

```bash
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-llm --log-dir tmp_llm_logs
```

These logs include:

- stage
- provider
- selected model
- wire API
- token usage when available
- router metadata when routing is enabled

They do not include prompts, completions, raw responses, headers, request
bodies, or API keys by default.

## 5. Eval Bench Demo

Run deterministic offline evaluation:

```bash
insight-graph-eval --case-file docs/evals/default.json --markdown --output reports/eval.md
```

CI-style gating example:

```bash
insight-graph-eval --case-file docs/evals/default.json --min-score 85 --fail-on-case-failure --output reports/eval.json
```

Summarize a local eval JSON report:

```bash
python scripts/summarize_eval_report.py reports/eval.json --markdown
```

Append a local eval history row:

```bash
python scripts/append_eval_history.py --summary reports/eval-summary.json --history reports/eval-history.json --markdown reports/eval-history.md --run-id local --head-sha local --created-at 2026-04-29T00:00:00Z
```

## Validate The Showcase Report

Run the offline source validator:

```bash
python scripts/validate_sources.py reports/ai-coding-agents-technical-review.md --markdown
```

The generated showcase report is intentionally not tracked by git.

## Demo Notes

- Offline mode is best for stable smoke demos
- Live mode quality depends on the configured model and returned evidence
- The report is evidence-bounded and should surface uncertainty instead of inventing unsupported facts
- For full operator context, pair this file with `docs/README.md` and `docs/scripts.md`
