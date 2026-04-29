import argparse
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class SmokeResponse:
    status_code: int
    body: str
    content_type: str


HttpGet = Callable[[str, dict[str, str], float], SmokeResponse]


def run_smoke(
    base_url: str,
    *,
    api_key: str | None = None,
    timeout: float = 5.0,
    http_get: HttpGet | None = None,
) -> dict[str, object]:
    http_get = default_http_get if http_get is None else http_get
    normalized_base_url = base_url.rstrip("/")
    auth_headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    checks = [
        _run_check(
            name="health",
            url=f"{normalized_base_url}/health",
            headers={},
            timeout=timeout,
            http_get=http_get,
            validator=_valid_json_object,
        ),
        _run_check(
            name="dashboard",
            url=f"{normalized_base_url}/dashboard",
            headers={},
            timeout=timeout,
            http_get=http_get,
            validator=lambda response: "InsightGraph" in response.body,
        ),
        _run_check(
            name="jobs_summary",
            url=f"{normalized_base_url}/research/jobs/summary",
            headers=auth_headers,
            timeout=timeout,
            http_get=http_get,
            validator=_valid_json_object,
        ),
    ]

    return {
        "ok": all(check["ok"] for check in checks),
        "base_url": normalized_base_url,
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
    json.dump(result, stdout, indent=2, ensure_ascii=False)
    stdout.write("\n")
    return 0 if result["ok"] else 1


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
    validator: Callable[[SmokeResponse], bool],
) -> dict[str, object]:
    try:
        response = http_get(url, headers, timeout)
    except OSError as exc:
        return {"name": name, "ok": False, "status_code": None, "error": str(exc)}
    except SmokeCheckError as exc:
        return {"name": name, "ok": False, "status_code": None, "error": str(exc)}

    ok = response.status_code == 200 and validator(response)
    check: dict[str, object] = {"name": name, "ok": ok, "status_code": response.status_code}
    if not ok:
        check["error"] = "unexpected response"
    return check


def _valid_json_object(response: SmokeResponse) -> bool:
    try:
        payload = json.loads(response.body)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict)


class SmokeCheckError(RuntimeError):
    pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
