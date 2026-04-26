# document_reader HTML Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic/offline local `.html` and `.htm` support to `document_reader`.

**Architecture:** Keep the existing public `document_reader(query, subtask_id="collect")` boundary. Add HTML suffixes to the current local-file path, parse HTML with BeautifulSoup after removing non-visible nodes, then reuse current snippet normalization and evidence construction.

**Tech Stack:** Python, BeautifulSoup (`bs4`), pytest, Ruff.

---

## File Map

- Modify `src/insight_graph/tools/document_reader.py`: add HTML suffix support and `_extract_text()`.
- Modify `tests/test_tools.py`: add HTML and HTM tests beside current `document_reader` tests.
- Modify `scripts/validate_document_reader.py`: add one HTML fixture and validation case.
- Modify `tests/test_validate_document_reader.py`: assert the validator covers the HTML case if current assertions are fixed-name/fixed-count based.
- Modify `README.md`: update support wording from TXT/Markdown only to TXT/Markdown/HTML.

---

### Task 1: Add HTML Parsing To `document_reader`

**Files:**
- Modify: `src/insight_graph/tools/document_reader.py`
- Modify: `tests/test_tools.py`

- [ ] **Step 1: Write failing HTML tests**

Add these tests in `tests/test_tools.py` after `test_document_reader_returns_verified_docs_evidence`:

```python
def test_document_reader_reads_html_visible_text(tmp_path, monkeypatch) -> None:
    document = tmp_path / "market.html"
    document.write_text(
        """
        <!doctype html>
        <html>
          <head>
            <title>Ignored page title</title>
            <style>.hidden { display: none; }</style>
            <script>window.secret = "do not include";</script>
          </head>
          <body>
            <h1>Market Brief</h1>
            <p>Cursor adds agent mode.</p>
            <noscript>Do not include noscript fallback.</noscript>
            <p>GitHub Copilot updates docs.</p>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("market.html", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("market.html")
    assert evidence[0].subtask_id == "s1"
    assert evidence[0].title == "market.html"
    assert evidence[0].source_url == document.resolve().as_uri()
    assert evidence[0].snippet == (
        "Ignored page title Market Brief Cursor adds agent mode. "
        "GitHub Copilot updates docs."
    )
    assert "do not include" not in evidence[0].snippet.lower()
    assert evidence[0].source_type == "docs"
    assert evidence[0].verified is True


def test_document_reader_accepts_htm_suffix(tmp_path, monkeypatch) -> None:
    document = tmp_path / "brief.htm"
    document.write_text(
        "<html><body><main><p>Local HTM research note.</p></main></body></html>",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    evidence = document_reader("brief.htm", "s1")

    assert len(evidence) == 1
    assert evidence[0].id == document_id_for("brief.htm")
    assert evidence[0].title == "brief.htm"
    assert evidence[0].snippet == "Local HTM research note."
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_reads_html_visible_text tests/test_tools.py::test_document_reader_accepts_htm_suffix -q
```

Expected: both tests fail because `.html` and `.htm` are not in `SUPPORTED_SUFFIXES`.

- [ ] **Step 3: Implement minimal HTML support**

Update `src/insight_graph/tools/document_reader.py` with these exact changes:

```python
from bs4 import BeautifulSoup

SUPPORTED_SUFFIXES = {".txt", ".md", ".markdown", ".html", ".htm"}
HTML_SUFFIXES = {".html", ".htm"}
```

Replace the snippet assignment with:

```python
snippet = _normalize_snippet(_extract_text(text, path.suffix.lower()))
```

Add this helper above `_resolve_inside_root()`:

```python
def _extract_text(text: str, suffix: str) -> str:
    if suffix not in HTML_SUFFIXES:
        return text
    soup = BeautifulSoup(text, "html.parser")
    for element in soup(["script", "style", "noscript"]):
        element.decompose()
    return soup.get_text(" ")
```

Keep `_resolve_inside_root()`, `_normalize_snippet()`, `_evidence_id()`, and `_slugify()` unchanged.

- [ ] **Step 4: Run focused tests to verify they pass**

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_returns_verified_docs_evidence tests/test_tools.py::test_document_reader_reads_html_visible_text tests/test_tools.py::test_document_reader_accepts_htm_suffix tests/test_tools.py::test_document_reader_rejects_invalid_paths -q
```

Expected: all selected tests pass.

- [ ] **Step 5: Run Ruff on touched code**

Run:

```bash
python -m ruff check src/insight_graph/tools/document_reader.py tests/test_tools.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add src/insight_graph/tools/document_reader.py tests/test_tools.py
git commit -m "feat: add html document reader support"
```

---

### Task 2: Update Offline Validator And Documentation

**Files:**
- Modify: `scripts/validate_document_reader.py`
- Modify: `tests/test_validate_document_reader.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing validator expectation**

