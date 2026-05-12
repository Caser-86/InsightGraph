# InsightGraph Configuration

This document describes the stable runtime knobs for InsightGraph.

## Product Path

The product-oriented path is `live-research`.

Offline remains the deterministic testing/CI fallback. Live search providers,
LLM calls, PostgreSQL, pgvector, external embeddings, and full trace payloads
are all explicit opt-in surfaces.

## `live-research` Preset Defaults

`--preset live-research` enables a reference-style networked run:

- `INSIGHT_GRAPH_USE_WEB_SEARCH=1`
- `INSIGHT_GRAPH_SEARCH_PROVIDER=duckduckgo`
- `INSIGHT_GRAPH_SEARCH_LIMIT=20`
- `INSIGHT_GRAPH_USE_GITHUB_SEARCH=1`
- `INSIGHT_GRAPH_GITHUB_PROVIDER=live`
- `INSIGHT_GRAPH_USE_NEWS_SEARCH=1`
- `INSIGHT_GRAPH_USE_SEC_FILINGS=1`
- `INSIGHT_GRAPH_USE_SEC_FINANCIALS=1`
- `INSIGHT_GRAPH_MULTI_SOURCE_COLLECTION=1`
- `INSIGHT_GRAPH_MAX_COLLECTION_ROUNDS=5`
- `INSIGHT_GRAPH_MAX_TOOL_CALLS=200`
- `INSIGHT_GRAPH_MAX_FETCHES=80`
- `INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN=120`
- `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`
- `INSIGHT_GRAPH_RELEVANCE_FILTER=1`
- `INSIGHT_GRAPH_RELEVANCE_JUDGE=openai_compatible`
- `INSIGHT_GRAPH_ANALYST_PROVIDER=llm`
- `INSIGHT_GRAPH_REPORTER_PROVIDER=llm`
- `INSIGHT_GRAPH_REPORT_REVIEW_PROVIDER=llm`

## Search And Fetch

### Search Provider Controls

- `INSIGHT_GRAPH_USE_WEB_SEARCH`
- `INSIGHT_GRAPH_SEARCH_PROVIDER`
- `INSIGHT_GRAPH_SEARCH_LIMIT`
- `INSIGHT_GRAPH_SEARCH_PROXY`
- `INSIGHT_GRAPH_SERPAPI_KEY`
- `INSIGHT_GRAPH_SERPAPI_ENGINE`

Supported provider values:

- `mock`
- `duckduckgo`
- `google`
- `serpapi`

### GitHub / News / SEC

- `INSIGHT_GRAPH_USE_GITHUB_SEARCH`
- `INSIGHT_GRAPH_GITHUB_PROVIDER=live`
- `INSIGHT_GRAPH_GITHUB_LIMIT`
- `INSIGHT_GRAPH_GITHUB_TOKEN`
- `INSIGHT_GRAPH_USE_NEWS_SEARCH`
- `INSIGHT_GRAPH_USE_SEC_FILINGS`
- `INSIGHT_GRAPH_USE_SEC_FINANCIALS`

### Rendered Fetch

- `INSIGHT_GRAPH_FETCH_RENDERED=1` enables optional Playwright-backed rendered
  fetch before bounded HTTP fallback.

### Source Semantics

Fetched evidence retains source metadata such as:

- search provider
- rank
- original query
- search snippet
- canonical URL
- reachable / trusted metadata
- fetch status and fetch error kind

Source types are classified as:

- `official_site`
- `docs`
- `github`
- `news`
- `blog`
- `sec`
- `paper`
- `unknown`

## Local Document Tools

### Document Reader

- `INSIGHT_GRAPH_USE_DOCUMENT_READER=1`
- supported files: `.txt`, `.md`, `.markdown`, `.html`, `.htm`, `.pdf`

`document_reader` reads only local files under the current working directory and
never fetches remote URLs.

### Search Document

- `INSIGHT_GRAPH_USE_SEARCH_DOCUMENT=1`
- `INSIGHT_GRAPH_DOCUMENT_RETRIEVAL=deterministic|vector`
- `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH`
- `INSIGHT_GRAPH_DOCUMENT_INDEX_BACKEND=pgvector`
- `INSIGHT_GRAPH_DOCUMENT_PGVECTOR_DSN`

This enables TOC/page/section-aware local document retrieval. The local JSON
index remains the default path. Optional pgvector-backed retrieval is still
explicit opt-in.

### File Tools

