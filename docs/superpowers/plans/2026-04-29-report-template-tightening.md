# Report Template Tightening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render deterministic reports using planned domain sections when `section_research_plan` is present.

**Architecture:** Add a Reporter helper that builds the main findings body from planned section metadata. Keep the current `Key Findings` helper path for states without a section plan.

**Tech Stack:** Python 3.11+, pytest, ruff.

---

### Task 1: Render Planned Report Sections

**Files:**
- Modify: `src/insight_graph/agents/reporter.py`
- Test: `tests/test_agents.py`

- [ ] **Step 1: Write failing test**

Add a test where evidence has `section_id`, findings cite that evidence, and `section_research_plan` contains `Executive Summary`, `Pricing and Packaging`, and `References`. Expected output contains the planned headings, places pricing finding under `Pricing and Packaging`, and omits `Key Findings`.

- [ ] **Step 2: Verify RED**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_reporter_uses_section_research_plan_for_deterministic_body -v
```

Expected: FAIL because Reporter still emits `## Key Findings` only.

- [ ] **Step 3: Implement planned-section body builder**

Add helpers that map verified evidence ID to `section_id`, assign each citable finding to the first matching section, and render planned section titles except `References`.

- [ ] **Step 4: Verify GREEN**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::test_reporter_uses_section_research_plan_for_deterministic_body -v
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

- Spec coverage: implements next-work queue item 5 for deterministic reports.
- Placeholder scan: no placeholders remain.
- Type consistency: uses existing `section_research_plan`, `Evidence.section_id`, and finding evidence IDs.
