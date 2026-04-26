import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, TextIO

_CITATION_RE = re.compile(r"\[(\d+)\]")
_REFERENCE_LINE_RE = re.compile(r"^\s*\[(\d+)\]\s+\S.*\S\s*$")
_REFERENCE_HEADING_RE = re.compile(
    r"^\s{0,3}(#{2,6})\s*(references|sources)\s*#*\s*$",
    re.IGNORECASE,
)
_ATX_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+.*$")


class _ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, stderr: TextIO, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._stderr = stderr

    def _print_message(self, message: str, file: TextIO | None = None) -> None:
        super()._print_message(message, self._stderr)


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


def main(
    argv: list[str] | None = None,
    *,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    parser = _ArgumentParser(
        description="Validate Markdown report sources.",
        stderr=stderr,
    )
    parser.add_argument("path", help="Markdown file path, or '-' to read stdin.")

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2

    try:
        markdown = _read_input(args.path, stdin)
    except (OSError, UnicodeError) as exc:
        stderr.write(f"Failed to read input: {exc}\n")
        return 2

    payload = validate_report(markdown)
    try:
        json.dump(payload, stdout, indent=2, ensure_ascii=False)
        stdout.write("\n")
    except OSError as exc:
        stderr.write(f"Failed to write output: {exc}\n")
        return 2

    return 0 if payload["ok"] else 1


def _read_input(path: str, stdin: TextIO) -> str:
    if path == "-":
        return stdin.read()

    return Path(path).read_text(encoding="utf-8")


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
        if not (url.startswith("http://") or url.startswith("https://")):
            issues.append(
                {
                    "type": "invalid_reference_url",
                    "reference": number,
                    "message": f"Reference [{number}] URL must start with http:// or https://.",
                }
            )

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

    return references, issues


def _unique_positive_numbers(numbers: list[str]) -> set[int]:
    return {int(number) for number in numbers if int(number) > 0}


if __name__ == "__main__":
    raise SystemExit(main())
