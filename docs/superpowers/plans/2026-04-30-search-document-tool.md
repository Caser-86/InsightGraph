# search_document Tool Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a built-in offline `search_document` tool that exposes local document RAG retrieval through the tool/evidence boundary.

**Architecture:** Create a focused `src/insight_graph/tools/search_document.py` module that reuses existing `document_reader` parsing/index/ranking helpers where practical. Register the tool in `ToolRegistry`, expose it via `tools.__init__`, and add opt-in planner selection through `INSIGHT_GRAPH_USE_SEARCH_DOCUMENT`.

**Tech Stack:** Python 3.13, local filesystem, existing document parser/index, pytest, ruff.

---

## File Structure

- Create `src/insight_graph/tools/search_document.py`: query parsing, filters, ranking, evidence construction.
- Modify `src/insight_graph/tools/registry.py`: register `search_document`.
- Modify `src/insight_graph/tools/__init__.py`: export `search_document`.
- Modify `src/insight_graph/agents/planner.py`: opt-in suggested tool selection.
- Modify `tests/test_tools.py`: tool behavior and registry tests.
- Modify `tests/test_agents.py`: planner opt-in tests.
- Modify docs/changelog/roadmap for Phase 16.

## Task 1: Add search_document Tool

**Files:**
- Create: `src/insight_graph/tools/search_document.py`
- Modify: `tests/test_tools.py`

- [ ] Add RED tests for plain path query, JSON path/query, `limit`, `page`, `section`, deterministic ranking, vector mode override, invalid path/outside-root behavior, and persisted index reuse.
- [ ] Implement `SearchDocumentQuery` parser supporting `path`, `query`, `limit`, `mode`, `page`, `section`.
- [ ] Reuse current working directory containment and supported suffix behavior from `document_reader`.
- [ ] Reuse document chunks/index/ranking helpers without broadening file access.
- [ ] Return verified docs `Evidence` preserving `chunk_index`, `document_page`, and `section_heading`.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py -q`.
- [ ] Run `git diff --check`.
- [ ] Commit as `feat(tools): add search_document tool`.

## Task 2: Registry And Planner Opt-In

**Files:**
- Modify: `src/insight_graph/tools/registry.py`
- Modify: `src/insight_graph/tools/__init__.py`
- Modify: `src/insight_graph/agents/planner.py`
- Modify: `tests/test_tools.py`
- Modify: `tests/test_agents.py`

- [ ] Add RED test that `ToolRegistry().run("search_document", ...)` dispatches the new tool.
- [ ] Add RED test that `INSIGHT_GRAPH_USE_SEARCH_DOCUMENT=1` makes Planner suggest `search_document` before `document_reader` and `mock_search` for document-oriented collection.
- [ ] Register and export `search_document`.
- [ ] Add planner opt-in handling without changing defaults.
- [ ] Run `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py tests/test_agents.py::test_planner_ -q` if node ids are available; otherwise run both files.
- [ ] Run `git diff --check`.
- [ ] Commit as `feat(planner): expose search_document opt-in`.

## Task 3: Docs, Verification, Merge

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] Document `search_document`, `INSIGHT_GRAPH_USE_SEARCH_DOCUMENT`, supported JSON fields, and offline limitations.
- [ ] Mark Phase 16 implemented and move Next Phase to PDF fetch/retrieval validation script.
- [ ] Run focused docs tests: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py tests/test_agents.py tests/test_repository_hygiene.py -q`.
- [ ] Commit docs as `docs: document search_document tool`.
- [ ] Run full pytest, full ruff, and `git diff --check` in the worktree.
- [ ] Fast-forward merge into `master`.
- [ ] Re-run full pytest, full ruff, and `git diff --check` on `master`.
- [ ] Remove worktree and delete branch.

## Self-Review

- Spec coverage: tool boundary, parser, filters, registry, planner opt-in, docs, and verification are covered.
- Placeholder scan: no placeholders or deferred implementation details remain.
- Type consistency: plan uses `search_document`, `SearchDocumentQuery`, and `INSIGHT_GRAPH_USE_SEARCH_DOCUMENT` consistently.
