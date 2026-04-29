# run_with_llm_log Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `scripts/run_with_llm_log.py` produce reference-style full LLM trace files and token/call summaries.

**Architecture:** Reuse the existing script and full trace writer. The script derives a `.jsonl` trace path next to its metadata `.json`, enables tracing before workflow execution, summarizes JSONL after completion, and supports `--safe-log-only` for legacy safe metadata behavior.

**Tech Stack:** Python 3.11+, argparse, JSON/JSONL, pytest.

---

### Task 1: Trace Summary Helpers

**Files:**
- Modify: `scripts/run_with_llm_log.py`
- Modify: `tests/test_run_with_llm_log_script.py`

- [ ] **Step 1: Write failing helper tests**

Add tests for deriving `.jsonl` trace path and summarizing JSONL call/token totals by stage/model.

- [ ] **Step 2: Run RED**

Run targeted `tests/test_run_with_llm_log_script.py` helper tests.

- [ ] **Step 3: Implement helpers**

Add `build_trace_path(log_path)` and `summarize_trace_file(trace_path)`.

- [ ] **Step 4: Run GREEN**

Run targeted helper tests.

### Task 2: Full Trace Default Runner Behavior

**Files:**
- Modify: `scripts/run_with_llm_log.py`
- Modify: `tests/test_run_with_llm_log_script.py`

- [ ] **Step 1: Write failing integration test**

Update script integration tests so default run sets `INSIGHT_GRAPH_LLM_TRACE_PATH`, fake workflow writes a trace JSONL to that path, metadata JSON includes `llm_trace_path` and `llm_trace_summary`, and stdout includes call/token summary lines.

- [ ] **Step 2: Run RED**

Run targeted integration test; expect missing trace fields/output.

- [ ] **Step 3: Implement full trace default**

Before workflow execution, compute log path and trace path, set `INSIGHT_GRAPH_LLM_TRACE_PATH`, run workflow, summarize trace file, write metadata JSON, and print summary.

- [ ] **Step 4: Run GREEN**

Run targeted integration test.

### Task 3: Safe-Log-Only Compatibility And Docs

**Files:**
- Modify: `scripts/run_with_llm_log.py`
- Modify: `tests/test_run_with_llm_log_script.py`
- Modify: `CHANGELOG.md`
- Modify: `docs/configuration.md`
- Modify: `docs/reference-parity-roadmap.md`

- [ ] **Step 1: Add `--safe-log-only` test**

Assert safe mode does not set `INSIGHT_GRAPH_LLM_TRACE_PATH`, does not include trace summary, and preserves old safe metadata behavior.

- [ ] **Step 2: Implement `--safe-log-only` and docs**

Add argparse flag and documentation. Mark roadmap phase implemented.

- [ ] **Step 3: Full verification and commit**

Run full pytest, ruff, and `git diff --check`; commit as `feat(scripts): summarize llm trace logs`, merge to master, rerun verification, cleanup worktree.
