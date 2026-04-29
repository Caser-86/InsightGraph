# Reference Parity Roadmap

This roadmap uses `wenyi-research-agent` as the reference standard for a production-grade deep research agent. InsightGraph keeps deterministic/offline defaults; live LLM, network, database, embeddings, MCP, and code execution remain explicit opt-in surfaces.

## Current Position

| Reference capability | InsightGraph status | Gap | Priority |
|---|---|---|---|
| Planner -> Executor -> Critic -> Reporter loop | Implemented as Planner -> Collector/Executor -> Analyst -> Critic -> Reporter | Mostly parity; graph naming differs | Low |
| Domain profiles from `domains/*.md` | Markdown-backed domain profiles implemented | Add more domain files over time | Medium |
| Entity resolver and query expansion | Implemented | Needs file-backed domain hints | Medium |
| Per-subtask multi-round tool loop | Implemented with configurable tool rounds | Expand query strategy diversity over time | Medium |
| Pre-search fetch pipeline | Search/fetch tools exist | Need automatic top-N fetch pipeline per search results | High |
| LLM relevance filtering | Implemented and opt-in | Needs tighter integration with pre-fetch loop | Medium |
| Conversation compression | Deterministic helper implemented | Need automatic long-run integration | High |
| Critic tried strategy blacklist | Implemented | Keep expanding strategy key coverage | Low |
| Reporter verified-only citations | Implemented | Need final URL revalidation and snippet-level citation tightening | High |
| Long PDF/RAG retrieval | Chunk/page/heading + lexical/vector fallback | Need persisted index and external embeddings | High |
| PostgreSQL checkpoint resume | Store + event/API resume hooks implemented | Need migration layer and restart E2E tests | Medium |
| pgvector memory | Store/search/delete + deterministic embeddings + Planner context injection | Need eval proof | High |
| Full LLM observability | Safe metadata + trace boundary | Need opt-in trace writer and CLI summary | High |
| Qwen/Minimax providers | OpenAI-compatible provider exists | Need named provider adapters | Medium |
| MCP registry/runtime | Spec registry only | Need safe runtime invocation | Medium |
| Code execution | Restricted expression boundary | Need real sandbox only if approved | Low |
| API parity | `/research/jobs` API exists | Need `/tasks` compatibility aliases if required | Medium |
| Dashboard parity | Dashboard exists | Need richer trace/tool/citation panels | Medium |
| Production benchmark | Eval Bench exists | Need reference-style live benchmark profile | High |

## Execution Order

### Phase A: Report Quality And Control Loop

1. File-backed domain profiles. **Implemented.**
2. Planner memory context injection. **Implemented.**
3. Planner consumption of memory context and tried strategies. **Implemented.**
4. Generic per-subtask multi-round tool loop. **Implemented.**
5. Automatic conversation compression in long-running loops.
6. Pre-search fetch pipeline hardening.
7. Reporter URL revalidation.
8. Snippet-level citation support tightening.
9. Opt-in full LLM trace writer.
10. `run_with_llm_log` token/call summary script.

### Phase B: Provider And Long-Document Parity

11. Named Qwen/DashScope LLM adapter.
12. Named Minimax LLM adapter.
13. Stage-aware model routing policy.
14. Persisted document vector index.
15. External embedding provider boundary.
16. `search_document` tool for TOC/page/vector retrieval.
17. PDF fetch/retrieval validation script.

### Phase C: Production Persistence And Runtime Parity

18. PostgreSQL migration layer for checkpoint and memory tables.
19. API/background restart resume E2E test.
20. Memory-on/off quality eval proof.
21. MCP runtime invocation behind explicit allowlist.
22. Python sandbox execution only if approved.
23. `/tasks` API compatibility layer.
24. Dashboard parity panels for traces, tools, citations, and token summary.
25. Reference-style production benchmark.

## Non-Negotiable Acceptance Criteria

- Default CLI, API, and tests remain offline and deterministic.
- Network, LLM, database, external embeddings, MCP, and code execution remain opt-in.
- New behavior uses TDD: RED test, GREEN implementation, focused verification.
- Each phase runs full `pytest`, full `ruff`, and `git diff --check` before merge.
- Each phase is committed independently and merged back to `master` with worktree cleanup.

## Next Phase

Phase 5 starts with automatic conversation compression in long-running loops. The first implementation should wire the deterministic compressor into bounded agent loops without changing default offline behavior or losing evidence IDs, source URLs, tool-call counts, and findings.
