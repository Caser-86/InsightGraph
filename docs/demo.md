# InsightGraph MVP Demo

This guide shows how to reproduce the MVP demo and inspect the generated report, workflow output, and safe LLM metadata.

## Showcase Report

The checked-in showcase report is:

```text
reports/ai-coding-agents-technical-review.md
```

It compares Cursor, OpenCode, Claude Code, GitHub Copilot, and Codeium/Windsurf for a technical-review audience. The report was generated through the InsightGraph research workflow and validated with the offline source validator.

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
report, tool calls, and LLM metadata tabs update as the job completes. If
`INSIGHT_GRAPH_API_KEY` is set, enter that key in the dashboard before using job
actions.

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

## Validate the Showcase Report

Run the offline source validator:

```bash
python scripts/validate_sources.py reports/ai-coding-agents-technical-review.md --markdown
```

Expected result for the checked-in report:

```text
OK: true
Issues: 0
```

## Demo Notes

- Offline mode is the safest default for CI and local smoke tests.
- Live mode quality depends on the configured model and live search results.
- The report is evidence-bounded: if the workflow cannot verify a product-specific claim, it should frame that uncertainty rather than invent detail.
