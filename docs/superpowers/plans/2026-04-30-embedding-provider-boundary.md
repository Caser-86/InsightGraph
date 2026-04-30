# Embedding Provider Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in external/local embedding providers while keeping deterministic embeddings as the default.

**Architecture:** Extend `src/insight_graph/memory/embeddings.py` with provider config resolution, injectable HTTP transports, validated response parsing, and a single `embed_text()` entry point. Wire memory record construction to `embed_text()`; leave document index embeddings deterministic in this phase.

**Tech Stack:** Python 3.13, stdlib HTTP/JSON, pytest fake transports, ruff.

---

## File Structure

- Modify `src/insight_graph/memory/embeddings.py`: provider config, `embed_text()`, HTTP request helpers, response validation, safe errors.
- Modify `tests/test_memory_embeddings.py`: config, deterministic, OpenAI-compatible, local HTTP, validation, and build-memory-record tests.
- Modify `docs/configuration.md`, `docs/reference-parity-roadmap.md`, and `CHANGELOG.md`: document provider boundary and mark roadmap progress.

## Task 1: Embedding Provider Boundary

**Files:**
- Modify: `src/insight_graph/memory/embeddings.py`
- Modify: `tests/test_memory_embeddings.py`

- [ ] Add RED tests for `resolve_embedding_config()` default deterministic config and explicit provider/env overrides.
- [ ] Add RED tests for `embed_text()` using deterministic provider.
- [ ] Add RED tests for `openai_compatible` request body and OpenAI response parsing via fake transport.
- [ ] Add RED tests for `local_http` request body and both local/OpenAI response shapes via fake transport.
- [ ] Add RED tests for invalid provider and invalid embedding responses raising `EmbeddingProviderError` or `ValueError` as appropriate.
- [ ] Implement `EmbeddingConfig`, `EmbeddingProviderError`, `resolve_embedding_config()`, `embed_text()`, and validation helpers.
- [ ] Keep `get_embedding_provider()` backward compatible: unknown env still returns `deterministic`.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_memory_embeddings.py -q`.
- [ ] Run `git diff --check`.
- [ ] Commit as `feat(memory): add embedding provider boundary`.

## Task 2: Memory Record Integration

**Files:**
- Modify: `src/insight_graph/memory/embeddings.py`
- Modify: `tests/test_memory_embeddings.py`

- [ ] Add RED test proving `build_memory_record()` uses `embed_text()` and records selected provider metadata.
- [ ] Add RED test proving deterministic default metadata remains unchanged.
- [ ] Implement minimal integration by replacing direct `deterministic_text_embedding()` call in `build_memory_record()` with `embed_text()`.
- [ ] Do not wire document index to external embeddings in this phase.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_memory_embeddings.py tests/test_document_index.py -q`.
- [ ] Run `git diff --check`.
- [ ] Commit as `feat(memory): use configured embeddings for memory records`.

## Task 3: Docs, Verification, Merge

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] Document `INSIGHT_GRAPH_EMBEDDING_PROVIDER`, `INSIGHT_GRAPH_EMBEDDING_BASE_URL`, `INSIGHT_GRAPH_EMBEDDING_API_KEY`, `INSIGHT_GRAPH_EMBEDDING_MODEL`, and `INSIGHT_GRAPH_EMBEDDING_DIMENSIONS`.
- [ ] State default deterministic/offline behavior and opt-in external provider behavior.
- [ ] Mark Phase 15 external embedding provider boundary implemented and move Next Phase to `search_document` tool.
- [ ] Run focused docs-adjacent tests: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_memory_embeddings.py tests/test_repository_hygiene.py -q`.
- [ ] Commit docs as `docs: document embedding provider boundary`.
- [ ] Run full pytest, full ruff, and `git diff --check` in the worktree.
- [ ] Fast-forward merge into `master`.
- [ ] Re-run full pytest, full ruff, and `git diff --check` on `master`.
- [ ] Remove worktree and delete branch.

## Self-Review

- Spec coverage: deterministic default, opt-in `openai_compatible` and `local_http`, config resolution, fake transports, response validation, memory integration, docs, and roadmap are covered.
- Placeholder scan: no placeholders or deferred implementation details remain.
- Type consistency: plan uses `EmbeddingConfig`, `EmbeddingProviderError`, `resolve_embedding_config()`, and `embed_text()` consistently.