Inspect `tests/test_validate_document_reader.py`. If it asserts fixed validation case names or counts, update it so the existing validation test includes:

```python
case_names = {case["name"] for case in result["cases"]}
assert "html_file_success" in case_names
```

Run:

```bash
python -m pytest tests/test_validate_document_reader.py -q
```

Expected: fails because the validator does not create or run an HTML case yet.

- [ ] **Step 2: Add HTML fixture and validation case**

In `scripts/validate_document_reader.py`, add this fixture in `_write_fixtures()` after the Markdown fixtures:

```python
(workspace / "brief.html").write_text(
    """
    <html>
      <head><style>.x { color: red; }</style></head>
      <body><h1>HTML market brief</h1><p>HTML document_reader support.</p></body>
    </html>
    """,
    encoding="utf-8",
)
```

Add this case in `_validation_cases()` after `markdown_suffix_success`:

```python
ValidationCase(
    "html_file_success",
    "brief.html",
    1,
    "brief.html",
    "HTML market brief",
),
```

- [ ] **Step 3: Update README support wording**

Replace the README wording that says `document_reader` only supports TXT/Markdown and HTML is future work with wording that says it supports `.txt`, `.md`, `.markdown`, `.html`, and `.htm`, while PDF, pagination, and semantic retrieval remain future work.

Use this tool table row:

```markdown
| `document_reader` | 当前读取 cwd 内本地 `.txt`、`.md`、`.markdown`、`.html`、`.htm` 文件；PDF、分页读取与语义检索属于后续路线图 |
```

Use this script status row:

```markdown
| `scripts/validate_document_reader.py` | 当前可用 | 离线验证当前本地 TXT/Markdown/HTML `document_reader` 行为，默认 JSON 输出，`--markdown` 输出表格；PDF、分页读取与语义检索验证属于后续路线图 |
```

Use this validator description sentence:

```markdown
该脚本会在临时目录内创建 TXT/Markdown/HTML fixtures，并验证 `document_reader` 的成功读取、unsupported/empty/invalid 文件、缺失文件和路径越界返回空结果；不读取用户文件、不访问公网、不调用 LLM。
```

- [ ] **Step 4: Run focused tests and validator smoke**

Run:

```bash
python -m pytest tests/test_validate_document_reader.py tests/test_tools.py::test_document_reader_reads_html_visible_text tests/test_tools.py::test_document_reader_accepts_htm_suffix -q
python scripts/validate_document_reader.py
python scripts/validate_document_reader.py --markdown
```

Expected: tests pass; both smoke commands exit 0 and include `html_file_success`.

- [ ] **Step 5: Run Ruff on touched code**

Run:

```bash
python -m ruff check scripts/validate_document_reader.py tests/test_validate_document_reader.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add scripts/validate_document_reader.py tests/test_validate_document_reader.py README.md
git commit -m "docs: document html document reader support"
```

---

### Task 3: Final Verification And Review

**Files:**
- Verify all touched files.

- [ ] **Step 1: Run final focused tests**

Run:

```bash
python -m pytest tests/test_tools.py::test_document_reader_returns_verified_docs_evidence tests/test_tools.py::test_document_reader_reads_html_visible_text tests/test_tools.py::test_document_reader_accepts_htm_suffix tests/test_validate_document_reader.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full verification**

Run:

```bash
python -m pytest -q
python -m ruff check .
```

Expected: full tests pass and Ruff reports `All checks passed!`.

- [ ] **Step 3: Request code review**

Review the diff from the implementation base commit through `HEAD`. Confirm:

- HTML parsing stays local/offline.
- Existing TXT/Markdown behavior is unchanged.
- Path containment remains enforced before reads.
- HTML extraction removes `script`, `style`, and `noscript`.
- README no longer says HTML is future work.

- [ ] **Step 4: Finish branch**

Use `superpowers:finishing-a-development-branch` to offer merge, PR, keep, or discard options.

---

## Self-Review

- Spec coverage: Tasks cover HTML suffix support, visible text extraction, safety preservation, validator updates, README updates, focused tests, full tests, Ruff, and review.
- Placeholder scan: No unresolved placeholder sections remain.
- Type consistency: The public function remains `document_reader(query: str, subtask_id: str = "collect")`; helpers are internal and use plain `str` inputs.
