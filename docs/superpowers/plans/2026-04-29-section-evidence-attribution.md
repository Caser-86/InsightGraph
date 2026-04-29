# Section Evidence Attribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Attribute collected evidence to likely report sections so section sufficiency is not based on the same global evidence count for every section.

**Architecture:** Add optional `section_id` metadata to `Evidence`. Executor assigns section IDs after deduplication and before scoring/status calculation using deterministic matches from section source requirements, section IDs/titles/questions, and evidence title/snippet/source URL.

**Tech Stack:** Python 3.11+, Pydantic state models, pytest, ruff.

---

### Task 1: Add Section Attribution Metadata

**Files:**
- Modify: `src/insight_graph/state.py`
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing tests**

Add tests proving `execute_subtasks()` assigns `section_id` on evidence and section collection status counts only evidence assigned to that section.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_assigns_evidence_to_matching_sections tests/test_executor.py::test_executor_counts_section_status_from_assigned_evidence -v
```

Expected: FAIL because `Evidence` has no `section_id` and status still uses global counts.

- [ ] **Step 3: Add `Evidence.section_id`**

Add `section_id: str | None = None` to the Pydantic `Evidence` model.

- [ ] **Step 4: Implement deterministic attribution**

In `executor.py`, assign each evidence item to the best matching section. Prefer source type matches from `required_source_types`, then lexical matches against section ID/title/questions, then fall back to the first section.

- [ ] **Step 5: Count per-section evidence**

Update `_build_section_collection_status()` so `evidence_count`, coverage, and missing evidence are computed from evidence with matching `section_id`.

- [ ] **Step 6: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_assigns_evidence_to_matching_sections tests/test_executor.py::test_executor_counts_section_status_from_assigned_evidence -v
```

Expected: PASS.

- [ ] **Step 7: Full verification**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: tests pass, ruff passes, diff check has no whitespace errors.

---

## Self-Review

- Spec coverage: implements next-work queue item 2 without changing providers or adding storage.
- Placeholder scan: no placeholders remain.
- Type consistency: `section_id` is optional and preserves existing evidence payload compatibility.
