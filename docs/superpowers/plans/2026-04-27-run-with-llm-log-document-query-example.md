# run_with_llm_log Document Query Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document and test `scripts/run_with_llm_log.py` pass-through support for `document_reader` JSON query strings.

**Architecture:** Keep wrapper behavior unchanged. Use the existing injectable `run_research_func` and temp log directory to prove the JSON query is passed through and logged as safe metadata.

**Tech Stack:** Python, pytest, Ruff, Markdown.

---

## File Map

- Modify `tests/test_run_with_llm_log_script.py`: add JSON query pass-through/log metadata test.
- Modify `README.md`: add `run_with_llm_log.py` document-reader JSON query example.

---

### Task 1: Add Test And Docs In One Batch

**Files:**
- Modify: `tests/test_run_with_llm_log_script.py`
- Modify: `README.md`

- [ ] **Step 1: Add pass-through/log test**

Add a test near the existing `test_main_runs_query_writes_markdown_and_log_file()` that calls `llm_log_script.main()` with `'{"path":"report.md","query":"enterprise pricing"}'`, fake `run_research_func`, temp `--log-dir`, and `fixed_now`. Assert exit code `0`, observed query equals the JSON string, stdout mentions `LLM log written to:`, and the JSON log payload `query` equals the same string.

- [ ] **Step 2: Update README**

In the `当前 run with LLM log 用法` block, add:

```bash
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python scripts/run_with_llm_log.py '{"path":"report.md","query":"enterprise pricing"}' --log-dir tmp_llm_logs
```

Below the existing explanation, add a sentence that this supports the same deterministic lexical `document_reader` ranking as `run_research.py` while writing safe metadata logs.

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m pytest tests/test_run_with_llm_log_script.py -q
python -m pytest -q
python -m ruff check .
```

Commit:

```bash
git add tests/test_run_with_llm_log_script.py README.md
git commit -m "docs: document llm log document queries"
```

---

## Self-Review

- Spec coverage: Covers pass-through behavior, safe log metadata, README example, focused/full tests, and Ruff.
- Placeholder scan: No unresolved placeholder sections remain.
- Type consistency: Uses existing `main()`, `make_state()`, and `fixed_now()` test helpers.
