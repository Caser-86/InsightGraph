# run_research Document Query Example Design

## Summary

Improve the discoverability of `document_reader` JSON query ranking by documenting how to pass JSON query strings through `scripts/run_research.py` and adding a regression test that the wrapper preserves those strings exactly.

## Goals

- Keep `scripts/run_research.py` runtime behavior unchanged.
- Verify JSON query strings are passed unchanged to `run_research_func`.
- Add README examples for local document retrieval with `INSIGHT_GRAPH_USE_DOCUMENT_READER=1`.
- Clarify that document query ranking is deterministic lexical matching, not embeddings or LLM retrieval.

## Non-Goals

- New scripts.
- New CLI flags.
- Changing planner, executor, or `document_reader` behavior.
- Running network or LLM calls in tests.

## Design

Add a focused test in `tests/test_run_research_script.py` that calls `run_research_script.main()` with a JSON string query and a fake `run_research_func`. The test asserts the fake receives the exact JSON string.

Update README's `scripts/run_research.py` usage section with a document-reader JSON query example:

```bash
INSIGHT_GRAPH_USE_DOCUMENT_READER=1 python scripts/run_research.py '{"path":"report.md","query":"enterprise pricing"}'
```

The docs should state that `document_reader` ranks chunks with deterministic lexical matching and does not use embeddings, LLMs, or network access.

## Verification

- `python -m pytest tests/test_run_research_script.py -q`
- `python -m pytest -q`
- `python -m ruff check .`
