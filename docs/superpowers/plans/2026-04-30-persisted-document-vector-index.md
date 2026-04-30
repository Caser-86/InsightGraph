# Persisted Document Vector Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in local JSON document vector index for reusable offline document chunks and deterministic embeddings.

**Architecture:** Extend `document_index.py` with JSON-backed index storage and keep `document_reader.py` as the only integration point. The index is used only when `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH` is set; otherwise the current in-memory path is unchanged.

**Tech Stack:** Python 3.13, dataclasses, JSON files, deterministic embeddings, pytest, ruff.

---

## File Structure

- Modify `src/insight_graph/report_quality/document_index.py`: add JSON index data types, load/save, freshness checks, and persisted chunk ranking helpers.
- Modify `src/insight_graph/tools/document_reader.py`: opt into persisted index when env path is configured and fall back on errors.
- Modify `tests/test_document_index.py`: unit tests for index save/load, stale rebuild, corrupted JSON fallback, and persisted vector ranking.
- Modify `tests/test_tools.py`: integration tests for `document_reader` using the persisted index.
- Modify `docs/configuration.md`, `docs/reference-parity-roadmap.md`, and `CHANGELOG.md`: document the opt-in index and mark roadmap progress.

## Task 1: JSON Document Vector Index

**Files:**
- Modify: `src/insight_graph/report_quality/document_index.py`
- Modify: `tests/test_document_index.py`

- [ ] Add RED tests for `DocumentVectorIndex` save/load, fresh entry reuse, stale metadata rebuild, and corrupted JSON fallback.
- [ ] Implement `IndexedDocumentChunk`, `DocumentVectorIndex`, `get_document_index_path()`, and `build_index_chunks()`.
- [ ] Use existing `deterministic_text_embedding()` for chunk embeddings.
- [ ] Ensure invalid/corrupt JSON returns an empty index and does not raise during `load()`.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_document_index.py -q`.
- [ ] Run `git diff --check`.
- [ ] Commit as `feat(documents): add persisted vector index`.

## Task 2: document_reader Integration

**Files:**
- Modify: `src/insight_graph/tools/document_reader.py`
- Modify: `tests/test_tools.py`

- [ ] Add RED tests proving `document_reader` writes an index file when `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH` is set.
- [ ] Add RED tests proving a second query reuses the persisted chunks and stale file content rebuilds the entry.
- [ ] Add RED test proving corrupt index JSON falls back to normal document reading.
- [ ] Integrate the index after document text extraction and before ranking.
- [ ] Preserve existing behavior when env var is unset.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_document_reader_ -q` if node ids are available; otherwise run `tests/test_tools.py -q`.
- [ ] Run `git diff --check`.
- [ ] Commit as `feat(tools): use persisted document index`.

## Task 3: Docs, Roadmap, Verification, Merge

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] Document `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH` and clarify it is local/offline JSON storage.
- [ ] Mark persisted document vector index implemented in the roadmap.
- [ ] Move next phase to external embedding provider boundary or `search_document` depending on remaining roadmap order.
- [ ] Run focused docs-adjacent tests: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_document_index.py tests/test_tools.py tests/test_repository_hygiene.py -q`.
- [ ] Commit docs as `docs: document persisted document index`.
- [ ] Run full pytest, full ruff, and `git diff --check` in the worktree.
- [ ] Fast-forward merge the branch into `master`.
- [ ] Re-run full pytest, full ruff, and `git diff --check` on `master`.
- [ ] Remove the worktree and delete the branch.

## Self-Review

- Spec coverage: opt-in local JSON index, no cloud/DB dependency, stale rebuild, corrupt fallback, vector retrieval compatibility, docs, and roadmap are covered.
- Placeholder scan: no placeholders or deferred implementation details remain.
- Type consistency: plan uses `DocumentVectorIndex`, `IndexedDocumentChunk`, and `INSIGHT_GRAPH_DOCUMENT_INDEX_PATH` consistently.
