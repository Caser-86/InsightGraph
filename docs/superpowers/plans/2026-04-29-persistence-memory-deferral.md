# Persistence And Memory Deferral Plan

> **For agentic workers:** PostgreSQL checkpoint resume and pgvector memory are intentionally deferred out of Phase 10 implementation. Do not add these dependencies without a separate approved spec and migration plan.

**Goal:** Close the Phase 10 report-quality queue without mixing heavy persistence infrastructure into the grounded evidence loop.

**Decision:** Defer PostgreSQL checkpoint resume and pgvector long-term memory to a later infrastructure phase.

**Why:** Phase 10 now has the missing report-quality primitives: live multi-source collection, SEC/PDF/rendered fetch options, section-aware queries, replan follow-ups, evidence attribution, budgets, ranking, deterministic report sections, and simple SEC financial evidence. Adding PostgreSQL/pgvector in the same phase would expand operational surface area without directly improving the current report-quality acceptance tests.

## Future Preconditions

Implement PostgreSQL checkpoint resume only after:

- Job worker lifecycle has a stable lease model for interrupted runs.
- GraphState serialization compatibility is versioned.
- Resume semantics are explicit for failed tool calls, partial evidence pools, and one-retry critic loops.
- Migration tests cover JSON/SQLite to PostgreSQL import or coexistence.

Implement pgvector memory only after:

- Evidence snippets include stable section/entity/source metadata.
- Embedding provider selection is opt-in and cost-bounded.
- Retrieval tests prove memory improves report quality without leaking unsupported claims.
- Memory storage has deletion and privacy controls.

## Acceptance For Phase 10

- No PostgreSQL or pgvector dependency is added in Phase 10.
- Existing JSON/SQLite job metadata behavior remains unchanged.
- The roadmap records persistence/memory as deferred infrastructure work, not an incomplete report-quality blocker.
