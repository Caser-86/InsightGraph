# document_reader PDF Support Design

## Summary

Extend `document_reader` to read local `.pdf` files inside the current working directory and return verified docs evidence from extracted PDF text.

The feature stays deterministic and offline. It does not fetch URLs, perform OCR, render pages, paginate large PDFs, run semantic retrieval, or call an LLM.

## Goals

- Accept `.pdf` paths in addition to existing `.txt`, `.md`, `.markdown`, `.html`, and `.htm` suffixes.
- Add `pypdf` as a normal project dependency so PDF support works in the default install.
- Preserve the current path safety boundary: only files inside `Path.cwd()` are readable.
- Preserve current evidence shape: one `Evidence` item, `title=path.name`, `source_url=path.as_uri()`, `source_type="docs"`, `verified=True`.
- Extract text from each PDF page with `pypdf.PdfReader` and concatenate page text before the existing snippet normalization and 500-character limit.
- Return `[]` for missing files, directories, unsupported suffixes, outside-root paths, encrypted PDFs, malformed PDFs, PDFs with no extractable text, and read failures.
- Update the offline validator and README to describe PDF support.

## Non-Goals

- OCR for scanned PDFs.
- Remote PDF fetching.
- JavaScript or embedded file handling.
- Page-level evidence, pagination, chunking, or semantic retrieval.
- Changing planner opt-in behavior or tool priority.
- Returning multiple `Evidence` items per PDF.

## Dependency

Add `pypdf>=4.0.0` to `pyproject.toml` `[project].dependencies`.

Rationale:

- Pure Python and widely used for PDF text extraction.
- Keeps `document_reader` PDF support available by default, matching the current README style where supported suffixes are directly available once the package is installed.
- Avoids an extra-dependency path that would make `.pdf` behavior vary by installation.

## Design

`src/insight_graph/tools/document_reader.py` keeps the same public function:

```python
def document_reader(query: str, subtask_id: str = "collect") -> list[Evidence]
```

Implementation changes:

- Add `.pdf` to `SUPPORTED_SUFFIXES`.
- Add `PDF_SUFFIXES = {".pdf"}`.
- Keep path resolution, `is_file()`, suffix validation, and cwd containment before opening the file.
- Split extraction by suffix:
  - TXT/Markdown: read UTF-8 text and normalize as today.
  - HTML/HTM: read UTF-8 text, remove `script`, `style`, `noscript`, extract body text as today.
  - PDF: open the file in binary mode, create `PdfReader`, reject encrypted PDFs, extract page text with `page.extract_text() or ""`, join pages with newlines, then normalize.
- Catch `OSError`, `UnicodeDecodeError`, and `pypdf.errors.PdfReadError` around extraction and return `[]`.
- If normalized snippet is empty, return `[]`.

The existing evidence ID remains based on the cwd-relative POSIX path and suffix, so PDF IDs are stable and collision-resistant in the same way as other local documents.

## Error Handling

All PDF failure paths return `[]` rather than raising:

- Malformed or unreadable PDF.
- Encrypted PDF.
- PDF with pages but no extractable text.
- File open/read errors.

The tool does not expose raw parser exceptions in evidence or logs.

## Tests

Add or update focused tests in `tests/test_tools.py`:

- A minimal generated PDF fixture returns one verified docs evidence item for `.pdf`.
- The PDF evidence keeps `title=path.name`, `source_url=path.as_uri()`, `source_type="docs"`, and `verified=True`.
- A malformed `.pdf` returns `[]`.
- Unsupported suffix coverage uses a non-PDF suffix such as `.docx`.
- Existing TXT/Markdown/HTML tests continue to pass.

Update `scripts/validate_document_reader.py` fixtures and tests:

- Generate a small PDF fixture in the temporary validation workspace.
- Add `pdf_file_success` with expected title and snippet.
- Keep the unsupported case with a non-PDF suffix.

## Documentation

Update README references that currently say PDF is future work. New wording should say TXT/Markdown/HTML/PDF are supported, while pagination and semantic retrieval remain future work. OCR is not supported.

## Verification

- `python -m pytest tests/test_tools.py::test_document_reader_reads_pdf_text tests/test_tools.py::test_document_reader_rejects_malformed_pdf tests/test_validate_document_reader.py -q`
- `python scripts/validate_document_reader.py`
- `python scripts/validate_document_reader.py --markdown`
- `python -m pytest -q`
- `python -m ruff check .`
