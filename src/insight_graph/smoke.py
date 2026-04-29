import argparse
import json
import os
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeResponse:
    status_code: int
    body: str
    content_type: str


HttpGet = Callable[[str, dict[str, str], float], SmokeResponse]
Now = Callable[[], str]
Monotonic = Callable[[], float]


def run_smoke(
    base_url: str,
    *,
    api_key: str | None = None,
    timeout: float = 5.0,
    http_get: HttpGet | None = None,
    now: Now | None = None,
    monotonic: Monotonic | None = None,
) -> dict[str, object]:
    http_get = default_http_get if http_get is None else http_get
    now = utc_now if now is None else now
    monotonic = time.monotonic if monotonic is None else monotonic
    normalized_base_url = base_url.rstrip("/")
    auth_headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    created_at = now()
    started_at = monotonic()

    checks = [
        _run_check(
            name="health",
            url=f"{normalized_base_url}/health",
            headers={},
            timeout=timeout,
            http_get=http_get,
            monotonic=monotonic,
            validator=_valid_json_object,
        ),
        _run_check(
            name="dashboard",
            url=f"{normalized_base_url}/dashboard",
            headers={},
            timeout=timeout,
            http_get=http_get,
            monotonic=monotonic,
            validator=lambda response: "InsightGraph" in response.body,
        ),
        _run_check(
            name="jobs_summary",
            url=f"{normalized_base_url}/research/jobs/summary",
            headers=auth_headers,
            timeout=timeout,
            http_get=http_get,
            monotonic=monotonic,
            validator=_valid_json_object,
        ),
    ]
    finished_at = monotonic()

    return {
        "ok": all(check["ok"] for check in checks),
        "base_url": normalized_base_url,
        "created_at": created_at,
        "duration_ms": _duration_ms(started_at, finished_at),
        "checks": checks,
    }


def main(
    argv: list[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    http_get: HttpGet | None = None,
) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr

    parser = argparse.ArgumentParser(description="Smoke test an InsightGraph API deployment.")
    parser.add_argument("base_url", help="Deployment base URL, for example https://host.example.com")
    parser.add_argument("--api-key", help="Shared API key for protected research endpoints.")
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="Per-request timeout in seconds. Defaults to 5.",
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Write a GitHub-flavored Markdown summary instead of JSON.",
    )
    parser.add_argument(
        "--output",
        help="Write the smoke report to this file instead of stdout.",
    )
    args = parser.parse_args(argv)

    if args.timeout <= 0:
        stderr.write("--timeout must be greater than zero\n")
        return 2

    api_key = args.api_key or os.environ.get("INSIGHT_GRAPH_API_KEY")

    result = run_smoke(
        args.base_url,
        api_key=api_key,
        timeout=args.timeout,
        http_get=http_get,
    )
    output = format_markdown(result) if args.markdown else format_json(result)
    if args.output:
        try:
            Path(args.output).write_text(output, encoding="utf-8")
        except OSError as exc:
            stderr.write(f"Failed to write smoke report: {exc}\n")
            return 2
    else:
        stdout.write(output)
    return 0 if result["ok"] else 1


def format_json(result: dict[str, object]) -> str:
    return json.dumps(result, indent=2, ensure_ascii=False) + "\n"


def format_markdown(result: dict[str, object]) -> str:
    checks = result.get("checks")
    if not isinstance(checks, list):
        checks = []

    lines = [
        "# Deployment Smoke Test",
        "",
        f"Base URL: `{result.get('base_url', '')}`",
        f"Created at: `{result.get('created_at', '')}`",
        f"Duration ms: `{result.get('duration_ms', '')}`",
        f"Overall: {'PASS' if result.get('ok') else 'FAIL'}",
        "",
        "| Check | Status | HTTP | Duration ms |",
        "| --- | --- | ---: | ---: |",
    ]
    for check in checks:
        if not isinstance(check, dict):
            continue
        name = _markdown_cell(str(check.get("name", "")))
        status = "PASS" if check.get("ok") else "FAIL"
        status_code = "" if check.get("status_code") is None else str(check.get("status_code"))
        duration_ms = "" if check.get("duration_ms") is None else str(check.get("duration_ms"))
        lines.append(f"| {name} | {status} | {status_code} | {duration_ms} |")
    return "\n".join(lines) + "\n"


def _markdown_cell(value: str) -> str:
    return " ".join(value.splitlines()).replace("|", r"\|")


def default_http_get(url: str, headers: dict[str, str], timeout: float) -> SmokeResponse:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return SmokeResponse(
                status_code=response.status,
                body=body,
                content_type=response.headers.get("Content-Type", ""),
            )
    except HTTPError as exc:
        return SmokeResponse(
            status_code=exc.code,
            body=exc.read().decode("utf-8", errors="replace"),
            content_type=exc.headers.get("Content-Type", ""),
        )
    except URLError as exc:
        raise SmokeCheckError(str(exc.reason)) from exc


def _run_check(
    *,
    name: str,
    url: str,
    headers: dict[str, str],
    timeout: float,
    http_get: HttpGet,
    monotonic: Monotonic,
    validator: Callable[[SmokeResponse], bool],
) -> dict[str, object]:
    started_at = monotonic()
    try:
        response = http_get(url, headers, timeout)
    except OSError as exc:
        return {
            "name": name,
            "ok": False,
            "status_code": None,
            "duration_ms": _duration_ms(started_at, monotonic()),
            "error": str(exc),
        }
    except SmokeCheckError as exc:
        return {
            "name": name,
            "ok": False,
            "status_code": None,
            "duration_ms": _duration_ms(started_at, monotonic()),
            "error": str(exc),
        }

    finished_at = monotonic()
    ok = response.status_code == 200 and validator(response)
    check: dict[str, object] = {
        "name": name,
        "ok": ok,
        "status_code": response.status_code,
        "duration_ms": _duration_ms(started_at, finished_at),
    }
    if not ok:
        check["error"] = "unexpected response"
    return check


def _valid_json_object(response: SmokeResponse) -> bool:
    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict)


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _duration_ms(started_at: float, finished_at: float) -> int:
    return max(0, round((finished_at - started_at) * 1000))


class SmokeCheckError(RuntimeError):
    pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
