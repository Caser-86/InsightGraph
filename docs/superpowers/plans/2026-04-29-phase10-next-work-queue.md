# Phase 10 Next Work Queue

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans before implementing any item from this queue. Use TDD for behavior changes and keep live/network/LLM paths opt-in.

**Goal:** Continue InsightGraph's report-quality route without drifting into heavy infrastructure before the grounded evidence loop is stronger.

**Execution Order:**
1. Done: replan-driven follow-up collection.
2. Done: section evidence attribution.
3. Done: collection budgets and caps.
4. Done: section-aware query generation.
5. Done: report template tightening.
6. Done: long-document retrieval v2.
7. Done: opt-in rendered-page fetch.
8. Next: financial analysis tools beyond recent filing discovery.
9. PostgreSQL checkpoint resume and pgvector memory.

**Rules:**
- Preserve deterministic/offline defaults.
- Keep live providers and LLM providers explicit opt-in.
- Prefer smallest useful behavior changes over new dependencies.
- Do not add Playwright, PostgreSQL, pgvector, or embeddings until items 1-5 are stable.
- Every item needs RED/GREEN tests and verification before merge.
