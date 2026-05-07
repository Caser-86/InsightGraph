import os
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse

from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    source: str = "mock"
    published_at: str | None = None


class SearchProvider(Protocol):
    def search(self, query: str, limit: int) -> list[SearchResult]: ...


class MockSearchProvider:
    def search(self, query: str, limit: int) -> list[SearchResult]:
        return _mock_results()[:limit]


class DuckDuckGoSearchProvider:
    def __init__(self, client_factory: Callable[..., Any] | None = None) -> None:
        self._client_factory = client_factory or _create_duckduckgo_client
        self._proxy = os.getenv("INSIGHT_GRAPH_SEARCH_PROXY") or os.getenv("DDGS_PROXY")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        effective_limit = _effective_provider_limit("duckduckgo", limit)
        if effective_limit <= 0:
            return []
        if not _consume_provider_daily_call("duckduckgo"):
            return []
        try:
            client = self._client_factory(proxy=self._proxy)
        except TypeError:
            try:
                client = self._client_factory()
            except Exception:
                return []
        try:
            raw_results = _run_text_search(client, query, effective_limit)
            return _apply_result_quality_filters(_map_duckduckgo_results(raw_results))
        except Exception:
            return []


class DuckDuckGoNewsSearchProvider(DuckDuckGoSearchProvider):
    def search(self, query: str, limit: int) -> list[SearchResult]:
        effective_limit = _effective_provider_limit("duckduckgo", limit)
        if effective_limit <= 0:
            return []
        if not _consume_provider_daily_call("duckduckgo"):
            return []
        try:
            client = self._client_factory(proxy=self._proxy)
        except TypeError:
            try:
                client = self._client_factory()
            except Exception:
                return []
        try:
            raw_results = _run_news_search(client, query, effective_limit)
            return _apply_result_quality_filters(
                _map_duckduckgo_results(raw_results, source="duckduckgo_news"),
                news_mode=True,
            )
        except Exception:
            return []


class GoogleSearchProvider:
    def __init__(self) -> None:
        self._api_key = os.getenv("INSIGHT_GRAPH_GOOGLE_API_KEY")
        self._cse_id = os.getenv("INSIGHT_GRAPH_GOOGLE_CSE_ID")

    def search(self, query: str, limit: int) -> list[SearchResult]:
        effective_limit = _effective_provider_limit("google", limit)
        if effective_limit <= 0:
            return []
        if not self._api_key or not self._cse_id:
            return []
        try:
            return _apply_result_quality_filters(
                _call_google_search(query, effective_limit, self._api_key, self._cse_id)
            )
        except Exception:
            return []


class SerpAPISearchProvider:
    def __init__(self) -> None:
        self._api_key = (
            os.getenv("INSIGHT_GRAPH_SERPAPI_KEY")
            or os.getenv("INSIGHT_GRAPH_SERPAPI_API_KEY")
            or os.getenv("SERPAPI_API_KEY")
        )

    def search(self, query: str, limit: int) -> list[SearchResult]:
        effective_limit = _effective_provider_limit("serpapi", limit)
        if effective_limit <= 0:
            return []
        if not _consume_provider_daily_call("serpapi"):
            return []
        if not self._api_key:
            return []
        try:
            return _apply_result_quality_filters(
                _call_serpapi_search(query, effective_limit, self._api_key)
            )
        except Exception:
            return []


class SerpAPINewsSearchProvider(SerpAPISearchProvider):
    def search(self, query: str, limit: int) -> list[SearchResult]:
        effective_limit = _effective_provider_limit("serpapi", limit)
        if effective_limit <= 0:
            return []
        if not _consume_provider_daily_call("serpapi"):
            return []
        if not self._api_key:
            return []
        try:
            return _apply_result_quality_filters(
                _call_serpapi_news_search(query, effective_limit, self._api_key),
                news_mode=True,
            )
        except Exception:
            return []


_VALID_PROVIDER_NAMES = ("mock", "duckduckgo", "google", "serpapi")
_PROVIDER_DAILY_CALL_USAGE: dict[str, int] = {}


def get_search_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")).lower()
    if provider_name == "mock":
        return MockSearchProvider()
    if provider_name == "duckduckgo":
        return DuckDuckGoSearchProvider()
    if provider_name == "google":
        return GoogleSearchProvider()
    if provider_name == "serpapi":
        return SerpAPISearchProvider()
    raise ValueError(f"Unknown search provider: {provider_name}")


