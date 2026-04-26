# run_with_llm_log Document Query Example Design

## Summary

Document and test that `scripts/run_with_llm_log.py` can pass `document_reader` JSON query strings through unchanged while still writing safe LLM metadata logs.

## Goals

- Keep `scripts/run_with_llm_log.py` runtime behavior unchanged.
- Verify JSON query strings are passed unchanged to `run_research_func`.
- Verify the safe log payload records the query metadata without adding sensitive content.
- Add README examples for using `INSIGHT_GRAPH_USE_DOCUMENT_READER=1` with `run_with_llm_log.py`.

## Non-Goals

- New CLI flags.
- New scripts.
- Changing log schema.
- Running network, embeddings, or LLM calls in tests.

## Design

Add a focused test in `tests/test_run_with_llm_log_script.py` that invokes `main()` with a JSON string query and a fake `run_research_func`. The test asserts:

- The fake workflow receives the exact JSON string.
- The generated log file contains that exact query in the `query` field.
- The script exits `0` and writes Markdown plus the log path.

Update README's `run_with_llm_log.py` usage section with a document-reader JSON query example and clarify that ranking is deterministic lexical matching, not embeddings, LLM retrieval, or network access.

## Verification

- `python -m pytest tests/test_run_with_llm_log_script.py -q`
- `python -m pytest -q`
- `python -m ruff check .`
