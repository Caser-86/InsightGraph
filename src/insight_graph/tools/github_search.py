from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from insight_graph.state import Evidence


def github_search(query: str, subtask_id: str = "collect") -> list[Evidence]:
    if os.getenv("INSIGHT_GRAPH_GITHUB_PROVIDER", "mock").lower() == "live":
        return _live_github_search(query, subtask_id)

    return [
        Evidence(
            id="github-opencode-repository",
            subtask_id=subtask_id,
            title="OpenCode Repository",
            source_url="https://github.com/sst/opencode",
            snippet=(
                "The OpenCode repository provides public project information, README "
                "content, and release history for an AI coding tool."
            ),
            source_type="github",
            verified=True,
        ),
        Evidence(
            id="github-copilot-docs-content",
            subtask_id=subtask_id,
            title="GitHub Docs Copilot Content",
            source_url="https://github.com/github/docs/tree/main/content/copilot",
            snippet=(
                "The GitHub Docs repository contains public Copilot documentation content "
                "covering product behavior, integrations, and enterprise guidance."
            ),
            source_type="github",
            verified=True,
        ),
        Evidence(
            id="github-ai-coding-assistant-ecosystem",
            subtask_id=subtask_id,
            title="AI Coding Assistant Ecosystem Repository",
            source_url="https://github.com/safishamsi/graphify",
            snippet=(
                "This GitHub repository describes AI coding assistant tooling across "
                "Claude Code, Codex, OpenCode, Cursor, Gemini CLI, and GitHub Copilot CLI."
            ),
            source_type="github",
            verified=True,
        ),
    ]


def _live_github_search(query: str, subtask_id: str) -> list[Evidence]:
    limit = _parse_github_limit()
    url = (
        "https://api.github.com/search/repositories?"
        f"q={quote_plus(query)}&per_page={limit}"
    )
    headers = _github_headers()
    try:
        payload = fetch_github_json(url, headers, timeout=10.0)
    except Exception:
        return []

    if not isinstance(payload, dict):
        return []
    items = payload.get("items")
    if not isinstance(items, list):
        return []

    evidence: list[Evidence] = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue
        parsed = _repository_to_evidence(item, subtask_id)
        if parsed is not None:
            evidence.append(parsed)
    return evidence


def fetch_github_json(
    url: str,
    headers: dict[str, str],
    timeout: float,
) -> dict[str, Any]:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if status_code < 200 or status_code >= 300:
                raise RuntimeError(f"Unexpected GitHub API status: {status_code}")
            body = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error while fetching GitHub API: {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while fetching GitHub API: {exc.reason}") from exc

    return json.loads(body.decode("utf-8"))


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "InsightGraph/0.1",
    }
    token = os.getenv("INSIGHT_GRAPH_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _parse_github_limit() -> int:
    raw = os.getenv("INSIGHT_GRAPH_GITHUB_LIMIT", "3")
    try:
        value = int(raw)
    except ValueError:
        return 3
    return min(max(value, 1), 10)


def _repository_to_evidence(
    item: dict[str, Any],
    subtask_id: str,
) -> Evidence | None:
    full_name = item.get("full_name")
    html_url = item.get("html_url")
    if not isinstance(full_name, str) or not full_name:
        return None
    if not isinstance(html_url, str) or not html_url.startswith("https://github.com/"):
        return None

    return Evidence(
        id=f"github-{_slugify(full_name)}",
        subtask_id=subtask_id,
        title=full_name,
        source_url=html_url,
        snippet=_repository_snippet(item),
        source_type="github",
        verified=True,
    )


def _repository_snippet(item: dict[str, Any]) -> str:
    description = item.get("description")
    parts = [description if isinstance(description, str) and description else "No description."]

    stars = item.get("stargazers_count")
    if isinstance(stars, int):
        parts.append(f"Stars: {stars}.")

    language = item.get("language")
    if isinstance(language, str) and language:
        parts.append(f"Language: {language}.")

    updated_at = item.get("updated_at")
    if isinstance(updated_at, str) and updated_at:
        parts.append(f"Updated: {updated_at}.")

    return " ".join(parts)


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "repository"