def get_news_search_provider(name: str | None = None) -> SearchProvider:
    provider_name = (name or os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")).lower()
    if provider_name == "mock":
        return MockSearchProvider()
    if provider_name == "duckduckgo":
        return DuckDuckGoNewsSearchProvider()
    if provider_name == "google":
        return GoogleSearchProvider()
    if provider_name == "serpapi":
        return SerpAPINewsSearchProvider()
    raise ValueError(f"Unknown search provider: {provider_name}")


def resolve_search_providers(raw: str | None = None) -> list[str]:
    expression = raw
    if expression is None:
        expression = os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDERS")
    if expression is None or not expression.strip():
        expression = os.getenv("INSIGHT_GRAPH_SEARCH_PROVIDER", "mock")
    expression = expression.strip().lower()
    if expression == "all":
        return ["duckduckgo", "serpapi", "google"]
    names: list[str] = []
    seen: set[str] = set()
    for part in expression.split(","):
        name = part.strip()
        if not name:
            continue
        if name not in _VALID_PROVIDER_NAMES:
            raise ValueError(f"Unknown search provider: {name}")
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names or ["mock"]


def search_with_providers(
    query: str,
    limit: int,
    provider_expression: str | None = None,
) -> list[SearchResult]:
    provider_names = resolve_search_providers(provider_expression)
    buckets = [
        _apply_result_quality_filters(get_search_provider(name).search(query, limit))
        for name in provider_names
    ]
    max_len = max((len(bucket) for bucket in buckets), default=0)
    merged: list[SearchResult] = []
    seen_urls: set[str] = set()
    for rank in range(max_len):
        for bucket in buckets:
            if rank >= len(bucket):
                continue
            result = bucket[rank]
            key = result.url.strip().lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            merged.append(result)
            if len(merged) >= limit:
                return merged
    return merged


def search_news_with_providers(
    query: str,
    limit: int,
    provider_expression: str | None = None,
) -> list[SearchResult]:
    provider_names = resolve_search_providers(provider_expression)
    buckets = [
        _apply_result_quality_filters(
            get_news_search_provider(name).search(query, limit),
            news_mode=True,
        )
        for name in provider_names
    ]
    return _merge_provider_buckets(buckets, limit)


def get_search_quota_snapshot() -> dict[str, object]:
    today = _today_utc_key()
    return {
        "date_utc": today,
        "serpapi": _provider_quota_status("serpapi"),
        "duckduckgo": _provider_quota_status("duckduckgo"),
    }


def parse_search_limit(default: int = 3) -> int:
    raw_limit = os.getenv("INSIGHT_GRAPH_SEARCH_LIMIT")
    if raw_limit is None:
        return default
    try:
        limit = int(raw_limit)
    except ValueError:
        return default
    if limit <= 0:
        return default
    return limit


def _create_duckduckgo_client(proxy: str | None = None) -> Any:
    from ddgs import DDGS

    effective_proxy = proxy or os.getenv("INSIGHT_GRAPH_SEARCH_PROXY") or os.getenv("DDGS_PROXY")
    kwargs = {"proxy": effective_proxy} if effective_proxy else {}
    return DDGS(**kwargs)


def _run_text_search(client: Any, query: str, limit: int) -> Iterable[dict[str, Any]]:
    timelimit = os.getenv("INSIGHT_GRAPH_DDG_TIMELIMIT")
    if hasattr(client, "__enter__"):
        with client as active_client:
            kwargs = {"max_results": limit}
            if timelimit:
                kwargs["timelimit"] = timelimit
            return active_client.text(query, **kwargs)
    kwargs = {"max_results": limit}
    if timelimit:
        kwargs["timelimit"] = timelimit
    return client.text(query, **kwargs)


def _run_news_search(client: Any, query: str, limit: int) -> Iterable[dict[str, Any]]:
    timelimit = os.getenv("INSIGHT_GRAPH_DDG_TIMELIMIT")
    if hasattr(client, "__enter__"):
        with client as active_client:
            kwargs = {"max_results": limit}
            if timelimit:
                kwargs["timelimit"] = timelimit
            return active_client.news(query, **kwargs)
    kwargs = {"max_results": limit}
    if timelimit:
        kwargs["timelimit"] = timelimit
    return client.news(query, **kwargs)


def _map_duckduckgo_results(
    raw_results: Iterable[dict[str, Any]],
    *,
    source: str = "duckduckgo",
) -> list[SearchResult]:
    results: list[SearchResult] = []
    for raw in raw_results:
        url = raw.get("href") or raw.get("url") or raw.get("link")
        if not url:
            continue
        results.append(
            SearchResult(
                title=raw.get("title") or url,
                url=url,
                snippet=raw.get("body") or raw.get("snippet") or "",
                source=source,
                published_at=raw.get("date") or raw.get("published") or raw.get("published_at"),
            )
        )
    return results


def _merge_provider_buckets(buckets: list[list[SearchResult]], limit: int) -> list[SearchResult]:
    max_len = max((len(bucket) for bucket in buckets), default=0)
    merged: list[SearchResult] = []
    seen_urls: set[str] = set()
    for rank in range(max_len):
        for bucket in buckets:
            if rank >= len(bucket):
                continue
            result = bucket[rank]
            key = result.url.strip().lower()
            if key in seen_urls:
                continue
            seen_urls.add(key)
            merged.append(result)
            if len(merged) >= limit:
                return merged
    return merged


def _mock_results() -> list[SearchResult]:
    return [
        SearchResult(
            title="Cursor Pricing",
            url="https://cursor.com/pricing",
            snippet="Cursor pricing information for AI coding plans.",
        ),
        SearchResult(
            title="GitHub Copilot Documentation",
            url="https://docs.github.com/copilot",
            snippet="GitHub Copilot documentation and feature guides.",
        ),
        SearchResult(
            title="opencode GitHub Repository",
            url="https://github.com/sst/opencode",
            snippet="Open source agentic coding tool repository.",
        ),
    ]


def _call_google_search(
    query: str, limit: int, api_key: str, cse_id: str
) -> list[SearchResult]:
    import json
    import urllib.parse
    import urllib.request

    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "num": min(limit, 10),
    }
    url = f"https://www.googleapis.com/customsearch/v1?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    items = data.get("items", [])
    results: list[SearchResult] = []
    for item in items:
        link = item.get("link")
        if not link:
            continue
        results.append(
            SearchResult(
                title=item.get("title", link),
                url=link,
                snippet=item.get("snippet", ""),
                source="google",
                published_at=(item.get("pagemap", {}) or {}).get("metatags", [{}])[0].get(
                    "article:published_time"
                )
                if isinstance(item.get("pagemap"), dict)
                else None,
            )
        )
    return results


