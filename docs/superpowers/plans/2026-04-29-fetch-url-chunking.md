# Fetch URL Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make live fetched HTML pages emit multiple chunked evidence records with section metadata.

**Architecture:** Keep `fetch_url` as the network fetch entry point and reuse existing `content_extract` output. Add deterministic chunking in `fetch_url` so long pages produce bounded evidence chunks with `chunk_index` and HTML heading metadata; do not add Playwright, OCR, storage, or vector search in this step.

**Tech Stack:** Python 3.11+, BeautifulSoup, Pydantic Evidence model, pytest, ruff.

---

### Task 1: Chunk Long Fetched HTML Pages

**Files:**
- Modify: `src/insight_graph/tools/fetch_url.py`
- Test: `tests/test_fetch_url.py`

- [ ] **Step 1: Write failing tests**

Add assertions that `fetch_url()` returns `chunk_index=1` for short pages and multiple evidence records for long pages:

```python
assert item.chunk_index == 1
assert len(evidence) > 1
assert evidence[1].id == "example-com-report-chunk-2"
assert any(item.section_heading == "Pricing" for item in evidence)
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_fetch_url.py::test_fetch_url_chunks_long_html_with_section_metadata -v
```

Expected: FAIL because `fetch_url` emits one evidence item without chunk metadata.

- [ ] **Step 3: Implement chunking**

In `src/insight_graph/tools/fetch_url.py`, add:

```python
MAX_FETCHED_EVIDENCE = 5
MAX_SNIPPET_CHARS = 500
SNIPPET_OVERLAP_CHARS = 100
```

Generate bounded chunks from `content.text`, derive IDs as `base-id`, `base-id-chunk-2`, and fill `chunk_index` plus the nearest preceding HTML heading.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_fetch_url.py -v
```

Expected: PASS.

- [ ] **Step 5: Full verification**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: extends live fetch evidence chain with long-page chunk metadata.
- Placeholder scan: no placeholders remain.
- Type consistency: uses existing optional `Evidence` metadata fields from Document RAG baseline.
