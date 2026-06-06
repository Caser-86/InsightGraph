#!/usr/bin/env python
"""LLM 连通性检查脚本。

对 fast/default/strong 三档模型分别发送最小 JSON completion 请求，
验证返回内容为合法 JSON，输出 stage/model/wire_api/duration_ms。
不打印 API key。
"""

from __future__ import annotations

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


def check_model(label: str, model: str) -> dict[str, object]:
    if not model:
        return {"label": label, "status": "SKIP", "model": "", "error": "model not configured"}

    base_url = env("INSIGHT_GRAPH_LLM_BASE_URL")
    api_key = env("INSIGHT_GRAPH_LLM_API_KEY")

    if not base_url or not api_key:
        return {
            "label": label,
            "status": "FAIL",
            "model": model,
            "error": "base_url or api_key missing",
        }

    try:
        import urllib.request

        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": 'Say exactly {"status":"ok"}'}],
            "max_tokens": 50,
            "temperature": 0,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        start = time.monotonic()
        resp = urllib.request.urlopen(req, timeout=30)
        duration_ms = int((time.monotonic() - start) * 1000)
        body = json.loads(resp.read().decode("utf-8"))

        content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        is_json = False
        try:
            json.loads(content)
            is_json = True
        except (json.JSONDecodeError, TypeError):
            pass

        return {
            "label": label,
            "status": "PASS" if is_json else f"non-json: {content[:80]}",
            "model": model,
            "wire_api": "chat_completions",
            "duration_ms": duration_ms,
            "usage": body.get("usage"),
        }

    except Exception as exc:
        return {"label": label, "status": "FAIL", "model": model, "error": str(exc)[:200]}


def main() -> int:
    results = [
        check_model("fast", env("INSIGHT_GRAPH_LLM_MODEL_FAST")),
        check_model(
            "default",
            env("INSIGHT_GRAPH_LLM_MODEL_DEFAULT") or env("INSIGHT_GRAPH_LLM_MODEL"),
        ),
        check_model("strong", env("INSIGHT_GRAPH_LLM_MODEL_STRONG")),
    ]

    output = {"check": "llm_provider", "results": results}
    print(json.dumps(output, ensure_ascii=False, indent=2))

    fail_count = sum(1 for r in results if r["status"] == "FAIL")
    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