def _call_serpapi_search(query: str, limit: int, api_key: str) -> list[SearchResult]:
    import json
    import urllib.parse
    import urllib.request

    params = {
        "api_key": api_key,
        "q": query,
        "engine": os.getenv("INSIGHT_GRAPH_SERPAPI_ENGINE", "google"),
        "num": min(limit, 10),
    }
    min_year = _search_min_year()
    if min_year is not None:
        params["as_ylo"] = min_year
    url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    organic_results = data.get("organic_results", [])
    results: list[SearchResult] = []
    for item in organic_results:
        link = item.get("link")
        if not link:
            continue
        results.append(
            SearchResult(
                title=item.get("title", link),
                url=link,
                snippet=item.get("snippet", ""),
                source="serpapi",
                published_at=item.get("date"),
            )
        )
    return results


def _call_serpapi_news_search(query: str, limit: int, api_key: str) -> list[SearchResult]:
    import json
    import urllib.parse
    import urllib.request

    params = {
        "api_key": api_key,
        "q": query,
        "engine": os.getenv("INSIGHT_GRAPH_SERPAPI_NEWS_ENGINE", "google_news"),
        "num": min(limit, 10),
    }
    min_year = _search_min_year()
    if min_year is not None:
        params["as_ylo"] = min_year
    url = f"https://serpapi.com/search?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as response:
        data = json.loads(response.read().decode("utf-8"))

    items = data.get("news_results") or data.get("organic_results", [])
    results: list[SearchResult] = []
    for item in items:
        link = item.get("link")
        if not link:
            continue
        results.append(
            SearchResult(
                title=item.get("title", link),
                url=link,
                snippet=item.get("snippet") or item.get("source", {}).get("name", ""),
                source="serpapi_news",
                published_at=item.get("date"),
            )
        )
    return results


def _apply_result_quality_filters(
    results: list[SearchResult],
    *,
    news_mode: bool = False,
) -> list[SearchResult]:
    filtered = _filter_by_domain_policy(results)
    filtered = _filter_by_recency_policy(filtered, news_mode=news_mode)
    return filtered


def _filter_by_domain_policy(results: list[SearchResult]) -> list[SearchResult]:
    allowlist = _domain_policy_env("INSIGHT_GRAPH_SOURCE_DOMAIN_ALLOWLIST")
    blocklist = _domain_policy_env("INSIGHT_GRAPH_SOURCE_DOMAIN_BLOCKLIST")
    if not allowlist and not blocklist:
        return results

    kept: list[SearchResult] = []
    for item in results:
        host = _normalize_domain_host(item.url)
        if not host:
            continue
        if blocklist and _host_matches_any(host, blocklist):
            continue
        if allowlist and not _host_matches_any(host, allowlist):
            continue
        kept.append(item)
    return kept


def _filter_by_recency_policy(
    results: list[SearchResult],
    *,
    news_mode: bool = False,
) -> list[SearchResult]:
    min_year = _search_min_year()
    if min_year is None:
        return results
    strict = _truthy_env("INSIGHT_GRAPH_SEARCH_RECENCY_STRICT")

    kept: list[SearchResult] = []
    for item in results:
        year = _extract_latest_year(item)
        if year is None:
            if strict:
                continue
            kept.append(item)
            continue
        if year >= min_year:
            kept.append(item)
    return kept


