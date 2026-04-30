# validate_pdf_fetch.py Design

## Goal

Add a validation script matching the reference project's `validate_pdf_fetch.py` surface. The first implementation validates PDF evidence extraction and retrieval metadata without network access by default.

## Behavior

`scripts/validate_pdf_fetch.py` creates a temporary workspace with generated PDF fixtures. It validates:

- local PDF parsing through `document_reader`
- local PDF retrieval through `search_document`
- remote PDF extraction through `fetch_url` using a fake in-process fetcher
- JSON query ranking for PDF chunks
- PDF page metadata and chunk metadata
- encrypted/bad/empty PDF safety behavior returning no evidence

The script writes JSON by default and Markdown with `--markdown`, following the existing validator script style. It never reads user files, never calls the network, and never calls an LLM.

## Output Shape

The JSON payload contains:

- `cases`: per-case result objects with query, pass/fail, evidence count, title, source type, source URL scheme, chunk index, document page, snippet check, and sanitized error.
- `summary`: case counts, pass/fail counts, total evidence count, and `all_passed`.

Exit codes:

- `0`: script ran and all validation cases passed
- `1`: script ran but one or more cases failed
- `2`: argument, fixture, output, or script-level failure

## Architecture

Reuse the existing validator pattern from `scripts/validate_document_reader.py`: custom argparse parser, temporary cwd context manager, deterministic fixtures, sanitized case errors, Markdown table formatting, and stdout/stderr injection for tests.

Remote PDF validation monkeypatches/fakes `fetch_url.fetch_text` in-process. Live URL validation is out of scope for this phase.

## Testing

Add `tests/test_validate_pdf_fetch.py` covering case list, success metadata, empty cases, summary, markdown output, parse errors, stdout write errors, cwd restoration, and sanitized exception handling.
