# Roadmap

## Current Product Path

The product path is `live-research`.

Offline remains the deterministic testing/CI fallback. Network, LLM, database,
external embeddings, full trace payloads, and live benchmark behavior remain
explicit opt-in surfaces.

The optimization goal remains high-quality, evidence-grounded deep research
reports. Future work should improve report correctness, depth, source quality,
citation support, or operator observability before expanding high-risk runtime
surfaces.

## Completed Optimization Batches

A-F complete. The report-quality and operations-hardening route below is
implemented, tested, and documented.

### Batch A: Report Quality v3 - complete

- Stronger section-level report contracts for deterministic and LLM Reporter outputs
- Claim density, evidence density, unsupported-claim, citation-support, and section metrics
- More specific Critic replan metadata for missing source type, entity, section, and unsupported claims
- Deterministic report completeness gates for section coverage, citation support, source diversity, and unsupported claims

### Batch B: Live Benchmark Case Profiles - complete

- Curated manual live benchmark cases
- Expanded live benchmark metrics for URL validation, citation precision proxy, source diversity, report depth, section coverage, runtime, token totals, and LLM/tool calls
- Safe benchmark artifact documentation without committing generated live reports

### Batch C: Production RAG Hardening - complete

- Document citation spans preserve page, section heading, chunk index, and snippet offsets
- Cross-document retrieval scoring prefers authoritative documents, exact section hits, recent chunks, and entity matches
- Optional pgvector-backed document retrieval remains explicit opt-in

### Batch D: Memory Quality Loop - complete

- Memory writeback taxonomy for summaries, entities, supported claims, references, and source reliability notes
- Memory retrieval quality controls by domain, entity, embedding config, recency, and support state
- Memory on/off eval proof with quality delta metadata

### Batch E: Dashboard Productization - complete

- Report-quality cards for section coverage, citation support, source diversity, unsupported claims, URL validation, tokens, and runtime
- Evidence drilldown for URL, source type, fetch state, citation state, section ID, and snippet
- Event and stream filtering by stage, type, and trace ID

### Batch F: API And Operations Hardening - complete

- Terminal job retention and cleanup policy
- Restart/resume smoke path for queued jobs, expired running jobs, checkpoints, and worker claim behavior
- Deployment guidance for API keys, SQLite, PostgreSQL, pgvector, live providers, trace redaction, and benchmark costs

## Remaining Explicit-Decision Work

These items expand API surface, attack surface, or release risk. Do them only
with explicit approval and a dedicated safety review.

0. V3 Deep Research Loop
- Priority: high for report quality, but intentionally deferred until the current quality diagnostics and optional review path have enough live-run evidence
- Purpose: automatically review report quality, generate follow-up searches, recollect evidence, and rewrite the report until a target score or budget limit is reached

1. `/tasks` API compatibility aliases
- Purpose: provide reference-compatible aliases for `/research/jobs` when a real consumer requires them

2. MCP runtime invocation behind allowlist
- Purpose: invoke external MCP tools under a strict allowlist and redaction boundary

3. release/deploy automation dry-run only
- Purpose: automate release readiness checks without push, tag, or force-push behavior

4. Real sandboxed Python/code execution
- Purpose: support true CSV/Excel/statistics/financial modeling under a real sandbox

## Current Status Summary

- The project is functionally complete for its intended current scope
- `live-research` is the supported live product route
- Offline deterministic mode remains the default verification route
- Higher-risk expansion work remains intentionally deferred
