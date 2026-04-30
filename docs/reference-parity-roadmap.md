# Reference Parity Roadmap

This roadmap uses `wenyi-research-agent` as the reference standard for a production-grade deep research agent. InsightGraph keeps deterministic/offline defaults; live LLM, network, database, embeddings, MCP, and code execution remain explicit opt-in surfaces.

Current product path is `live-research`. Offline remains the deterministic testing/CI fallback. Batch 14 docs final alignment complete.

## Current Position

| Reference capability | InsightGraph status | Gap | Priority |
|---|---|---|---|
| Planner -> Executor -> Critic -> Reporter loop | Implemented as Planner -> Collector/Executor -> Analyst -> Critic -> Reporter | Mostly parity; graph naming differs | Low |
| Domain profiles from `domains/*.md` | Markdown-backed domain profiles implemented | Add more domain files over time | Medium |
| Entity resolver and query expansion | Implemented | Needs file-backed domain hints | Medium |
| Per-subtask multi-round tool loop | Implemented with configurable tool rounds | Expand query strategy diversity over time | Medium |
| Pre-search fetch pipeline | Implemented with bounded fetch fan-out | Add cache/retry policies only if needed | Medium |
| LLM relevance filtering | Implemented and opt-in | Needs tighter integration with pre-fetch loop | Medium |
| Conversation compression | Opt-in Executor integration implemented | Need broader graph/runtime memory integration | Medium |
| Critic tried strategy blacklist | Implemented | Keep expanding strategy key coverage | Low |
| Reporter verified-only citations | URL revalidation and snippet support metadata implemented | Improve live LLM judge only if needed | Medium |
| Long PDF/RAG retrieval | `search_document` tool + chunk/page/heading + lexical/vector fallback + opt-in local JSON persisted index + embedding provider boundary | Need pgvector/TOC production RAG and live validation | High |
| PostgreSQL checkpoint resume | Store + event/API resume hooks + migration layer + SQLite worker resume claim implemented | Keep hardening restart E2E as bugs appear | Low |
| pgvector memory | Store/search/delete + deterministic/external embeddings + Planner context injection + writeback/API/eval proof implemented | Improve memory quality over time | Low |
| Full LLM observability | Trace IDs, redacted JSONL trace controls, dashboard panels, and runner summary implemented | Extend to relevance judge if needed | Low |
| LLM provider presets | Local/self-hosted presets plus Qwen/DashScope config are implemented on the OpenAI-compatible client | Add Minimax preset if needed | Medium |
| MCP registry/runtime | Spec registry only | Deferred pending explicit approval | Deferred |
| Code execution | Restricted expression boundary | Real sandbox deferred pending explicit approval | Deferred |
| API parity | `/research/jobs` API exists | `/tasks` aliases deferred until a real consumer requires them | Deferred |
| Dashboard parity | Dashboard evidence/citation/quality panels implemented | Continue polish as needed | Low |
| Production benchmark | Manual opt-in live benchmark implemented | Keep live runs manual/cost-aware | Low |

## Execution Order

### Phase A: Report Quality And Control Loop

1. File-backed domain profiles. **Implemented.**
2. Planner memory context injection. **Implemented.**
3. Planner consumption of memory context and tried strategies. **Implemented.**
4. Generic per-subtask multi-round tool loop. **Implemented.**
5. Automatic conversation compression in long-running loops. **Implemented.**
6. Pre-search fetch pipeline hardening. **Implemented.**
7. Reporter URL revalidation. **Implemented.**
8. Snippet-level citation support tightening. **Implemented.**
9. Opt-in full LLM trace writer. **Implemented.**
10. `run_with_llm_log` token/call summary script. **Implemented.**

### Phase B: Provider And Long-Document Parity

11. Multi-provider LLM config presets. **Implemented.**
12. Named Minimax LLM preset. **Deferred until needed.**
13. Stage-aware model routing policy. **Implemented.**
14. Persisted document vector index. **Implemented.**
15. External embedding provider boundary. **Implemented.**
16. `search_document` tool for TOC/page/vector retrieval. **Implemented.**
17. PDF fetch/retrieval validation script. **Implemented.**

### Phase C: Production Persistence And Runtime Parity

18. PostgreSQL migration layer for checkpoint and memory tables. **Implemented.**
19. API/background restart resume E2E path. **Implemented via checkpoint resume and SQLite worker claim; keep hardening as bugs appear.**
20. Memory quality eval proof. **Implemented.**
21. MCP runtime invocation behind explicit allowlist. **Deferred until explicit approval.**
22. Python sandbox execution only if approved. **Deferred until explicit approval.**
23. `/tasks` API compatibility layer. **Deferred until a real consumer requires it.**
24. Dashboard parity panels for traces, tools, citations, and token summary. **Implemented.**
25. Reference-style production benchmark. **Implemented as manual opt-in live benchmark.**

## Non-Negotiable Acceptance Criteria

- Default CLI, API, and tests remain offline and deterministic.
- Network, LLM, database, external embeddings, MCP, and code execution remain opt-in.
- New behavior uses TDD: RED test, GREEN implementation, focused verification.
- Each phase runs full `pytest`, full `ruff`, and `git diff --check` before merge.
- Each phase is committed independently and merged back to `master` with worktree cleanup.

## Next Phase

Next work should be chosen from explicit user priorities. Deferred items stay out of scope until approved.
