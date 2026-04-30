# Roadmap

## Current Product Path

The product path is `live-research`.

Offline remains the deterministic testing/CI fallback. Network, LLM, database, external embeddings, full trace payloads, and live benchmark behavior remain explicit opt-in surfaces.

The next optimization goal is 生成高质量、可验证深度研究报告. All future work should improve report correctness, depth, source quality, citation support, or operator observability before expanding high-risk runtime surfaces.

## Next Optimization Plan

### Batch A: Report Quality v3

Goal: make final reports more complete, source-grounded, and comparable to mature deep-research outputs.

1. Add stronger section-level report contracts.
- Define required sections per domain: Executive Summary, Background, Market/Company/Product Analysis, Competitive Landscape, Risks, Outlook, References.
- Add tests that deterministic and LLM Reporter outputs include required sections when section plans exist.
- Files: `src/insight_graph/agents/reporter.py`, `src/insight_graph/report_quality/domain_profiles.py`, `tests/test_agents.py`.

2. Add claim density and evidence density metrics.
- Track claims per section, evidence per claim, unsupported claims per section, and citation support ratio.
- Add Eval Bench summary fields and Markdown columns.
- Files: `src/insight_graph/eval.py`, `tests/test_eval.py`.

3. Improve Critic replan specificity.
- Emit missing source type, missing entity, missing section, and unsupported claim hints as structured metadata.
- Ensure retry queries use those hints without repeating tried strategies.
- Files: `src/insight_graph/agents/critic.py`, `src/insight_graph/agents/executor.py`, `tests/test_agents.py`, `tests/test_executor.py`.

4. Add report completeness gates.
- Gate report output on section coverage, citation support, source diversity, and unsupported claim count.
- Keep gates offline/deterministic by default.
- Files: `src/insight_graph/eval.py`, `docs/evals/default.json`, `tests/test_eval.py`.

### Batch B: Live Benchmark Case Profiles

Goal: measure real report quality with manual, cost-aware benchmark cases.

1. Add benchmark case files.
- Create curated live cases for AI coding agents, public company analysis, SEC filing risk analysis, and technology trend analysis.
- Each case defines expected sections, required source types, minimum source diversity, and report depth target.
- Files: `docs/benchmarks/live-research-cases.json`, `tests/test_benchmark_live_research.py`.

2. Expand live benchmark metrics.
- Add URL validation rate, citation precision proxy, source diversity by type/domain, report depth, section coverage, token totals, runtime, and LLM/tool call counts.
- Files: `scripts/benchmark_live_research.py`, `tests/test_benchmark_live_research.py`.

3. Add benchmark artifact examples.
- Document safe example output without committing generated live reports.
- Files: `docs/scripts.md`, `docs/configuration.md`, `README.md`.

### Batch C: Production RAG Hardening

Goal: improve long-document grounding without making heavy services mandatory.

1. Add document citation spans.
- Preserve page, section heading, chunk index, and snippet offsets where available.
- Use spans in citation support output.
- Files: `src/insight_graph/state.py`, `src/insight_graph/tools/document_reader.py`, `src/insight_graph/tools/search_document.py`, `tests/test_document_index.py`.

2. Add cross-document retrieval scoring.
- Prefer authoritative documents, exact section hits, recent chunks, and entity matches.
- Keep deterministic lexical/vector fallback.
- Files: `src/insight_graph/report_quality/document_index.py`, `tests/test_document_index.py`.

3. Add optional pgvector-backed document retrieval design.
- Keep local JSON index as default.
- Only enable pgvector retrieval with explicit env vars and migration coverage.
- Files: `src/insight_graph/report_quality/document_index.py`, `src/insight_graph/persistence/migrations.py`, `tests/test_document_index.py`, `tests/test_migrations.py`.

### Batch D: Memory Quality Loop

Goal: make long-term memory improve future reports without polluting evidence.

1. Improve memory writeback taxonomy.
- Separate report summaries, entities, supported claims, references, and source reliability notes.
- Include expiration/refresh metadata for stale facts.
- Files: `src/insight_graph/memory/writeback.py`, `tests/test_memory.py`.

2. Add memory retrieval quality controls.
- Filter memory by domain, entity, embedding config, recency, and support status.
- Prevent memory-only facts from becoming final report claims without fresh evidence.
- Files: `src/insight_graph/agents/planner.py`, `src/insight_graph/memory/store.py`, `tests/test_agents.py`, `tests/test_memory.py`.

3. Expand memory eval proof.
- Compare memory off/on across multiple fake cases and report quality deltas.
- Files: `src/insight_graph/eval.py`, `tests/test_eval.py`.

### Batch E: Dashboard Productization

Goal: make quality issues visible during and after research jobs.

1. Add report-quality cards.
- Show section coverage, citation support, source diversity, unsupported claims, URL validation, token totals, runtime.
- Files: `src/insight_graph/dashboard.py`, `tests/test_api.py`.

2. Add evidence drilldown UX.
- Show evidence title, URL, source type, fetch status, citation support status, section ID, and snippets.
- Files: `src/insight_graph/dashboard.py`, `tests/test_api.py`.

3. Add trace/event filtering.
- Filter job events by stage, type, and trace ID.
- Files: `src/insight_graph/dashboard.py`, `src/insight_graph/api.py`, `tests/test_api.py`.

### Batch F: API And Operations Hardening

Goal: keep production paths reliable without expanding public surface unnecessarily.

1. Add job retention and cleanup policy docs/tests.
- Define terminal job retention, SQLite cleanup, and artifact retention behavior.
- Files: `src/insight_graph/research_jobs.py`, `src/insight_graph/research_jobs_sqlite_backend.py`, `docs/research-jobs-api.md`, tests.

2. Add restart/resume smoke path.
- Cover queued jobs, expired running jobs, checkpoints, and worker claim behavior.
- Files: `tests/test_research_jobs_sqlite_backend.py`, `tests/test_api.py`.

3. Add deployment runbook alignment.
- Clarify env vars for API keys, SQLite, PostgreSQL, pgvector, live providers, trace redaction, and benchmark costs.
- Files: `docs/deployment.md`, `docs/configuration.md`, `README.md`.

## Deferred Until Other Optimizations Are Complete

These four items expand attack surface, API surface, or release risk. Do them only after the report-quality work above is complete and there is an explicit decision to proceed.

1. MCP runtime invocation behind allowlist.
- Purpose: actually invoke external MCP tools, not just store metadata specs.
- Required safety: allowlist, auth boundaries, request/response redaction, audit logs, timeout/resource limits.

2. Real sandboxed Python/code execution.
- Purpose: run real analysis code for CSV/Excel/statistics/financial modeling.
- Required safety: sandbox, network isolation, filesystem isolation, CPU/memory/time limits, dependency policy.

3. `/tasks` API compatibility aliases.
- Purpose: provide reference-compatible aliases for `/research/jobs` if a real consumer needs them.
- Required safety: stable compatibility contract and duplicated API docs/tests.

4. release/deploy/force-push automation.
- Purpose: automate tags/releases/deploys only after the product path is stable.
- Required safety: branch protections, dry runs, manual approval gates, no force push to protected branches.
