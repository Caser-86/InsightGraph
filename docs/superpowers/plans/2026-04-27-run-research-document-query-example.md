# run_research Document Query Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document and test `scripts/run_research.py` pass-through support for `document_reader` JSON query strings.

**Architecture:** Keep wrapper behavior unchanged. Add one focused test around existing `main()` injection seam, then update README usage examples.

**Tech Stack:** Python, pytest, Ruff, Markdown.

---

## File Map

- Modify `tests/test_run_research_script.py`: add JSON query pass-through test.
- Modify `README.md`: add document-reader JSON query examples and clarify deterministic lexical ranking.

---

### Task 1: Add Test And Docs In One Batch

**Files:**
- Modify: `tests/test_run_research_script.py`
- Modify: `README.md`

- [ ] **Step 1: Add pass-through test**

Add this test after `test_main_runs_query_and_writes_markdown()`:

```python
def test_main_passes_document_reader_json_query_unchanged():
    observed_queries: list[str] = []
    query = '{"path":"report.md","query":"enterprise pricing"}'

    def fake_run_research(value: str) -> GraphState:
        observed_queries.append(value)
        return make_state(value)

    exit_code = run_research_script.main(
        [query],
        stdin=io.StringIO(),
        stdout=io.StringIO(),
        stderr=io.StringIO(),
        run_research_func=fake_run_research,
    )

    assert exit_code == 0
    assert observed_queries == [query]
```

Run:

```bash
python -m pytest tests/test_run_research_script.py::test_main_passes_document_reader_json_query_unchanged -q
```

Expected: test passes because the wrapper already preserves non-empty query strings.

- [ ] **Step 2: Update README**

In the `当前 run research 用法` block, add:

```bash
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python scripts/run_research.py '{"path":"report.md","query":"enterprise pricing"}'
```

After the existing run research explanation, add:

```markdown
当 `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` 时，query 可以是本地文件路径，也可以是 JSON：`{"path":"report.md","query":"enterprise pricing"}`。JSON `query` 会触发 `document_reader` 的 deterministic lexical ranking，从本地文档 chunks 中优先返回词项匹配的 evidence；不使用 embeddings、LLM 或公网服务。
```

- [ ] **Step 3: Verify and commit**

Run:

```bash
python -m pytest tests/test_run_research_script.py -q
python -m pytest -q
python -m ruff check .
```

Expected: all tests pass and Ruff reports `All checks passed!`.

Commit:

```bash
git add tests/test_run_research_script.py README.md
git commit -m "docs: document run research document queries"
```

---

## Self-Review

- Spec coverage: Covers wrapper pass-through test, README examples, deterministic lexical ranking wording, and verification.
- Placeholder scan: No unresolved placeholder sections remain.
- Type consistency: Uses existing `main()` and `GraphState` test helper.
