# Document RAG Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add page/chunk/section metadata to document evidence as the first long-document RAG foundation.

**Architecture:** Extend `Evidence` with optional metadata fields and populate them in `document_reader`. Keep current snippet chunking and lexical ranking behavior; do not add embeddings, pgvector, OCR, or remote PDF download in this step.

**Tech Stack:** Python 3.11+, Pydantic, pypdf, BeautifulSoup, pytest, ruff.

---

### Task 1: Add Document Evidence Metadata

**Files:**
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/tools/document_reader.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write failing metadata tests**

Add assertions that document evidence exposes:

```python
assert evidence[0].chunk_index == 1
assert evidence[0].document_page == 1
assert evidence[0].section_heading == "Pricing"
```

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py::test_document_reader_records_section_heading_for_ranked_markdown -v
```

Expected: FAIL because `Evidence` has no document RAG metadata fields.

- [ ] **Step 3: Add optional Evidence fields**

Add to `src/insight_graph/state.py`:

```python
chunk_index: int | None = None
document_page: int | None = None
section_heading: str | None = None
```

- [ ] **Step 4: Populate metadata in document_reader**

Convert chunk tuples to a small `DocumentChunk` dataclass carrying snippet, index, optional page, and optional section heading. Fill metadata when building `Evidence`.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_tools.py -v
```

Expected: PASS.

- [ ] **Step 6: Full verification**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: implements long-document RAG baseline metadata without adding deferred storage/vector systems.
- Placeholder scan: no placeholders remain.
- Type consistency: metadata fields are optional and preserve existing Evidence construction.
