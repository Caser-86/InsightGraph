# document_reader PDF Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic/offline local `.pdf` support to `document_reader`.

**Architecture:** Keep `document_reader(query, subtask_id="collect")` as the only public boundary. Add `pypdf` as a normal dependency, route suffix-specific extraction through small internal helpers, and preserve the existing single-evidence output shape and cwd containment checks.

**Tech Stack:** Python, pypdf, BeautifulSoup, pytest, Ruff.

---

## File Map

- Modify `pyproject.toml`: add `pypdf>=4.0.0` to `[project].dependencies`.
- Modify `src/insight_graph/tools/document_reader.py`: add PDF suffix support and binary PDF extraction.
- Modify `tests/test_tools.py`: add raw-PDF fixture helper and PDF success/failure tests.
- Modify `scripts/validate_document_reader.py`: add raw-PDF fixture generation and `pdf_file_success`.
- Modify `tests/test_validate_document_reader.py`: update fixed case names, summary counts, and metadata assertions.
- Modify `README.md`: document TXT/Markdown/HTML/PDF support and leave OCR/pagination/semantic retrieval out of scope.

---

### Task 1: Implement PDF Support In One Batch

**Files:**
- Modify: `pyproject.toml`
- Modify: `src/insight_graph/tools/document_reader.py`
- Modify: `tests/test_tools.py`
- Modify: `scripts/validate_document_reader.py`
- Modify: `tests/test_validate_document_reader.py`
- Modify: `README.md`

- [ ] **Step 1: Add failing PDF tests**

In `tests/test_tools.py`, add this helper near `document_id_for()`:

```python
def write_minimal_pdf(path, text: str) -> None:
    escaped_text = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content.encode('utf-8'))} >>\nstream\n{content}\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n{body}\nendobj\n".encode("utf-8"))
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("utf-8")
    )
    path.write_bytes(bytes(output))
```

Add these tests after the HTML tests:

```python
def test_document_reader_reads_pdf_text(tmp_path, monkeypatch) -> None:
    document = tmp_path / "market.pdf"
    write_minimal_pdf(document, "PDF market brief for Cursor and GitHub Copilot.")
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("market.pdf", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("market.pdf")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "market.pdf"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == "PDF market brief for Cursor and GitHub Copilot."
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_document_reader_rejects_malformed_pdf(tmp_path, monkeypatch) -> None:
    document = tmp_path / "broken.pdf"
    document.write_bytes(b"not a valid pdf")
    monkeypatch.chdir(tmp_path)

    assert document_reader("broken.pdf", "s1") == []
```

Update `test_document_reader_rejects_invalid_paths()` so the unsupported fixture and query use `.docx` instead of `.pdf`:

```python
"unsupported.docx",
```

and:

```python
(tmp_path / "unsupported.docx").write_text("docx text", encoding="utf-8")
```

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_reads_pdf_text tests/test_tools.py::test_document_reader_rejects_malformed_pdf tests/test_tools.py::test_document_reader_rejects_invalid_paths -q
```

Expected: PDF tests fail because `.pdf` is not supported yet; invalid path tests still pass.

- [ ] **Step 2: Add dependency and implement PDF extraction**

In `pyproject.toml`, add `pypdf>=4.0.0` to dependencies:

```toml
  "pypdf>=4.0.0",
```

Install the updated editable package:

```bash
python -m pip install -e .
```

In `src/insight_graph/tools/document_reader.py`, add imports and suffix constants:

```python
from pypdf import PdfReader
from pypdf.errors import PdfReadError

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm", ".pdf"}
HTML_SUFFIXES = {".html", ".htm"}
PDF_SUFFIXES = {".pdf"}
```

Replace the current text read block with:

```python
    try:
        text = _read_document_text(path)
    except (OSError, UnicodeDecodeError, PdfReadError):
        return []

    snippet = _normalize_snippet(_extract_text(text, path.suffix.lower()))
