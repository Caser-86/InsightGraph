# document_reader HTML Support Design

## Summary

Extend `document_reader` to read local `.html` and `.htm` files inside the current working directory and return verified docs evidence from visible page text.

The feature stays deterministic and offline. It does not fetch URLs, parse PDF, paginate long files, run semantic retrieval, or call an LLM.

## Goals

- Accept `.html` and `.htm` paths in addition to the existing `.txt`, `.md`, and `.markdown` suffixes.
- Preserve the current path safety boundary: only files inside `Path.cwd()` are readable.
- Preserve current evidence shape: one `Evidence` item, `title=path.name`, `source_url=path.as_uri()`, `source_type="docs"`, `verified=True`.
- Extract visible HTML text while excluding `script`, `style`, and `noscript` content.
- Keep existing UTF-8 and empty-content failure behavior: invalid UTF-8, missing files, directories, unsupported suffixes, outside-root paths, and empty normalized snippets return `[]`.
- Update the offline validator and README to describe HTML support.

## Non-Goals

- PDF parsing.
- Remote HTML fetching.
- JavaScript rendering.
- Pagination, chunking, or semantic retrieval.
- Changing planner opt-in behavior or tool priority.
- Using `<title>` as evidence title; the title remains the filename for consistency with existing local document behavior.

## Design

`src/insight_graph/tools/document_reader.py` will keep its current public function:

```python
def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]
```

Implementation changes:

- Add `.html` and `.htm` to `SUPPORTED_SUFFIXES`.
- Read all supported files as UTF-8 text, as today.
- For HTML suffixes, parse the text with BeautifulSoup.
- Remove `script`, `style`, and `noscript` nodes before text extraction.
- Convert HTML to text with whitespace separators, then pass it through the existing `_normalize_snippet()` limit and whitespace normalization.
- For TXT/Markdown, keep the current direct text normalization path unchanged.

## Tests

Add focused tests in `tests/test_tools.py`:

- `.html` returns verified docs evidence with visible text and without script/style/noscript content.
- `.htm` is accepted.
- Existing unsupported suffix coverage keeps `.pdf` rejected.

Update `scripts/validate_document_reader.py` fixtures and tests so the validator includes a successful HTML case while remaining offline and temporary-directory scoped.

## Documentation

Update README references that currently say `document_reader` only supports TXT/Markdown and that HTML is future work. New wording should say TXT/Markdown/HTML are supported, while PDF, pagination, and semantic retrieval remain future work.

## Verification

- `python -m pytest tests/test_tools.py::test_document_reader_returns_verified_docs_evidence tests/test_tools.py::test_document_reader_reads_html_visible_text tests/test_tools.py::test_document_reader_accepts_htm_suffix tests/test_validate_document_reader.py -q`
- `python -m pytest -q`
- `python -m ruff check .`
