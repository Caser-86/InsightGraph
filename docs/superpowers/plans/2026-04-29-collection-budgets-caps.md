# Collection Budgets And Caps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound evidence retained by Executor per tool, per run, and per section.

**Architecture:** Keep provider/tool APIs unchanged. Add deterministic caps inside Executor after relevance filtering, deduplication, section attribution, and score ordering so downstream Analyst/Reporter receive a bounded evidence pool.

**Tech Stack:** Python 3.11+, pytest, ruff.

---

### Task 1: Add Executor Evidence Caps

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing tests**

Add tests proving a tool returning more than 5 evidence records is capped, a section with budget 1 keeps only one attributed evidence record, and the run cap keeps the total evidence pool bounded.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_caps_evidence_per_tool tests/test_executor.py::test_executor_caps_evidence_per_section_budget tests/test_executor.py::test_executor_caps_total_evidence_per_run -v
```

Expected: FAIL because Executor currently keeps all deduped evidence.

- [ ] **Step 3: Implement per-tool cap**

Add `MAX_EVIDENCE_PER_TOOL = 5` and cap kept tool results after relevance filtering. Increase `filtered_count` by records removed by the cap.

- [ ] **Step 4: Implement per-section and per-run caps**

After section attribution and score ordering, keep at most each section's positive integer `budget` and then at most `MAX_EVIDENCE_PER_RUN = 20` total records.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_caps_evidence_per_tool tests/test_executor.py::test_executor_caps_evidence_per_section_budget tests/test_executor.py::test_executor_caps_total_evidence_per_run -v
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

- Spec coverage: implements next-work queue item 3 without adding providers or config surface.
- Placeholder scan: no placeholders remain.
- Type consistency: caps are Executor constants and section budget uses existing plan payload field.
