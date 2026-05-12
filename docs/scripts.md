# InsightGraph Scripts

This document summarizes the scripts that are meant to be used directly by
operators and contributors.

## Script Inventory

| Script | Status | Purpose |
| --- | --- | --- |
| `scripts/run_research.py` | active | Run one research workflow and print Markdown or JSON |
| `scripts/run_with_llm_log.py` | active | Run one workflow and write safe LLM metadata logs |
| `scripts/validate_sources.py` | active | Validate report citations and references offline |
| `scripts/benchmark_research.py` | active | Run deterministic offline benchmark cases |
| `scripts/benchmark_live_research.py` | active | Manual opt-in live benchmark; may incur network/LLM cost |
| `scripts/validate_document_reader.py` | active | Validate local TXT/Markdown/HTML/PDF document reading |
| `scripts/validate_pdf_fetch.py` | active | Validate PDF fetch and retrieval metadata flows |
| `scripts/validate_github_search.py` | active | Validate deterministic and fake-live GitHub search mapping |
| `scripts/smoke_deployment.py` / `insight-graph-smoke` | active | Run API/dashboard deployment smoke checks |
| `scripts/summarize_eval_report.py` | active | Summarize eval JSON into compact outputs |
| `scripts/append_eval_history.py` | active | Append eval summary history artifacts |

## `run_research.py`

Examples:

```bash
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_research.py - < query.txt
python scripts/run_research.py "Compare Cursor, OpenCode, and GitHub Copilot" --preset live-research --output-json
```

Notes:

- offline is the default path
- live defaults are applied only through explicit presets or explicit env vars
- `--output-json` mirrors the API-aligned result shape

## `run_with_llm_log.py`

Examples:

```bash
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot"
python scripts/run_with_llm_log.py "Compare Cursor, OpenCode, and GitHub Copilot" --log-dir tmp_llm_logs
```

The log contains safe LLM metadata only:

- stage
- provider
- model
- duration
- token counts
- error summary

It does not store prompt/completion bodies, raw responses, headers, request
bodies, or API keys by default.

## `benchmark_research.py`

Examples:

```bash
python scripts/benchmark_research.py
python scripts/benchmark_research.py --markdown
```

This path stays offline and deterministic.

## `benchmark_live_research.py`

Examples:

```bash
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json --case-file docs/benchmarks/live-research-cases.json
```

Or:

```bash
export INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1
python scripts/benchmark_live_research.py --output reports/live-benchmark.json
```

Important:

- always uses `live-research`
- may incur network/LLM cost
- uses `docs/benchmarks/live-research-cases.json`
- do not commit generated live benchmark reports

Typical metrics include:

- `url_validation_rate`
- `citation_precision_proxy`
- `source_diversity_by_type`
- `source_diversity_by_domain`
- `section_coverage`
- `total_tokens`

## Document Validation Scripts

### `validate_document_reader.py`

Validates:

- TXT / Markdown / HTML / PDF parsing
- bounded snippets
- deterministic query ranking
- safety boundaries for local-only access

### `validate_pdf_fetch.py`

Validates:

- local PDF reading
- fake remote PDF fetch
- page metadata
- chunk metadata
- retrieval behavior

## Deployment Smoke

Examples:

```bash
insight-graph-smoke http://127.0.0.1:8000
insight-graph-smoke http://127.0.0.1:8000 --api-key "$INSIGHT_GRAPH_API_KEY" --markdown
```

The smoke script checks:

- `/health`
- `/dashboard`
- `/research/jobs/summary`

## Related Docs

- `README.md`
- `docs/QUICK_START.md`
- `docs/configuration.md`
- `docs/deployment.md`
- `docs/BENCHMARKS.md`
