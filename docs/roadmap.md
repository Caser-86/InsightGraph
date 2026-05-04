# Roadmap

## Current Product Path

The product path is `live-research`.

Offline remains the deterministic testing/CI fallback. Network, LLM, database, external embeddings, full trace payloads, and live benchmark behavior remain explicit opt-in surfaces.

The optimization goal remains 生成高质量、可验证深度研究报告. Future work should improve report correctness, depth, source quality, citation support, or operator observability before expanding high-risk runtime surfaces.

## Completed Optimization Batches

A-F complete. The report-quality and operations hardening route below is implemented, tested, and documented.

### Batch A: Report Quality v3 - complete

- Stronger section-level report contracts for deterministic and LLM Reporter outputs.
- Claim density, evidence density, unsupported-claim, citation-support, and section metrics in Eval Bench summaries and Markdown output.
- More specific Critic replan metadata for missing source type, entity, section, and unsupported-claim hints.
- Deterministic report completeness gates for section coverage, citation support, source diversity, and unsupported claims.

### Batch B: Live Benchmark Case Profiles - complete

- Curated manual live benchmark cases for AI coding agents, public company analysis, SEC risk analysis, and technology trend analysis.
- Expanded live benchmark metrics for URL validation, citation precision proxy, source diversity, report depth, section coverage, runtime, token totals, and LLM/tool call counts.
- Safe benchmark artifact documentation without committing generated live reports.

### Batch C: Production RAG Hardening - complete

- Document citation spans preserve page, section heading, chunk index, and snippet offsets where available.
- Cross-document retrieval scoring prefers authoritative documents, exact section hits, recent chunks, and entity matches while keeping deterministic fallback.
- Optional pgvector-backed document retrieval design remains explicit opt-in; local JSON index stays default.

### Batch D: Memory Quality Loop - complete

- Memory writeback taxonomy separates report summaries, entities, supported claims, references, source reliability notes, and expiration metadata.
- Memory retrieval quality controls filter by domain, entity, embedding config, recency, and support status.
- Memory eval proof compares memory off/on across fake cases and reports quality deltas.

### Batch E: Dashboard Productization - complete

- Report-quality cards expose section coverage, citation support, source diversity, unsupported claims, URL validation, token totals, and runtime.
- Evidence drilldown shows evidence title, URL, source type, fetch status, citation support status, section ID, and snippets.
- Job event and stream filtering supports stage, type, and trace ID.

### Batch F: API And Operations Hardening - complete

- Terminal job retention and cleanup policy covers SQLite cleanup and artifact retention boundaries.
- Restart/resume smoke path covers queued jobs, expired running jobs, checkpoints, and worker claim behavior.
- Deployment runbook aligns API keys, SQLite, PostgreSQL, pgvector, live providers, trace redaction, and benchmark costs.

## Remaining Explicit-Decision Work

These items expand API surface, attack surface, or release risk. Do them only with an explicit decision and dedicated safety review.

0. V3 Deep Research Loop.
- Priority: high for report quality, but intentionally deferred until V1 quality diagnostics and optional V2 LLM review have enough live-run evidence.
- Purpose: automatically review report quality, generate gap-specific follow-up searches, recollect evidence, and rewrite the report until a target score or budget limit is reached.
- Required safety: hard search/tool/token budgets, duplicate-query suppression, citation validation after every rewrite, visible quality diagnostics, and explicit operator controls for cost.

1. `/tasks` API compatibility aliases.
- Priority: highest among deferred items because it is mostly an API adapter and has the smallest security footprint.
- Purpose: provide reference-compatible aliases for `/research/jobs` if a real consumer needs them.
- Required safety: stable compatibility contract, duplicated API docs/tests, no behavior drift from `/research/jobs`.

2. MCP runtime invocation behind allowlist.
- Priority: medium; valuable only when external tool invocation has a concrete use case.
- Purpose: actually invoke external MCP tools, not just store metadata specs.
- Required safety: allowlist, auth boundaries, request/response redaction, audit logs, timeout/resource limits.

3. release/deploy automation dry-run only.
- Priority: medium-low; useful after release cadence exists, but should start as non-destructive checks.
- Purpose: automate release readiness checks and dry-run deploy steps without pushing, tagging, or force-pushing.
- Required safety: branch protections, manual approval gates, dry runs by default, no force push to protected branches.

4. Real sandboxed Python/code execution.
- Priority: lowest and highest risk.
- Purpose: run real analysis code for CSV/Excel/statistics/financial modeling.
- Required safety: sandbox, network isolation, filesystem isolation, CPU/memory/time limits, dependency policy.