- `INSIGHT_GRAPH_USE_READ_FILE=1`
- `INSIGHT_GRAPH_USE_LIST_DIRECTORY=1`
- `INSIGHT_GRAPH_USE_WRITE_FILE=1`

These tools stay bounded to the working directory and do not execute code.

## Research Budgets

Global research budgets bound long-running collection loops.

Key variables:

- `INSIGHT_GRAPH_MAX_TOOL_CALLS`
- `INSIGHT_GRAPH_MAX_STEPS`
- `INSIGHT_GRAPH_MAX_FETCHES`
- `INSIGHT_GRAPH_MAX_EVIDENCE_PER_RUN`
- `INSIGHT_GRAPH_MAX_TOKENS`
- `INSIGHT_GRAPH_REPORT_INTENSITY`
- `INSIGHT_GRAPH_REPORT_REVIEW_PROVIDER`
- `INSIGHT_GRAPH_MAX_TOOL_ROUNDS`
- `INSIGHT_GRAPH_CONVERSATION_COMPRESSION`

Current report intensity tiers are tuned around the implemented long-form report
workflow. The default is `standard`.

## Research Jobs Persistence

`INSIGHT_GRAPH_RESEARCH_JOBS_PATH` enables opt-in JSON metadata persistence.
When unset, job metadata is process-local unless SQLite is selected.

For durable, multi-process-safe storage:

- `INSIGHT_GRAPH_RESEARCH_JOBS_BACKEND=sqlite`
- `INSIGHT_GRAPH_RESEARCH_JOBS_SQLITE_PATH=/path/jobs.sqlite3`
- `INSIGHT_GRAPH_RESEARCH_JOBS_STARTUP_WORKER=1`
- `INSIGHT_GRAPH_RESEARCH_JOBS_TERMINAL_RETENTION_DAYS=<days>`

JSON persistence marks interrupted queued/running jobs as failed on restart.
SQLite keeps queued jobs queued and requeues expired running jobs through worker
lease claim.

## Checkpoint Persistence

Checkpoint persistence is separate from research job metadata.

- `INSIGHT_GRAPH_CHECKPOINT_BACKEND=memory`
- `INSIGHT_GRAPH_CHECKPOINT_BACKEND=postgres`
- `INSIGHT_GRAPH_POSTGRES_DSN`
- `INSIGHT_GRAPH_CHECKPOINT_RESUME=1`

`PostgresCheckpointStore` persists the latest `GraphState` per `run_id`.
When `INSIGHT_GRAPH_CHECKPOINT_RESUME=1`, API/background jobs pass the job ID as
checkpoint `run_id` and can resume from the latest stored checkpoint.

## Long-Term Memory

Memory is opt-in.

- `INSIGHT_GRAPH_MEMORY_BACKEND=memory`
- `INSIGHT_GRAPH_MEMORY_BACKEND=pgvector`
- `INSIGHT_GRAPH_POSTGRES_DSN`
- `INSIGHT_GRAPH_EMBEDDING_PROVIDER`
- `INSIGHT_GRAPH_EMBEDDING_BASE_URL`
- `INSIGHT_GRAPH_EMBEDDING_API_KEY`
- `INSIGHT_GRAPH_EMBEDDING_MODEL`
- `INSIGHT_GRAPH_EMBEDDING_DIMENSIONS`
- `INSIGHT_GRAPH_USE_MEMORY_CONTEXT=1`
- `INSIGHT_GRAPH_MEMORY_WRITEBACK=1`

Current memory writeback stores:

- report summaries
- entities
- supported claims
- reference metadata
- source reliability notes

## Observability And Trace Controls

- `INSIGHT_GRAPH_LLM_TRACE`
- `INSIGHT_GRAPH_LLM_TRACE_PATH`
- `INSIGHT_GRAPH_LLM_TRACE_FULL=1`

Safe metadata traces are the default. Full prompt/completion traces require
explicit opt-in and still go through redaction controls.

## Live Benchmark

Manual live benchmark requires:

- `scripts/benchmark_live_research.py`
- `--allow-live`
- or `INSIGHT_GRAPH_ALLOW_LIVE_BENCHMARK=1`

Case profiles:

- `docs/benchmarks/live-research-cases.json`

Typical metrics:

- `url_validation_rate`
- `citation_precision_proxy`
- `source_diversity_by_type`
- `source_diversity_by_domain`
- `section_coverage`
- `total_tokens`

This path may incur network/LLM cost. Do not commit generated live benchmark
reports.
