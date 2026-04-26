from scripts.validate_sources import validate_report


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
