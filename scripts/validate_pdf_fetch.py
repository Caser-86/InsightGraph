from __future__ import annotations


def run_validation() -> dict:
    return {"cases": [], "summary": {}}


def format_markdown(payload: dict) -> str:
    del payload
    return ""


def main(argv: list[str] | None = None, *, stdout=None, stderr=None) -> int:
    del argv, stdout, stderr
    return 0
