from insight_graph.state import Evidence

AUTHORITY_BY_SOURCE_TYPE = {
    "official_site": 100,
    "docs": 90,
    "github": 80,
    "news": 70,
    "blog": 50,
    "unknown": 20,
}


def score_evidence(evidence: Evidence) -> dict[str, object]:
    authority_score = AUTHORITY_BY_SOURCE_TYPE.get(evidence.source_type, 20)
    if not evidence.verified:
        authority_score = min(authority_score, 20)
    relevance_score = _snippet_relevance_score(evidence.snippet)
    overall_score = round((authority_score * 0.6) + (relevance_score * 0.4))
    return {
        "evidence_id": evidence.id,
        "authority_score": authority_score,
        "relevance_score": relevance_score,
        "overall_score": overall_score,
    }


def score_evidence_pool(evidence_pool: list[Evidence]) -> list[dict[str, object]]:
    return [score_evidence(item) for item in evidence_pool]


def _snippet_relevance_score(snippet: str) -> int:
    word_count = len(snippet.split())
    return min(100, max(20, word_count * 34))
