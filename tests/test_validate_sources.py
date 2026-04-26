import io
import json

from scripts.validate_sources import main, validate_report

VALID_REPORT = """# Report

Cursor pricing is documented publicly [1]. Copilot docs describe product behavior [2].

## References

[1] Cursor Pricing. https://cursor.com/pricing
[2] GitHub Copilot Docs. https://docs.github.com/en/copilot
"""


def issue_types(payload: dict) -> list[str]:
    return [issue["type"] for issue in payload["issues"]]


def test_validate_report_accepts_valid_references():
    payload = validate_report(VALID_REPORT)

    assert payload == {
        "ok": True,
        "citation_count": 2,
        "reference_count": 2,
        "issues": [],
    }


def test_validate_report_reports_missing_references_section():
    payload = validate_report("# Report\n\nThis report cites one source [1].\n")

    assert payload["ok"] is False
    assert payload["citation_count"] == 1
    assert payload["reference_count"] == 0
    assert payload["issues"] == [
        {
            "type": "missing_references_section",
            "reference": None,
            "message": "Report has no References or Sources section.",
        }
    ]


def test_validate_report_reports_missing_reference_for_citation():
    payload = validate_report(
        """# Report

The report cites a missing source [2].

## References

[1] Existing source. https://example.com/source
"""
    )

    assert issue_types(payload) == ["missing_reference", "unused_reference"]
    assert payload["issues"][0] == {
        "type": "missing_reference",
        "reference": 2,
        "message": "Citation [2] has no matching reference.",
    }


def test_validate_report_reports_unused_reference():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] Used source. https://example.com/used
[2] Unused source. https://example.com/unused
"""
    )

    assert issue_types(payload) == ["unused_reference"]
    assert payload["issues"][0] == {
        "type": "unused_reference",
        "reference": 2,
        "message": "Reference [2] is not cited in the report body.",
    }


def test_validate_report_reports_invalid_reference_url():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] Bad URL source. ftp://example.com/source
"""
    )

    assert issue_types(payload) == ["invalid_reference_url"]
    assert payload["issues"][0] == {
        "type": "invalid_reference_url",
        "reference": 1,
        "message": "Reference [1] URL must start with http:// or https://.",
    }


def test_validate_report_reports_duplicate_reference_number():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] First source. https://example.com/first
[1] Duplicate source. https://example.com/duplicate
"""
    )

    assert issue_types(payload) == ["duplicate_reference"]
    assert payload["issues"][0] == {
        "type": "duplicate_reference",
        "reference": 1,
        "message": "Reference [1] appears more than once.",
    }


def test_validate_report_validates_duplicate_reference_url():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] First source. https://example.com/first
[1] Duplicate source. ftp://example.com/duplicate
"""
    )

    assert issue_types(payload) == ["invalid_reference_url", "duplicate_reference"]
    assert payload["issues"][0] == {
        "type": "invalid_reference_url",
        "reference": 1,
        "message": "Reference [1] URL must start with http:// or https://.",
    }
    assert payload["issues"][1] == {
        "type": "duplicate_reference",
        "reference": 1,
        "message": "Reference [1] appears more than once.",
    }


def test_validate_report_ignores_citations_inside_references_section():
    payload = validate_report(
        """# Report

The report cites one source [1].

## References

[1] Source title mentioning [2]. https://example.com/source
"""
    )

    assert payload["ok"] is True
    assert payload["citation_count"] == 1
    assert payload["reference_count"] == 1
    assert payload["issues"] == []


def test_main_reads_file_and_writes_json(tmp_path):
    report_path = tmp_path / "report.md"
    report_path.write_text(VALID_REPORT, encoding="utf-8")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([str(report_path)], stdin=io.StringIO(), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is True
    assert payload["issues"] == []


def test_main_reads_stdin_when_path_is_dash():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(["-"], stdin=io.StringIO(VALID_REPORT), stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert json.loads(stdout.getvalue())["ok"] is True


def test_main_returns_one_when_issues_exist():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(
        ["-"],
        stdin=io.StringIO("# Report\n\nMissing refs [1].\n"),
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 1
    payload = json.loads(stdout.getvalue())
    assert payload["ok"] is False
    assert payload["issues"][0]["type"] == "missing_references_section"


def test_main_returns_two_for_missing_file_without_traceback(tmp_path):
    missing_path = tmp_path / "missing.md"
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([str(missing_path)], stdin=io.StringIO(), stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "Failed to read input" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_invalid_utf8_without_traceback(tmp_path):
    report_path = tmp_path / "invalid.md"
    report_path.write_bytes(b"\xff\xfe\xfa")
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([str(report_path)], stdin=io.StringIO(), stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "Failed to read input" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_output_write_error_without_traceback():
    class BadStdout(io.StringIO):
        def write(self, value: str) -> int:
            raise OSError("cannot write")

    stderr = io.StringIO()

    exit_code = main(
        ["-"],
        stdin=io.StringIO(VALID_REPORT),
        stdout=BadStdout(),
        stderr=stderr,
    )

    assert exit_code == 2
    assert "Failed to write output" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()


def test_main_returns_two_for_missing_args_without_traceback():
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main([], stdin=io.StringIO(), stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    assert "usage:" in stderr.getvalue()
    assert "Traceback" not in stderr.getvalue()
