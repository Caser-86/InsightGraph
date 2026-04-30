from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from insight_graph.tools.http_client import ALLOWED_CONTENT_TYPES, DEFAULT_MAX_RESPONSE_BYTES
from insight_graph.tools.url_canonicalization import canonicalize_url


@dataclass(frozen=True)
class FetchCacheEntry:
    url: str
    status_code: int
    content_type: str
    body: bytes


def get_fetch_cache_dir() -> Path | None:
    value = os.environ.get("INSIGHT_GRAPH_FETCH_CACHE_DIR", "").strip()
    return Path(value) if value else None


def load_cached_fetch(url: str) -> FetchCacheEntry | None:
    path = _cache_path(url)
    if path is None:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    entry = _entry_from_json(payload)
    if entry is None or not _entry_is_allowed(entry):
        return None
    return entry


def store_cached_fetch(entry: FetchCacheEntry) -> None:
    if not _entry_is_allowed(entry):
        return
    path = _cache_path(entry.url)
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_entry_to_json(entry), sort_keys=True), encoding="utf-8")


def _cache_path(url: str) -> Path | None:
    cache_dir = get_fetch_cache_dir()
    if cache_dir is None:
        return None
    digest = hashlib.sha256(canonicalize_url(url).encode("utf-8")).hexdigest()
    return cache_dir / f"{digest}.json"


def _entry_is_allowed(entry: FetchCacheEntry) -> bool:
    media_type = entry.content_type.split(";", maxsplit=1)[0].strip().lower()
    if media_type and media_type not in ALLOWED_CONTENT_TYPES and not media_type.endswith("+xml"):
        return False
    return len(entry.body) <= _max_cache_bytes()


def _max_cache_bytes() -> int:
    value = os.environ.get("INSIGHT_GRAPH_FETCH_CACHE_MAX_BYTES", "").strip()
    if not value:
        return DEFAULT_MAX_RESPONSE_BYTES
    try:
        max_bytes = int(value)
    except ValueError:
        return DEFAULT_MAX_RESPONSE_BYTES
    return max_bytes if max_bytes >= 0 else DEFAULT_MAX_RESPONSE_BYTES


def _entry_to_json(entry: FetchCacheEntry) -> dict[str, object]:
    return {
        "url": entry.url,
        "status_code": entry.status_code,
        "content_type": entry.content_type,
        "body": base64.b64encode(entry.body).decode("ascii"),
    }


def _entry_from_json(payload: object) -> FetchCacheEntry | None:
    if not isinstance(payload, dict):
        return None
    url = payload.get("url")
    status_code = payload.get("status_code")
    content_type = payload.get("content_type")
    body = payload.get("body")
    if not isinstance(url, str):
        return None
    if not isinstance(status_code, int) or isinstance(status_code, bool):
        return None
    if not isinstance(content_type, str):
        return None
    if not isinstance(body, str):
        return None
    try:
        decoded_body = base64.b64decode(body.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError):
        return None
    return FetchCacheEntry(
        url=url,
        status_code=status_code,
        content_type=content_type,
        body=decoded_body,
    )
