import re
from typing import Any


_CITATION_RE = re.compile(r"\[(\d+)\]")
_REFERENCE_LINE_RE = re.compile(r"^\s*\[(\d+)\]\s+\S.*\S\s*$")
_REFERENCE_HEADING_RE = re.compile(
    r"^\s{0,3}(#{2,6})\s*(references|sources)\s*#*\s*$",
    re.IGNORECASE,
)
_ATX_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+.*$")


def validate_report(markdown: str) -> dict[str, Any]:
    section = _find_references_section(markdown)
    if section is None:
        citations = _unique_positive_numbers(_CITATION_RE.findall(markdown))
        return {
            "ok": False,
            "citation_count": len(citations),
            "reference_count": 0,
            "issues": [
                {
                    "type": "missing_references_section",
                    "reference": None,
                    "message": "Report has no References or Sources section.",
                }
            ],
        }

    heading_index, end_index = section
    lines = markdown.splitlines()
    body_lines = lines[:heading_index] + lines[end_index:]
    citations = _unique_positive_numbers(_CITATION_RE.findall("\n".join(body_lines)))

    references, issues = _parse_references(lines[heading_index + 1 : end_index])
    reference_numbers = set(references)

    for citation in sorted(citations - reference_numbers):
        issues.append(
            {
                "type": "missing_reference",
                "reference": citation,
                "message": f"Citation [{citation}] has no matching reference.",
            }
        )

    for reference in sorted(reference_numbers - citations):
        issues.append(
            {
                "type": "unused_reference",
                "reference": reference,
                "message": f"Reference [{reference}] is not cited in the report body.",
            }
        )

    return {
        "ok": not issues,
        "citation_count": len(citations),
        "reference_count": len(reference_numbers),
        "issues": issues,
    }


def _find_references_section(markdown: str) -> tuple[int, int] | None:
    lines = markdown.splitlines()

    for index, line in enumerate(lines):
        match = _REFERENCE_HEADING_RE.match(line)
        if match is None:
            continue

        level = len(match.group(1))
        end_index = len(lines)
        for next_index in range(index + 1, len(lines)):
            heading_match = _ATX_HEADING_RE.match(lines[next_index])
            if heading_match is not None and len(heading_match.group(1)) <= level:
                end_index = next_index
                break
        return index, end_index

    return None


def _parse_references(lines: list[str]) -> tuple[dict[int, str], list[dict[str, Any]]]:
    references: dict[int, str] = {}
    issues: list[dict[str, Any]] = []
    duplicates: set[int] = set()

    for line in lines:
        match = _REFERENCE_LINE_RE.match(line)
        if match is None:
            continue

        number = int(match.group(1))
        if number <= 0:
            continue

        url = line.strip().split()[-1]
        if number in references:
            if number not in duplicates:
                issues.append(
                    {
                        "type": "duplicate_reference",
                        "reference": number,
                        "message": f"Reference [{number}] appears more than once.",
                    }
                )
                duplicates.add(number)
            continue

        references[number] = url
        if not (url.startswith("http://") or url.startswith("https://")):
            issues.append(
                {
                    "type": "invalid_reference_url",
                    "reference": number,
                    "message": f"Reference [{number}] URL must start with http:// or https://.",
                }
            )

    return references, issues


def _unique_positive_numbers(numbers: list[str]) -> set[int]:
    return {int(number) for number in numbers if int(number) > 0}
