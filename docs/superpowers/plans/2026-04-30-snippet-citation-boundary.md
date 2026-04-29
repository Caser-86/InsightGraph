# Snippet Citation Boundary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tie citation support to verified evidence snippets and strengthen Reporter anti-hallucination prompts.

**Architecture:** Extend existing deterministic `citation_support.py` records with snippet metadata and support scoring. Update Reporter prompt wording to present evidence snippets as the only factual basis. Keep all behavior offline/deterministic unless existing LLM Reporter opt-in is used.

**Tech Stack:** Python 3.11+, Pydantic state models, pytest, ruff.

---

### Task 1: Citation Support Snippet Metadata

**Files:**
- Modify: `tests/test_citation_support.py`
- Modify: `src/insight_graph/report_quality/citation_support.py`

- [ ] **Step 1: Write failing tests**

Add tests that expect supported records to include `supporting_snippets`, `matched_terms`, `missing_terms`, and `support_score`; add a weak-support test where verified evidence exists but claim terms are missing.

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_citation_support.py -v`

Expected: metadata assertions fail.

- [ ] **Step 3: Implement minimal metadata**

Update `citation_support.py` to compute meaningful claim terms, snippet terms, matched/missing terms, score, and supporting snippets from verified cited evidence.

- [ ] **Step 4: Run GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_citation_support.py -q`

Expected: citation support tests pass.

### Task 2: Reporter Anti-Hallucination Prompt Boundary

**Files:**
- Modify: `tests/test_agents.py`
- Modify: `src/insight_graph/agents/reporter.py`

- [ ] **Step 1: Write failing prompt test**

Add a test for LLM Reporter that captures the user prompt and asserts it contains `Evidence snippets are the only allowed factual basis` and the verified evidence snippet text.

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::<new_test_name> -v`

Expected: prompt wording assertion fails.

- [ ] **Step 3: Implement prompt tightening**

Update `_build_reporter_messages()` to label evidence as `Verified evidence snippets` and add explicit anti-hallucination instructions: use only listed snippets, do not invent facts/numbers, and use only allowed citations.

- [ ] **Step 4: Run GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_agents.py::<new_test_name> -q`

Expected: test passes.

### Task 3: Reporter Citation Support Rendering And Docs

**Files:**
- Modify: `tests/test_agents.py`
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] **Step 1: Write or update rendering test**

Update the existing Citation Support table test so support metadata with `support_score` and `matched_terms` renders useful support detail without exposing unverified evidence.

- [ ] **Step 2: Implement rendering and docs**

Keep the existing table shape if possible; include support score/matched terms in the reason cell. Update changelog/configuration/roadmap to mark snippet-level citation support implemented.

- [ ] **Step 3: Full verification**

Run:

```powershell
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
git diff --check
```

Expected: pytest passes, ruff passes, whitespace check has no errors.

- [ ] **Step 4: Commit, merge, cleanup**

Commit as `feat(citations): add snippet support boundary`, fast-forward merge to `master`, rerun full verification on master, and remove the worktree/branch.
