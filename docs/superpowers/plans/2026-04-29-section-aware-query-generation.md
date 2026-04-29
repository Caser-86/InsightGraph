# Section-Aware Query Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Send narrower deterministic collection queries to each tool based on section source requirements.

**Architecture:** Keep Planner and tool APIs unchanged. Executor will build a per-tool query from `user_request`, matching section IDs/titles/questions, resolved entity names, and retry replan hints.

**Tech Stack:** Python 3.11+, pytest, ruff.

---

### Task 1: Generate Per-Tool Section Queries

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing test**

Add a test with multi-source tools and section plans where GitHub and news tools receive different queries containing only their matching section IDs/questions.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_builds_section_aware_queries_per_tool -v
```

Expected: FAIL because every tool receives the same raw `user_request`.

- [ ] **Step 3: Implement tool-source mapping**

Map `github_search -> github`, `news_search -> news`, `sec_filings -> official_site`, `document_reader -> docs`, and `web_search -> official_site/docs/news/blog/unknown`.

- [ ] **Step 4: Build deterministic query text**

For each tool, include original request, resolved entity names, and up to two matching sections with section ID, title, and first question. Keep retry replan clauses from the existing follow-up query behavior.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_builds_section_aware_queries_per_tool -v
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

- Spec coverage: implements next-work queue item 4 without adding providers or LLM calls.
- Placeholder scan: no placeholders remain.
- Type consistency: query generation consumes existing section and entity payloads.