def _extract_latest_year(result: SearchResult) -> int | None:
    haystack = " ".join(
        [
            result.title,
            result.snippet,
            result.url,
            result.published_at or "",
        ]
    )
    years = [int(match) for match in re.findall(r"\b(19\d{2}|20\d{2})\b", haystack)]
    if not years:
        return None
    return max(years)


def _search_min_year() -> int | None:
    raw = os.getenv("INSIGHT_GRAPH_SEARCH_MIN_YEAR")
    if raw is None or not raw.strip():
        return datetime.now(UTC).year - 2
    try:
        year = int(raw)
    except ValueError:
        return datetime.now(UTC).year - 2
    return year if 1900 <= year <= 2100 else datetime.now(UTC).year - 2


def _domain_policy_env(name: str) -> set[str]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return set()
    return {host for host in (_normalize_domain_host(item) for item in raw.split(",")) if host}


def _normalize_domain_host(value: str) -> str:
    raw = value.strip().lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    host = parsed.netloc or parsed.path.split("/", maxsplit=1)[0]
    host = host.split("@", maxsplit=1)[-1].split(":", maxsplit=1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _host_matches_any(host: str, patterns: set[str]) -> bool:
    return any(host == pattern or host.endswith(f".{pattern}") for pattern in patterns)


def _provider_quota_status(provider: str) -> dict[str, object]:
    daily_limit = _provider_daily_call_limit(provider)
    used = _PROVIDER_DAILY_CALL_USAGE.get(_provider_usage_key(provider), 0)
    remaining = None if daily_limit is None else max(daily_limit - used, 0)
    alert_threshold = _provider_alert_threshold(provider)
    alert_trigger = None
    if daily_limit and daily_limit > 0:
        alert_trigger = int(daily_limit * alert_threshold)
    return {
        "daily_call_limit": daily_limit,
        "daily_calls_used": used,
        "daily_calls_remaining": remaining,
        "alert_threshold_ratio": alert_threshold,
        "alert_trigger_calls": alert_trigger,
        "alert_reached": bool(alert_trigger is not None and used >= alert_trigger),
    }


def _consume_provider_daily_call(provider: str) -> bool:
    daily_limit = _provider_daily_call_limit(provider)
    usage_key = _provider_usage_key(provider)
    used = _PROVIDER_DAILY_CALL_USAGE.get(usage_key, 0)
    if daily_limit is not None and used >= daily_limit:
        return False
    _PROVIDER_DAILY_CALL_USAGE[usage_key] = used + 1
    return True


def _provider_usage_key(provider: str) -> str:
    return f"{provider}:{_today_utc_key()}"


def _today_utc_key() -> str:
    return datetime.now(UTC).date().isoformat()


def _provider_daily_call_limit(provider: str) -> int | None:
    env_name = {
        "serpapi": "INSIGHT_GRAPH_SERPAPI_DAILY_CALL_LIMIT",
        "duckduckgo": "INSIGHT_GRAPH_DUCKDUCKGO_DAILY_CALL_LIMIT",
    }.get(provider)
    if env_name is None:
        return None
    raw = os.getenv(env_name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(value, 0)


def _provider_per_run_limit(provider: str) -> int | None:
    env_name = {
        "serpapi": "INSIGHT_GRAPH_SERPAPI_PER_RUN_LIMIT",
        "duckduckgo": "INSIGHT_GRAPH_DUCKDUCKGO_PER_RUN_LIMIT",
        "google": "INSIGHT_GRAPH_GOOGLE_PER_RUN_LIMIT",
    }.get(provider)
    if env_name is None:
        return None
    raw = os.getenv(env_name)
    if raw is None or not raw.strip():
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return max(value, 0)


def _effective_provider_limit(provider: str, limit: int) -> int:
    per_run_limit = _provider_per_run_limit(provider)
    if per_run_limit is None:
        return limit
    return min(limit, per_run_limit)


def _provider_alert_threshold(provider: str) -> float:
    env_name = {
        "serpapi": "INSIGHT_GRAPH_SERPAPI_ALERT_THRESHOLD_RATIO",
        "duckduckgo": "INSIGHT_GRAPH_DUCKDUCKGO_ALERT_THRESHOLD_RATIO",
    }.get(provider)
    if env_name is None:
        return 0.8
    raw = os.getenv(env_name)
    if raw is None or not raw.strip():
        return 0.8
    try:
        value = float(raw)
    except ValueError:
        return 0.8
    return min(max(value, 0.0), 1.0)


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes"}
