#!/usr/bin/env python
"""搜索提供商连通性检查脚本。

支持 --provider duckduckgo/serpapi/google/mock，输出 provider/result_count/first_url。
SerpAPI 未配置 key 时输出明确错误。
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

# 加载 .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def check_duckduckgo(query: str, limit: int) -> dict[str, object]:
    try:
        from ddgs import DDGS

        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=limit):
                results.append(r)
        return {
            "provider": "duckduckgo",
            "status": "PASS",
            "result_count": len(results),
            "first_url": results[0].get("href", "") if results else "",
            "error": None,
        }
    except Exception as exc:
        return {
            "provider": "duckduckgo",
            "status": "FAIL",
            "result_count": 0,
            "first_url": "",
            "error": str(exc)[:200],
        }


def check_serpapi(query: str, limit: int) -> dict[str, object]:
    api_key = (
        env("INSIGHT_GRAPH_SERPAPI_KEY")
        or env("INSIGHT_GRAPH_SERPAPI_API_KEY")
        or env("SERPAPI_API_KEY")
    )
    if not api_key:
        return {
            "provider": "serpapi",
            "status": "FAIL",
            "result_count": 0,
            "first_url": "",
            "error": "SerpAPI key not configured",
        }
    try:
        import urllib.request

        params = {
            "engine": "google",
            "q": query,
            "num": str(limit),
            "api_key": api_key,
        }
        url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"
        start = time.monotonic()
        resp = urllib.request.urlopen(url, timeout=10)
        duration_ms = int((time.monotonic() - start) * 1000)
        body = json.loads(resp.read().decode("utf-8"))
        results = body.get("organic_results", [])
        return {
            "provider": "serpapi",
            "status": "PASS",
            "result_count": len(results),
            "first_url": results[0].get("link", "") if results else "",
            "duration_ms": duration_ms,
            "error": None,
        }
    except Exception as exc:
        error_msg = str(exc)[:200]
        if "401" in error_msg or "403" in error_msg or "Invalid API key" in error_msg:
            error_msg = "API key invalid or unauthorized (key masked for security)"
        return {
            "provider": "serpapi",
            "status": "FAIL",
            "result_count": 0,
            "first_url": "",
            "error": error_msg,
        }


def check_google(query: str, limit: int) -> dict[str, object]:
    api_key = env("INSIGHT_GRAPH_GOOGLE_API_KEY")
    cse_id = env("INSIGHT_GRAPH_GOOGLE_CSE_ID")
    if not api_key or not cse_id:
        return {
            "provider": "google",
            "status": "FAIL",
            "result_count": 0,
            "first_url": "",
            "error": "GOOGLE_API_KEY or GOOGLE_CSE_ID not configured",
        }
    try:
        import urllib.request

        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": str(limit),
        }
        url = (
            "https://www.googleapis.com/customsearch/v1?"
            + urllib.parse.urlencode(params)
        )
        start = time.monotonic()
        resp = urllib.request.urlopen(url, timeout=10)
        duration_ms = int((time.monotonic() - start) * 1000)
        body = json.loads(resp.read().decode("utf-8"))
        results = body.get("items", [])
        return {
            "provider": "google",
            "status": "PASS",
            "result_count": len(results),
            "first_url": results[0].get("link", "") if results else "",
            "duration_ms": duration_ms,
            "error": None,
        }
    except Exception as exc:
        return {
            "provider": "google",
            "status": "FAIL",
            "result_count": 0,
            "first_url": "",
            "error": str(exc)[:200],
        }


def check_mock(query: str, limit: int) -> dict[str, object]:
    return {
        "provider": "mock",
        "status": "PASS",
        "result_count": 1,
        "first_url": f"https://mock.example.com/search?q={query}",
        "error": None,
    }


PROVIDERS = {
    "duckduckgo": check_duckduckgo,
    "serpapi": check_serpapi,
    "google": check_google,
    "mock": check_mock,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Check search provider connectivity")
    parser.add_argument("--provider", default="duckduckgo", choices=list(PROVIDERS))
    parser.add_argument("--query", default="InsightGraph test")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()

    check_fn = PROVIDERS[args.provider]
    result = check_fn(args.query, args.limit)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
