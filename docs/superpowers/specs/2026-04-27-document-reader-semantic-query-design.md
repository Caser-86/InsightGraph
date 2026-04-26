# document_reader Semantic Query Design

## Summary

Add deterministic query-aware chunk selection to `document_reader` without changing `ToolRegistry`, Executor, GraphState, or the `Evidence` schema.

Plain path input remains fully compatible. JSON object input can provide both a local file path and a retrieval query:

```json
{"path":"report.pdf","query":"pricing strategy enterprise plan"}
```

When a retrieval query is present, `document_reader` ranks extracted chunks with a deterministic lexical score and returns the top bounded snippets.

## Goals

- Keep existing path-only behavior unchanged.
- Support JSON object input with `path` and `query` string fields.
- Keep cwd containment and supported suffix checks before file reads.
- Rank chunks deterministically by query-term overlap, without LLMs, embeddings, remote calls, or new dependencies.
- Keep returning at most `MAX_DOCUMENT_EVIDENCE = 5` evidence items.
- Keep each snippet at most `MAX_SNIPPET_CHARS = 500` with existing overlap generation.
- Preserve evidence shape and ID/title convention.
- Update validator and README to document JSON query input.

## Non-Goals

- Vector embeddings or semantic models.
- LLM-based ranking.
- Changing planner/tool registry/executor interfaces.
- Requiring JSON input for existing users.
- Ranking across multiple files.

## Input Format

`document_reader(query: str, subtask_id: str = "collect")` accepts:

1. Plain path string, existing behavior:

```text
report.md
```

2. JSON object string:

```json
{"path":"report.md","query":"enterprise pricing"}
```

Rules:

- JSON must decode to an object.
- `path` must be a non-empty string.
- `query` is optional but only enables ranking when it is a non-empty string.
- Invalid JSON falls back to treating the whole input as a path, preserving compatibility with unusual filenames.
- JSON object without valid `path` returns `[]`.
- Extra JSON fields are ignored.

## Ranking Design

The tool first extracts and normalizes full document text exactly as today, then creates candidate chunks using the current 500-character / 100-character overlap / 5-result cap mechanics except internally it may generate enough candidates to rank before applying the final cap.

For query-aware ranking:

- Tokenize query and chunks with a lowercase alphanumeric regex.
- Drop tokens shorter than 3 characters.
- Score each chunk by summed query token frequency in that chunk.
- Prefer chunks with more distinct matched query tokens as a tie-breaker.
- Preserve original chunk order as the final tie-breaker.
- Return only chunks with score greater than zero.
- If no chunks match, fall back to the original first 5 chunks.

Returned evidence uses the selected chunk text but keeps chunk numbers based on the original chunk index. For example, if selected original chunks are 1, 4, and 6, their IDs are base, `-chunk-4`, and `-chunk-6`. This preserves traceability to the original document order and avoids pretending ranked results are adjacent.

## Error Handling

- Invalid JSON string input is treated as a path.
- Valid JSON object with missing/empty/non-string `path` returns `[]`.
- Valid JSON object with empty/non-string `query` uses path-only behavior.
- Existing file errors, parser errors, malformed PDFs, encrypted PDFs, no-text PDFs, unsupported suffixes, and outside-root paths still return `[]`.

## Tests

Add focused tests in `tests/test_tools.py`:

- Plain path behavior for long docs remains original first-5 chunk order.
- JSON query input ranks matching chunks ahead of earlier non-matching chunks.
- JSON query input falls back to first chunks when no query terms match.
- Invalid JSON is treated as a path.
- Valid JSON object without valid path returns `[]`.

Update `scripts/validate_document_reader.py` and `tests/test_validate_document_reader.py`:

- Add a query-ranked fixture case.
- Keep validator offline and temporary-directory scoped.

## Documentation

Update README with JSON query examples and clarify that ranking is deterministic lexical retrieval, not embeddings or LLM semantic search.

## Verification

- `python -m pytest tests/test_tools.py::test_document_reader_ranks_chunks_with_json_query tests/test_validate_document_reader.py -q`
- `python scripts/validate_document_reader.py`
- `python scripts/validate_document_reader.py --markdown`
- `python -m pytest -q`
- `python -m ruff check .`
