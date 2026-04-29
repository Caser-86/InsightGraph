# Remote PDF Fetch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `fetch_url` extract verified evidence from remote PDF responses with page metadata.

**Architecture:** Preserve the existing `fetch_text` API while retaining response bytes on `FetchedPage`. Teach `fetch_url` to detect PDF responses by content type or `.pdf` URL path, extract text with pypdf, and emit chunked `Evidence` records with `document_page`.

**Tech Stack:** Python 3.11+, urllib, pypdf, pytest, ruff.

---

### Task 1: Add PDF-Aware Fetch Evidence

**Files:**
- Modify: `src/insight_graph/tools/http_client.py`
- Modify: `src/insight_graph/tools/fetch_url.py`
- Test: `tests/test_fetch_url.py`

- [ ] **Step 1: Write failing tests**

Add a test that fakes `fetch_text()` returning `application/pdf` with PDF bytes and expects one verified docs evidence item with `document_page=1`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_fetch_url.py::test_fetch_url_reads_remote_pdf_with_page_metadata tests/test_fetch_url.py::test_infer_source_type_from_url -v
```

Expected: FAIL because PDF bytes are treated as decoded text and `.pdf` URLs infer `unknown`.

- [ ] **Step 3: Retain raw response bytes**

Add `body: bytes | None = None` to `FetchedPage` and set it in `fetch_text()`.

- [ ] **Step 4: Extract remote PDF text**

In `fetch_url.py`, detect PDF by content type or `.pdf` path, parse `FetchedPage.body` with `PdfReader(BytesIO(...))`, skip encrypted/unreadable PDFs, and build chunked evidence with page metadata.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_fetch_url.py::test_fetch_url_reads_remote_pdf_with_page_metadata tests/test_fetch_url.py::test_infer_source_type_from_url -v
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

- Spec coverage: extends live fetched evidence to PDF pages without adding OCR, browser rendering, storage, or vector search.
- Placeholder scan: no placeholders remain.
- Type consistency: `FetchedPage.body` is optional and preserves existing text callers.
