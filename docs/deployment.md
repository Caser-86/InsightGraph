# InsightGraph Deployment Guide

This guide describes the supported deployment shape for the finished project.
It targets private demos, internal tools, and operator-controlled environments.

## Recommended Deployment Shape

- Python 3.11+ virtual environment
- `uvicorn` serving `insight_graph.api:app`
- SQLite for durable job metadata
- optional PostgreSQL checkpoints
- optional pgvector memory
- reverse proxy, VPN, or API gateway in front of the service

## Install

```bash
git clone https://github.com/Caser-86/InsightGraph.git
cd InsightGraph
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pip install "uvicorn[standard]"
```

## API Key

Protect the API with:

```bash
export INSIGHT_GRAPH_API_KEY="replace-with-shared-demo-key"
```

When this variable is set, all non-`/health` endpoints require either:

- `Authorization: Bearer <key>`
- `X-API-Key: <key>`

## Start The Service

```bash
uvicorn insight_graph.api:app --host 127.0.0.1 --port 8000
```

## Storage Matrix

| Surface | Variables | Purpose |
| --- | --- | --- |
| Jobs in memory | `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=memory` | Local single-process demos and tests |
| SQLite jobs | `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite`, `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH`, `INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER`, `INSIGHT_GRAPH_RESEARCH_JOBS_TERMINAL_RETENTION_DAYS` | Durable job metadata, worker leases, restart claim, terminal cleanup |
| PostgreSQL checkpoints | `INSIGHT_GRAPH_CHECKPOINT_BACKEND=postgres`, `INSIGHT_GRAPH_POSTGRES_DSN`, `INSIGHT_GRAPH_CHECKPOINT_RESUME` | Durable latest-state checkpoint resume keyed by job ID |
| pgvector memory | `INSIGHT_GRAPH_MEMORY_BACKEND=pgvector`, `INSIGHT_GRAPH_POSTGRES_DSN` | Long-term memory store and retrieval |
| pgvector document retrieval | `INSIGHT_GRAPH_DOCUMENT_INDEX_BACKEND=pgvector`, `INSIGHT_GRAPH_DOCUMENT_PGVECTOR_DSN` | Optional document retrieval backend |

## Restart And Resume

To enable restart-safe async execution:

```bash
export INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite
export INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/data/jobs.sqlite3
export INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER=1
export INSIGHT_GRAPH_CHECKPOINT_RESUME=1
```

Behavior:

- queued jobs are claimed on startup
- expired running jobs are requeued before the next worker claim
- checkpoint resume can continue from the latest stored state
- worker claim ownership protects terminal writes

## Live Providers

### Search

- `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo`
- `INSIGHT_GRAPH_SEARCH_PROVIDER=serpapi`
- `INSIGHT_GRAPH_SEARCH_PROVIDER=google`

### GitHub

- `INSIGHT_GRAPH_GITHUB_PROVIDER=live`

### SEC

- `INSIGHT_GRAPH_USE_SEC_FILINGS=1`
- `INSIGHT_GRAPH_USE_SEC_FINANCIALS=1`

### LLM

- `INSIGHT_GRAPH_LLM_BASE_URL`
- `INSIGHT_GRAPH_LLM_API_KEY`
- `INSIGHT_GRAPH_LLM_MODEL`
- `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`
- `INSIGHT_GRAPH_REPORTER_PROVIDER=llm`

## Trace Redaction

InsightGraph supports safe metadata tracing and optional full trace export.

Key variables:

- `INSIGHT_GRAPH_LLM_TRACE`
- `INSIGHT_GRAPH_LLM_TRACE_PATH`
- `INSIGHT_GRAPH_LLM_TRACE_FULL=1`

Guidance:

- metadata-only traces are safer for most deployments
- prompt/completion traces should be enabled only for local diagnostics
- API keys and sensitive tokens still go through redaction

## Offline And Smoke Validation

Health:

```bash
curl http://127.0.0.1:8000/health
```

Deployment smoke:

```bash
insight-graph-smoke http://127.0.0.1:8000
insight-graph-smoke http://127.0.0.1:8000 --api-key "$INSIGHT_GRAPH_API_KEY" --markdown
```

## Live Benchmark

Manual live benchmark is allowed only through explicit opt-in:

```bash
python scripts/benchmark_live_research.py --allow-live --output reports/live-benchmark.json
```

Or:

```bash
export INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1
python scripts/benchmark_live_research.py --output reports/live-benchmark.json --case-file docs/benchmarks/live-research-cases.json
```

This path may incur network/LLM cost. Do not commit generated live benchmark
reports.

## Operational Notes

- `live-research` is the only intended live product path.
- Keep offline deterministic behavior available for smoke checks and CI.
- Do not share JSON job metadata across multiple API workers.
- Prefer SQLite for durable async demos before introducing PostgreSQL.
- Treat MCP runtime invocation and real sandboxed Python execution as deferred
  features, not deployment defaults.