```

Add these helpers above `_extract_text()`:

```python
def _read_document_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in PDF_SUFFIXES:
        return _read_pdf_text(path)
    return path.read_text(encoding="utf-8")


def _read_pdf_text(path: Path) -> str:
    with path.open("rb") as handle:
        reader = PdfReader(handle)
        if reader.is_encrypted:
            return ""
        return "\n".join(page.extract_text() or "" for page in reader.pages)
```

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_reads_pdf_text tests/test_tools.py::test_document_reader_rejects_malformed_pdf tests/test_tools.py::test_document_reader_rejects_invalid_paths -q
python -m ruff check pyproject.toml src/insight_graph/tools/document_reader.py tests/test_tools.py
```

Expected: tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 3: Update validator and docs**

In `scripts/validate_document_reader.py`, add a local helper near `_write_fixtures()`:

```python
def _write_minimal_pdf(path: Path, text: str) -> None:
    escaped_text = text.replace("\\", "\\\\").replace("(", r"\(").replace(")", r"\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped_text}) Tj ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content.encode('utf-8'))} >>\nstream\n{content}\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n{body}\nendobj\n".encode("utf-8"))
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("utf-8"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("utf-8"))
    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("utf-8")
    )
    path.write_bytes(bytes(output))
```

In `_write_fixtures()`, add:

```python
_write_minimal_pdf(workspace / "brief.pdf", "PDF market brief for document_reader.")
(workspace / "unsupported.docx").write_text("not a supported document", encoding="utf-8")
```

Remove the old `unsupported.pdf` fixture line.

In `_validation_cases()`, add the PDF success case after `html_file_success`:

```python
ValidationCase(
    "pdf_file_success",
    "brief.pdf",
    1,
    "brief.pdf",
    "PDF market brief",
),
```

Change unsupported suffix case to:

```python
ValidationCase("unsupported_suffix_returns_empty", "unsupported.docx", 0),
```

In `tests/test_validate_document_reader.py`, insert `"pdf_file_success"` after `"html_file_success"`; add metadata assertions:

```python
    pdf_case = case_by_name(payload, "pdf_file_success")
    assert pdf_case["title"] == "brief.pdf"
    assert pdf_case["snippet_contains"] is True
```

Update summary counts from 11/5 to 12/6 and failure case counts from 11 to 12.

In README, update the relevant document reader wording to say `.txt`, `.md`, `.markdown`, `.html`, `.htm`, and `.pdf` are supported; OCR, pagination, and semantic retrieval remain out of scope. Update validator wording from TXT/Markdown/HTML to TXT/Markdown/HTML/PDF.

Run:

```bash
python -m pytest tests/test_validate_document_reader.py tests/test_tools.py::test_document_reader_reads_pdf_text tests/test_tools.py::test_document_reader_rejects_malformed_pdf -q
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
python -m ruff check scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
```

Expected: focused tests pass, both validator smoke commands include `pdf_file_success`, and Ruff reports `All checks passed!`.

- [ ] **Step 4: Final verification, review, and commit**

Run:

```bash
python -m pytest -q
python -m ruff check .
```

Expected: full tests pass and Ruff reports `All checks passed!`.

Request code review for the full diff and verify:

- PDF support remains local/offline and path-contained.
- TXT/Markdown/HTML behavior is unchanged.
- Malformed/encrypted/no-text PDFs return `[]`.
- README no longer says PDF is future work.

Commit the implementation in one commit:

```bash
git add pyproject.toml src/insight_graph/tools/document_reader.py tests/test_tools.py scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
git commit -m "feat: add pdf document reader support"
```

---

## Self-Review

- Spec coverage: The plan covers `pypdf` dependency, `.pdf` suffix support, cwd containment, single evidence shape, malformed PDF handling, validator updates, README updates, focused tests, full tests, Ruff, and review.
- Placeholder scan: No unresolved placeholder sections remain.
- Type consistency: The public function remains `document_reader(query: str, subtask_id: str = "collect")`; all new PDF helpers are internal and use `Path`/`str` inputs.
