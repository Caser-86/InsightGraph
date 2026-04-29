# Long Document Retrieval V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rank local and remote long-document chunks by query relevance before truncating to the evidence cap.

**Architecture:** Keep deterministic chunking and evidence schemas. Add query-aware chunk ordering to `document_reader` using heading boosts, and add JSON query support to `fetch_url` so remote HTML/PDF chunks can be ranked by caller intent.

**Tech Stack:** Python 3.11+, pytest, ruff.

---

### Task 1: Rank Long Document Chunks By Query And Metadata

**Files:**
- Modify: `src/insight_graph/tools/document_reader.py`
- Modify: `src/insight_graph/tools/fetch_url.py`
- Test: `tests/test_tools.py`
- Test: `tests/test_fetch_url.py`

- [ ] **Step 1: Write failing tests**

Add one local document test proving a section heading match can rank a later chunk first, and one remote HTML test proving `fetch_url` accepts `{"url": "...", "query": "pricing"}` and returns the matching section first.

- [ ] **Step 2: Verify RED**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_document_reader_ranks_heading_matches tests/test_fetch_url.py::test_fetch_url_ranks_chunks_from_json_query -v
```

Expected: FAIL because document heading matches are not boosted and `fetch_url` treats JSON as a URL.

- [ ] **Step 3: Implement heading-aware local ranking**

Update `_rank_snippets()` to score query tokens in `section_heading` above body token matches while preserving stable chunk order for ties.

- [ ] **Step 4: Implement remote fetch query parsing and ranking**

Parse JSON `{"url": str, "query": str}` in `fetch_url()`. Rank HTML/PDF chunks by query tokens before applying `MAX_FETCHED_EVIDENCE`; for HTML include section heading matches in the score.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_document_reader_ranks_heading_matches tests/test_fetch_url.py::test_fetch_url_ranks_chunks_from_json_query -v
```

Expected: PASS.

- [ ] **Step 6: Full verification**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: implements next-work queue item 6 without embeddings or pgvector.
- Placeholder scan: no placeholders remain.
- Type consistency: fetch JSON query mirrors existing document reader JSON query shape.
