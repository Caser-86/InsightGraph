import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from insight_graph.report_quality.budgeting import get_research_budgets
from insight_graph.report_quality.intensity import get_report_intensity_config
from insight_graph.report_quality.source_types import infer_source_type
from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.search_providers import SearchResult
from insight_graph.tools.url_canonicalization import canonicalize_url

PREFETCH_CONCURRENCY_ENV = "INSIGHT_GRAPH_PREFETCH_CONCURRENCY"
DEFAULT_PREFETCH_CONCURRENCY = 2
MAX_PREFETCH_CONCURRENCY = 5


@dataclass(frozen=True)
class _RankedResult:
    rank: int
    result: SearchResult


@dataclass(frozen=True)
class _FetchedResult:
    rank: int
    evidence: list[Evidence]


def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
    query: str | None = None,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    fetch_limit = min(
        limit,
        get_research_budgets().max_fetches,
        _per_query_prefetch_limit(),
    )
    ranked_results = _unique_ranked_results(results, fetch_limit)
    concurrency = _prefetch_concurrency()
    if concurrency <= 1 or len(ranked_results) <= 1:
        for ranked in ranked_results:
            evidence.extend(_fetch_one_result(ranked, subtask_id, query).evidence)
        return evidence

    fetched_results: list[_FetchedResult] = []
    with ThreadPoolExecutor(max_workers=min(concurrency, len(ranked_results))) as pool:
        futures = [
            pool.submit(_fetch_one_result, ranked, subtask_id, query)
            for ranked in ranked_results
        ]
        for future in as_completed(futures):
            fetched_results.append(future.result())

    for fetched in sorted(fetched_results, key=lambda item: item.rank):
        evidence.extend(fetched.evidence)
    return evidence


def _unique_ranked_results(results: list[SearchResult], fetch_limit: int) -> list[_RankedResult]:
    ranked_results: list[_RankedResult] = []
    seen_canonical_urls: set[str] = set()
    for rank, result in enumerate(results[:fetch_limit], start=1):
        canonical_url = canonicalize_url(result.url)
        if canonical_url in seen_canonical_urls:
            continue
        seen_canonical_urls.add(canonical_url)
        ranked_results.append(_RankedResult(rank=rank, result=result))
    return ranked_results


def _fetch_one_result(
    ranked: _RankedResult,
    subtask_id: str,
    query: str | None,
) -> _FetchedResult:
    rank = ranked.rank
    result = ranked.result
    try:
        fetched = fetch_url(_fetch_query(result.url, query), subtask_id)
    except Exception as exc:
        return _FetchedResult(
            rank=rank,
            evidence=[_diagnostic_evidence(result, subtask_id, rank, query, exc)],
        )
    if not fetched:
        return _FetchedResult(
            rank=rank,
            evidence=[_diagnostic_evidence(result, subtask_id, rank, query, None)],
        )
    return _FetchedResult(
        rank=rank,
        evidence=[
            _attach_search_metadata(item, result, rank, query, fetch_status="fetched")
            for item in fetched
        ],
    )


def _fetch_query(url: str, query: str | None) -> str:
    if not query:
        return url
    return json.dumps({"url": url, "query": query}, separators=(",", ":"))


def _attach_search_metadata(
    evidence: Evidence,
    result: SearchResult,
    rank: int,
    query: str | None,
    *,
    fetch_status: str,
    fetch_error: str | None = None,
) -> Evidence:
    return evidence.model_copy(
        update={
            "search_provider": result.source,
            "search_rank": rank,
            "search_query": query,
            "search_snippet": result.snippet,
            "canonical_url": canonicalize_url(evidence.source_url),
            "fetch_status": fetch_status,
            "fetch_error": fetch_error,
            "reachable": True,
            "source_trusted": _source_url_is_trusted(evidence.source_url),
            "claim_supported": None,
        }
    )


def _diagnostic_evidence(
    result: SearchResult,
    subtask_id: str,
    rank: int,
    query: str | None,
    error: Exception | None,
) -> Evidence:
    fetch_status = "failed" if error is not None else "empty"
    fetch_error = _fetch_error_message(error) if error is not None else "fetch returned no evidence"
    prefix = "fetch-failed" if error is not None else "fetch-missing"
    return Evidence(
        id=f"{prefix}-{_url_slug(result.url)}",
        subtask_id=subtask_id,
        title=f"{result.title} (fetch {fetch_status})",
        source_url=result.url,
        snippet=result.snippet or fetch_error,
        verified=False,
        canonical_url=canonicalize_url(result.url),
        reachable=error is None,
        source_trusted=_source_url_is_trusted(result.url),
        claim_supported=False,
        search_provider=result.source,
        search_rank=rank,
        search_query=query,
        search_snippet=result.snippet,
        fetch_status=fetch_status,
        fetch_error=fetch_error,
    )


def _url_slug(url: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    raw = f"{parsed.netloc}{parsed.path}".strip("/") or url
    return re.sub(r"[^a-zA-Z0-9]+", "-", raw).strip("-").lower() or "candidate"


def _source_url_is_trusted(url: str) -> bool:
    return infer_source_type(url) in {"official_site", "docs", "github", "news", "sec", "paper"}


def _per_query_prefetch_limit() -> int:
    raw_value = os.getenv("INSIGHT_GRAPH_PREFETCH_PER_QUERY_LIMIT")
    if raw_value is not None:
        try:
            value = int(raw_value)
        except ValueError:
            value = 0
        if value > 0:
            return value
    intensity = get_report_intensity_config().name
    if intensity == "deep-plus":
        return 5
    if intensity == "deep":
        return 3
    if intensity == "standard":
        return 2
    return 1


def _prefetch_concurrency() -> int:
    raw_value = os.getenv(PREFETCH_CONCURRENCY_ENV)
    if raw_value is None:
        return DEFAULT_PREFETCH_CONCURRENCY
    try:
        value = int(raw_value)
    except ValueError:
        return DEFAULT_PREFETCH_CONCURRENCY
    if value <= 1:
        return 1
    return min(value, MAX_PREFETCH_CONCURRENCY)


def _fetch_error_message(error: Exception) -> str:
    kind = getattr(error, "kind", None)
    if isinstance(kind, str) and kind:
        return f"{kind}: {error}"
    return str(error)
