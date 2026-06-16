import base64
import hashlib
import json

from insight_graph.tools.fetch_cache import (
    FetchCacheEntry,
    get_fetch_cache_dir,
    load_cached_fetch,
    store_cached_fetch,
)
from insight_graph.tools.url_canonicalization import canonicalize_url


def test_get_fetch_cache_dir_defaults_to_none(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_FETCH_CACHE_DIR", raising=False)

    assert get_fetch_cache_dir() is None


def test_fetch_cache_round_trips_by_canonical_url_hash(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_FETCH_CACHE_DIR", str(tmp_path))
    entry = FetchCacheEntry(
        url="https://example.com/report.pdf?utm_source=newsletter",
        status_code=200,
        content_type="application/pdf",
        body=b"%PDF cached bytes",
    )

    store_cached_fetch(entry)

    cached = load_cached_fetch("https://example.com/report.pdf")

    assert cached == FetchCacheEntry(
        url="https://example.com/report.pdf?utm_source=newsletter",
        status_code=200,
        content_type="application/pdf",
        body=b"%PDF cached bytes",
    )


def test_fetch_cache_rejects_cached_entry_over_max_bytes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_FETCH_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("INSIGHT_GRAPH_FETCH_CACHE_MAX_BYTES", "4")
    store_cached_fetch(
        FetchCacheEntry(
            url="https://example.com/report.pdf",
            status_code=200,
            content_type="application/pdf",
            body=b"12345",
        )
    )

    assert load_cached_fetch("https://example.com/report.pdf") is None


def test_fetch_cache_rejects_cached_entry_with_disallowed_mime(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_FETCH_CACHE_DIR", str(tmp_path))
    digest = hashlib.sha256(
        canonicalize_url("https://example.com/report.pdf").encode("utf-8")
    ).hexdigest()
    metadata_file = tmp_path / f"{digest}.json"
    metadata_file.write_text(
        json.dumps(
            {
                "url": "https://example.com/report.pdf",
                "status_code": 200,
                "content_type": "application/octet-stream",
                "body": base64.b64encode(b"cached bytes").decode("ascii"),
            }
        ),
        encoding="utf-8",
    )

    assert load_cached_fetch("https://example.com/report.pdf") is None
    assert json.loads(metadata_file.read_text(encoding="utf-8"))["content_type"]
