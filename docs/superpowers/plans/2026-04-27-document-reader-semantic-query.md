# document_reader Semantic Query Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic lexical query ranking for `document_reader` chunks via optional JSON input.

**Architecture:** Keep plain path input unchanged. Parse JSON object input inside `document_reader`, extract `path` and optional `query`, generate chunks as today, and rank candidate chunks by deterministic query-token overlap before applying the existing evidence cap.

**Tech Stack:** Python standard library, pytest, Ruff.

---

## File Map

- Modify `src/insight_graph/tools/document_reader.py`: parse query input and rank chunks lexically.
- Modify `tests/test_tools.py`: add JSON query ranking and compatibility tests.
- Modify `scripts/validate_document_reader.py`: add a query-ranked validation case.
- Modify `tests/test_validate_document_reader.py`: update fixed cases and summary counts.
- Modify `README.md`: document JSON input and deterministic lexical ranking.

---

### Task 1: Implement Query-Aware Ranking In One Batch

**Files:**
- Modify: `src/insight_graph/tools/document_reader.py`
- Modify: `tests/test_tools.py`
- Modify: `scripts/validate_document_reader.py`
- Modify: `tests/test_validate_document_reader.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing tests**

Add tests in `tests/test_tools.py` after chunking tests:

```python
def test_document_reader_ranks_chunks_with_json_query(tmp_path, monkeypatch) -> None:
    document = tmp_path / "ranked.md"
    chunks = [
        "alpha " * 100,
        "beta " * 100,
        "enterprise pricing " * 40,
        "gamma " * 100,
    ]
    document.write_text(" ".join(chunks), encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader(
        '{"path":"ranked.md","query":"enterprise pricing"}',
        "s1",
    )

    assert len(evidence) >= 1
    assert "enterprise pricing" in evidence[0].snippet
    assert evidence[0].id.endswith("chunk-3") or evidence[0].id.endswith("chunk-4")
    assert evidence[0].title.startswith("ranked.md (chunk ")
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_document_reader_json_query_falls_back_when_no_terms_match(
    tmp_path, monkeypatch
) -> None:
    document = tmp_path / "fallback.md"
    document.write_text("alpha " * 500, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader('{"path":"fallback.md","query":"unmatched"}', "s1")

    assert len(evidence) == 5
    assert evidence[0].id == document_id_for("fallback.md")
    assert evidence[1].id == f"{document_id_for('fallback.md')}-chunk-2"


def test_document_reader_invalid_json_input_is_treated_as_path(
    tmp_path, monkeypatch
) -> None:
    document = tmp_path / "{not-json}.md"
    document.write_text("Curly filename content.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("{not-json}.md", "s1")

    assert len(evidence) == 1
    assert evidence[0].title == "{not-json}.md"
    assert evidence[0].snippet == "Curly filename content."


def test_document_reader_json_object_without_valid_path_returns_empty() -> None:
    assert document_reader('{"query":"pricing"}', "s1") == []
    assert document_reader('{"path":"","query":"pricing"}', "s1") == []
    assert document_reader('{"path":123,"query":"pricing"}', "s1") == []
```

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_ranks_chunks_with_json_query tests/test_tools.py::test_document_reader_json_query_falls_back_when_no_terms_match tests/test_tools.py::test_document_reader_invalid_json_input_is_treated_as_path tests/test_tools.py::test_document_reader_json_object_without_valid_path_returns_empty -q
```

Expected: JSON query ranking tests fail because JSON input is currently treated as a path.

- [ ] **Step 2: Implement input parsing and ranking**

In `src/insight_graph/tools/document_reader.py`, add imports:

```python
import json
from dataclasses import dataclass
```

Add dataclass:

```python
@dataclass(frozen=True)
class DocumentReaderQuery:
    path: str
    retrieval_query: str | None = None
```

At the top of `document_reader()`, parse query:

```python
    parsed_query = _parse_document_reader_query(query)
    if parsed_query is None:
        return []
    path = _resolve_inside_root(root, parsed_query.path)
```

Replace snippet generation with ranked candidates:

```python
    normalized_text = _normalize_snippet(_extract_text(text, path.suffix.lower()))
    snippets = _select_snippets(normalized_text, parsed_query.retrieval_query)
```

Add helpers:

```python
def _parse_document_reader_query(query: str) -> DocumentReaderQuery | None:
    try:
        parsed = json.loads(query)
    except json.JSONDecodeError:
        return DocumentReaderQuery(path=query)
    if not isinstance(parsed, dict):
        return DocumentReaderQuery(path=query)
    path = parsed.get("path")
    if not isinstance(path, str) or not path.strip():
        return None
    retrieval_query = parsed.get("query")
    if not isinstance(retrieval_query, str) or not retrieval_query.strip():
        retrieval_query = None
    return DocumentReaderQuery(path=path.strip(), retrieval_query=retrieval_query.strip() if retrieval_query else None)


def _select_snippets(text: str, retrieval_query: str | None) -> list[tuple[str, int]]:
    candidates = _chunk_snippets(text)
    if not retrieval_query:
        return candidates[:MAX_DOCUMENT_EVIDENCE]
    ranked = _rank_snippets(candidates, retrieval_query)
    return ranked[:MAX_DOCUMENT_EVIDENCE] if ranked else candidates[:MAX_DOCUMENT_EVIDENCE]


def _chunk_snippets(text: str) -> list[tuple[str, int]]:
    if not text:
        return []
    if len(text) <= MAX_SNIPPET_CHARS:
        return [(text, 0)]
    step = MAX_SNIPPET_CHARS - SNIPPET_OVERLAP_CHARS
    return [
        (text[start : start + MAX_SNIPPET_CHARS], index)
        for index, start in enumerate(range(0, len(text), step))
        if text[start : start + MAX_SNIPPET_CHARS]
    ]


def _rank_snippets(
    candidates: list[tuple[str, int]],
    retrieval_query: str,
) -> list[tuple[str, int]]:
    query_tokens = set(_tokenize(retrieval_query))
    if not query_tokens:
        return []
    scored = []
    for snippet, index in candidates:
        tokens = _tokenize(snippet)
        score = sum(1 for token in tokens if token in query_tokens)
        distinct_matches = len({token for token in tokens if token in query_tokens})
        if score > 0:
            scored.append((score, distinct_matches, -index, snippet, index))
    scored.sort(reverse=True)
    return [(snippet, index) for _, _, _, snippet, index in scored]


def _tokenize(value: str) -> list[str]:
    return [token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) >= 3]
```

Update `document_reader()` evidence construction to preserve original chunk indexes:

```python
    return [
        _build_evidence(root, path, subtask_id, snippet, index)
        for snippet, index in snippets
    ]
```

Keep `_build_evidence()` chunk numbering based on `index + 1`.

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_chunks_long_documents tests/test_tools.py::test_document_reader_ranks_chunks_with_json_query tests/test_tools.py::test_document_reader_json_query_falls_back_when_no_terms_match tests/test_tools.py::test_document_reader_invalid_json_input_is_treated_as_path tests/test_tools.py::test_document_reader_json_object_without_valid_path_returns_empty -q
python -m ruff check src/insight_graph/tools/document_reader.py tests/test_tools.py
```

Expected: tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 3: Update validator and README**

Add a query-ranked fixture/case in `scripts/validate_document_reader.py`:

```python
(workspace / "ranked.txt").write_text(
    ("alpha " * 100) + ("enterprise pricing " * 40),
    encoding="utf-8",
)
```

Add validation case:

```python
ValidationCase(
    "json_query_ranking_success",
    '{"path":"ranked.txt","query":"enterprise pricing"}',
    1,
    "ranked.txt (chunk 2)",
    "enterprise pricing",
),
```

Update `tests/test_validate_document_reader.py` fixed case names, metadata assertions, and counts:

- Add `json_query_ranking_success` after `long_file_chunking_success`.
- Assert title is `ranked.txt (chunk 2)` and snippet check true.
- Summary: `case_count=14`, `passed_count=14`, `total_evidence_count=12`.
- Failing-reader counts: `case_count=14`, `failed_count=14`.
- Markdown summary: `| 14 | 14 | 0 | true | 12 |`.
- JSON main case count: `14`.

Update README with examples:

```bash
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python -m insight_graph.cli research README.md
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python -m insight_graph.cli research '{"path":"report.pdf","query":"enterprise pricing"}'
```

Document that JSON query ranking is deterministic lexical matching, not embeddings or LLM retrieval.

Run:

```bash
python -m pytest tests/test_validate_document_reader.py tests/test_tools.py::test_document_reader_ranks_chunks_with_json_query -q
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
python -m ruff check scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
```

Expected: tests pass; validator includes `json_query_ranking_success`; Ruff reports `All checks passed!`.

- [ ] **Step 4: Final verification, review, and commit**

Run:

```bash
python -m pytest -q
python -m ruff check .
```

Expected: full tests pass and Ruff reports `All checks passed!`.

Request code review and verify:

- Plain path behavior remains compatible.
- JSON query object ranks chunks deterministically.
- Invalid JSON path filenames still work.
- Valid JSON object without a valid path returns `[]`.
- No LLMs, embeddings, remote calls, or dependency changes.

Commit:

```bash
git add src/insight_graph/tools/document_reader.py tests/test_tools.py scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
git commit -m "feat: rank document reader chunks by query"
```

---

## Self-Review

- Spec coverage: Covers JSON query input, path compatibility, lexical ranking, fallback, validator, README, tests, full verification, and review.
- Placeholder scan: No unresolved placeholder sections remain.
- Type consistency: Public function remains `document_reader(query: str, subtask_id: str = "collect")`; helper types use existing standard-library types.
