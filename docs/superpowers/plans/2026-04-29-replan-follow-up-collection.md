# Replan Follow-Up Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Critic `replan_requests` affect the retry collection pass with targeted follow-up queries.

**Architecture:** Keep the existing LangGraph retry structure. `record_retry` already increments `iterations`; on a retry, Executor will preserve prior evidence, build a deterministic follow-up query from missing section/source metadata, and run the planned collection tools with that query.

**Tech Stack:** Python 3.11+, LangGraph state, pytest, ruff.

---

### Task 1: Use Replan Requests During Retry Collection

**Files:**
- Modify: `src/insight_graph/agents/executor.py`
- Test: `tests/test_executor.py`

- [ ] **Step 1: Write failing test**

Add a test that sets `iterations=1`, existing `global_evidence_pool`, and one `missing_section_evidence` replan request. Fake `ToolRegistry.run()` should assert the query contains the original request, section ID, missing source type, and missing evidence count.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_uses_replan_requests_for_retry_follow_up_query -v
```

Expected: FAIL because Executor still uses only `state.user_request` as the tool query and does not preserve previous evidence on retry.

- [ ] **Step 3: Implement minimal follow-up query builder**

In `executor.py`, add a helper that returns `state.user_request` unless `state.iterations > 0` and `state.replan_requests` is non-empty. For missing section evidence, append deterministic clauses for `section_id`, `missing_source_types`, and `missing_evidence`.

- [ ] **Step 4: Preserve prior evidence during retry**

When retrying with replan requests, seed `collected` with `state.global_evidence_pool` or `state.evidence_pool` before adding new tool results. Existing dedupe/order logic should keep the merged pool stable.

- [ ] **Step 5: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_executor.py::test_executor_uses_replan_requests_for_retry_follow_up_query -v
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

- Spec coverage: implements next-work queue item 1 without adding another graph loop or new provider.
- Placeholder scan: no placeholders remain.
- Type consistency: uses existing `replan_requests`, `iterations`, and evidence pool fields.
