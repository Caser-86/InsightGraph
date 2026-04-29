# Full LLM Trace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in full LLM call logging compatible with the reference `llm_logger` behavior.

**Architecture:** Add a focused JSONL trace writer under `insight_graph.llm`, reuse `build_full_trace_event()`, and wire Reporter/Analyst LLM paths to write full payload events only when explicitly enabled.

**Tech Stack:** Python 3.11+, pytest, ruff, JSONL files.

---

### Task 1: Trace Writer Helper

**Files:**
- Create: `src/insight_graph/llm/trace_writer.py`
- Modify: `tests/test_extensibility.py`

- [ ] **Step 1: Write failing tests**

Add tests for env gating, default path, explicit path, directory creation, and JSONL append.

- [ ] **Step 2: Run RED**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_extensibility.py -v`

Expected: import errors for `trace_writer`.

- [ ] **Step 3: Implement helper**

Create `trace_writer.py` with `is_llm_trace_enabled()`, `resolve_llm_trace_path()`, and `write_llm_trace_event()`.

- [ ] **Step 4: Run GREEN**

Run: `$env:PYTHONPATH='src'; & "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_extensibility.py -q`

Expected: tests pass.

### Task 2: Reporter Full Trace Integration

**Files:**
- Modify: `src/insight_graph/agents/reporter.py`
- Modify: `tests/test_agents.py`

- [ ] **Step 1: Write failing tests**

Add tests that enable `INSIGHT_GRAPH_LLM_TRACE_PATH`, run fake LLM Reporter success and failure paths, then assert JSONL contains messages/output/token usage or error metadata.

- [ ] **Step 2: Run RED**

Run targeted Reporter trace tests.

Expected: trace file missing.

- [ ] **Step 3: Implement Reporter trace writes**

Use `build_full_trace_event(include_payload=True)` and `write_llm_trace_event()` in Reporter success and failure paths.

- [ ] **Step 4: Run GREEN**

Run targeted Reporter trace tests.

Expected: tests pass.

### Task 3: Analyst Full Trace Integration And Docs

**Files:**
- Modify: `src/insight_graph/agents/analyst.py`
- Modify: `tests/test_agents.py`
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] **Step 1: Add Analyst trace test**

Enable `INSIGHT_GRAPH_LLM_TRACE_PATH`, run fake LLM Analyst success path, assert JSONL event stage is `analyst` and contains payload/token metadata.

- [ ] **Step 2: Implement Analyst trace writes**

Use same helper and event builder as Reporter.

- [ ] **Step 3: Update docs**

Document `INSIGHT_GRAPH_LLM_TRACE=1`, `INSIGHT_GRAPH_LLM_TRACE_PATH`, and full payload behavior. Mark roadmap phase implemented.

- [ ] **Step 4: Full verification and commit**

Run full pytest, ruff, and `git diff --check`; commit as `feat(llm): add full trace writer`, merge to master, rerun verification, cleanup worktree.
