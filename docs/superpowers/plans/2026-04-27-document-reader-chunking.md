# document_reader Chunking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Return bounded multiple evidence snippets for long local documents read by `document_reader`.

**Architecture:** Keep GraphState, Executor, and Evidence schemas unchanged. Implement chunking inside `document_reader` after extraction and normalization, preserving the original first evidence ID for compatibility and appending `-chunk-N` only to later chunks.

**Tech Stack:** Python, pytest, Ruff.

---

## File Map

- Modify `src/insight_graph/tools/document_reader.py`: add chunking constants and helper functions.
- Modify `tests/test_tools.py`: add long-document chunking tests.
- Modify `scripts/validate_document_reader.py`: add a long text fixture and validation case.
- Modify `tests/test_validate_document_reader.py`: update fixed case list and summary counts.
- Modify `README.md`: document bounded multi-snippet behavior.

---

### Task 1: Implement Chunking In One Batch

**Files:**
- Modify: `src/insight_graph/tools/document_reader.py`
- Modify: `tests/test_tools.py`
- Modify: `scripts/validate_document_reader.py`
- Modify: `tests/test_validate_document_reader.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing chunking tests**

Add this test in `tests/test_tools.py` after `test_document_reader_limits_snippet_length`:

```python
def test_document_reader_chunks_long_documents(tmp_path, monkeypatch) -> None:
    document = tmp_path / "long.md"
    text = "".join(str(index % 10) for index in range(2200))
    document.write_text(text, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("long.md", "s1")

    assert len(evidence) == 5
    assert [len(item.snippet) for item in evidence] == [500, 500, 500, 500, 500]
    assert evidence[0].id == document_id_for("long.md")
    assert evidence[1].id == f"{document_id_for('long.md')}-chunk-2"
    assert evidence[4].id == f"{document_id_for('long.md')}-chunk-5"
    assert evidence[0].title == "long.md"
    assert evidence[1].title == "long.md (chunk 2)"
    assert evidence[4].title == "long.md (chunk 5)"
    assert evidence[0].snippet[-100:] == evidence[1].snippet[:100]
    assert {item.source_url for item in evidence} == {document.resolve().as_uri()}
    assert {item.source_type for item in evidence} == {"docs"}
    assert {item.verified for item in evidence} == {True}
```

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_limits_snippet_length tests/test_tools.py::test_document_reader_chunks_long_documents -q
```

Expected: the new test fails because `document_reader` still returns one evidence item.

- [ ] **Step 2: Implement chunking**

In `src/insight_graph/tools/document_reader.py`, add constants:

```python
SNIPPET_OVERLAP_CHARS = 100
MAX_DOCUMENT_EVIDENCE = 5
```

Replace the current single-evidence return path with:

```python
    snippets = _chunk_snippets(_normalize_snippet(_extract_text(text, path.suffix.lower())))
    if not snippets:
        return []

    return [_build_evidence(root, path, subtask_id, snippet, index) for index, snippet in enumerate(snippets)]
```

Add helpers:

```python
def _chunk_snippets(text: str) -> list[str]:
    if not text:
        return []
    step = MAX_SNIPPET_CHARS - SNIPPET_OVERLAP_CHARS
    return [
        text[start : start + MAX_SNIPPET_CHARS]
        for start in range(0, len(text), step)
        if text[start : start + MAX_SNIPPET_CHARS]
    ][:MAX_DOCUMENT_EVIDENCE]


def _build_evidence(
    root: Path,
    path: Path,
    subtask_id: str,
    snippet: str,
    index: int,
) -> Evidence:
    base_id = _evidence_id(root, path)
    chunk_number = index + 1
    return Evidence(
        id=base_id if index == 0 else f"{base_id}-chunk-{chunk_number}",
        subtask_id=subtask_id,
        title=path.name if index == 0 else f"{path.name} (chunk {chunk_number})",
        source_url=path.as_uri(),
        snippet=snippet,
        source_type="docs",
        verified=True,
    )
```

Keep extraction and path safety behavior unchanged.

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_returns_verified_docs_evidence tests/test_tools.py::test_document_reader_limits_snippet_length tests/test_tools.py::test_document_reader_chunks_long_documents -q
python -m ruff check src/insight_graph/tools/document_reader.py tests/test_tools.py
```

Expected: tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 3: Update validator and README**

In `scripts/validate_document_reader.py`, add this fixture:

```python
(workspace / "long.txt").write_text("".join(str(index % 10) for index in range(2200)), encoding="utf-8")
```

Add this validation case after `txt_file_success`:

```python
ValidationCase("long_file_chunking_success", "long.txt", 5, "long.txt", "0123456789"),
```

In `tests/test_validate_document_reader.py`:

- Insert `"long_file_chunking_success"` after `"txt_file_success"`.
- Add assertions that the case title is `long.txt` and `snippet_contains` is true.
- Update summary counts from 12/6 to 13/11.
- Update failing-reader case counts from 12 to 13.
- Update Markdown summary assertion to `| 13 | 13 | 0 | true | 11 |`.
- Update JSON main case count assertion to 13.

In README, update document reader wording to say long local documents return up to 5 bounded snippets; PDF OCR, page-level pagination, and semantic retrieval remain future work.

Run:

```bash
python -m pytest tests/test_validate_document_reader.py tests/test_tools.py::test_document_reader_chunks_long_documents -q
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
python -m ruff check scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
```

Expected: tests pass, validator includes `long_file_chunking_success`, and Ruff reports `All checks passed!`.

- [ ] **Step 4: Final verification, review, and commit**

Run:

```bash
python -m pytest -q
python -m ruff check .
```

Expected: full tests pass and Ruff reports `All checks passed!`.

Request code review and verify:

- Short documents keep one evidence item and the original ID.
- Long documents return at most 5 evidence items.
- Adjacent snippets overlap by 100 characters.
- Existing extraction and safety behavior is unchanged.
- Validator and README reflect bounded chunking.

Commit:

```bash
git add src/insight_graph/tools/document_reader.py tests/test_tools.py scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
git commit -m "feat: chunk long document reader evidence"
```

---

## Self-Review

- Spec coverage: The plan covers bounded chunking, compatibility for short documents, IDs, titles, overlap, validator updates, README updates, tests, full verification, and review.
- Placeholder scan: No unresolved placeholder sections remain.
- Type consistency: The public function remains `document_reader(query: str, subtask_id: str = "collect")`; new helpers use existing `Path`, `Evidence`, and `str` types.
