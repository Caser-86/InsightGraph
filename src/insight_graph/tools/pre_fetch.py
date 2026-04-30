import json
import re

from insight_graph.report_quality.budgeting import get_research_budgets
from insight_graph.report_quality.source_types import infer_source_type
from insight_graph.state import Evidence
from insight_graph.tools.fetch_url import fetch_url
from insight_graph.tools.search_providers import SearchResult
from insight_graph.tools.url_canonicalization import canonicalize_url


def pre_fetch_results(
    results: list[SearchResult],
    subtask_id: str = "collect",
    limit: int = 3,
    query: str | None = None,
) -> list[Evidence]:
    evidence: list[Evidence] = []
    fetch_limit = min(limit, get_research_budgets().max_fetches)
    seen_canonical_urls: set[str] = set()
    for rank, result in enumerate(results[:fetch_limit], start=1):
        canonical_url = canonicalize_url(result.url)
        if canonical_url in seen_canonical_urls:
            continue
        seen_canonical_urls.add(canonical_url)
        try:
            fetched = fetch_url(_fetch_query(result.url, query), subtask_id)
        except Exception as exc:
            evidence.append(_diagnostic_evidence(result, subtask_id, rank, query, exc))
            continue
        if not fetched:
            evidence.append(_diagnostic_evidence(result, subtask_id, rank, query, None))
            continue
        evidence.extend(
            _attach_search_metadata(item, result, rank, query, fetch_status="fetched")
            for item in fetched
        )
    return evidence


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
    fetch_error = str(error) if error is not None else "fetch returned no evidence"
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
