# Fetch Response Size Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound live fetched response bodies before HTML/PDF evidence extraction.

**Architecture:** Keep `fetch_text()` as the single HTTP fetch helper and add a default byte limit. Callers keep the same API unless they explicitly pass `max_bytes`; oversized responses raise `FetchError` before decoding, PDF parsing, or evidence chunking.

**Tech Stack:** Python 3.11+, urllib, pytest, ruff.

---

### Task 1: Add Response Body Limit

**Files:**
- Modify: `src/insight_graph/tools/http_client.py`
- Test: `tests/test_http_client.py`

- [ ] **Step 1: Write failing test**

Add a test that fakes a 6-byte response and calls `fetch_text("https://example.com/large", max_bytes=5)`, expecting `FetchError("Response body too large: 6 bytes")`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_http_client.py::test_fetch_text_rejects_response_over_max_bytes -v
```

Expected: FAIL because `fetch_text()` does not accept `max_bytes`.

- [ ] **Step 3: Implement minimal guard**

Add `DEFAULT_MAX_RESPONSE_BYTES = 2_000_000`, accept `max_bytes` in `fetch_text()`, and raise `FetchError` when `len(body) > max_bytes` after empty-body validation and before decoding.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_http_client.py::test_fetch_text_rejects_response_over_max_bytes -v
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

- Spec coverage: bounds live network fetches before expensive evidence extraction.
- Placeholder scan: no placeholders remain.
- Type consistency: `max_bytes` defaults through the HTTP helper only and does not change callers.
