# document_reader Chunking Design

## Summary

Extend `document_reader` so long local documents can return multiple evidence snippets instead of truncating everything after the first 500 normalized characters.

The feature stays deterministic and offline. It does not add embeddings, semantic retrieval, page-level metadata, remote fetching, OCR, or LLM calls.

## Goals

- Preserve current behavior for short documents: one `Evidence` item with the existing stable ID.
- Return multiple `Evidence` items for long extracted text.
- Keep each snippet at `MAX_SNIPPET_CHARS = 500`.
- Add `SNIPPET_OVERLAP_CHARS = 100` so adjacent snippets preserve context.
- Add `MAX_DOCUMENT_EVIDENCE = 5` to cap context growth.
- Keep existing cwd containment, supported suffixes, extraction rules, PDF parser-log suppression, and failure behavior.
- Keep evidence shape unchanged: `title`, `source_url`, `snippet`, `source_type="docs"`, and `verified=True`.
- Update validator and README to document the bounded multi-evidence behavior.

## Non-Goals

- Returning every possible chunk from very large files.
- Page-level PDF evidence or line/section metadata.
- Semantic retrieval, ranking, or embeddings.
- Changing planner opt-in behavior, collector behavior, GraphState, or ToolCallRecord schema.
- Changing Analyst/Reporter citation handling.

## Design

After suffix-specific extraction and normalization, `document_reader` will split normalized text into bounded chunks:

- If normalized text length is at most 500, return one evidence item exactly as today.
- If longer, emit chunks of up to 500 characters.
- The next chunk starts `500 - 100 = 400` characters after the previous chunk start.
- Stop after 5 evidence items.
- Drop empty chunks.

Evidence IDs:

- First chunk keeps the current ID: `document-<relative-path-slug>-<hash>`.
- Later chunks append a suffix: `document-<relative-path-slug>-<hash>-chunk-2`, `-chunk-3`, etc.

Evidence titles:

- First chunk keeps `path.name`.
- Later chunks use `f"{path.name} (chunk {index})"` where `index` starts at 2.

This preserves compatibility for existing single-snippet consumers while allowing executor, relevance filtering, Analyst, and Reporter to use more coverage from long local documents without schema changes.

## Error Handling

No new error modes are introduced. If extraction fails or normalized text is empty, return `[]`. Chunking only runs after successful extraction and normalization.

## Tests

Add focused tests in `tests/test_tools.py`:

- A short document still returns one evidence item with the existing ID.
- A long document returns 5 evidence items.
- Each snippet length is at most 500.
- Later chunks have `-chunk-N` IDs and `(chunk N)` titles.
- Adjacent chunks overlap by 100 characters.

Update `scripts/validate_document_reader.py` and `tests/test_validate_document_reader.py`:

- Add a long text fixture and `long_file_chunking_success` case.
- Validate evidence count and summary count changes.

## Documentation

Update README to state that `document_reader` returns up to 5 bounded snippets for long local documents. Keep page-level pagination and semantic retrieval as future work.

## Verification

- `python -m pytest tests/test_tools.py::test_document_reader_chunks_long_documents tests/test_validate_document_reader.py -q`
- `python scripts/validate_document_reader.py`
- `python scripts/validate_document_reader.py --markdown`
- `python -m pytest -q`
- `python -m ruff check .`
