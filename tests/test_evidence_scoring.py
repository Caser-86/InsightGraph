from insight_graph.report_quality.evidence_scoring import score_evidence
from insight_graph.state import Evidence


def test_score_evidence_prefers_verified_authoritative_sources() -> None:
    evidence = Evidence(
        id="official",
        subtask_id="collect",
        title="Official Pricing",
        source_url="https://example.com/pricing",
        snippet="Official pricing evidence.",
        source_type="official_site",
        verified=True,
    )

    score = score_evidence(evidence)

    assert score["evidence_id"] == "official"
    assert score["authority_score"] == 100
    assert score["relevance_score"] == 100
    assert score["overall_score"] == 100


def test_score_evidence_penalizes_unverified_and_unknown_sources() -> None:
    evidence = Evidence(
        id="unknown",
        subtask_id="collect",
        title="Unknown",
        source_url="https://blog.example.com/post",
        snippet="Short.",
        source_type="unknown",
        verified=False,
    )

    score = score_evidence(evidence)

    assert score["authority_score"] == 20
    assert score["relevance_score"] < 100
    assert score["overall_score"] < 60


def test_score_evidence_prioritizes_sec_and_official_sources() -> None:
    sec_score = score_evidence(
        Evidence(
            id="sec",
            subtask_id="collect",
            title="SEC Filing",
            source_url="https://www.sec.gov/Archives/edgar/data/320193/10-k.htm",
            snippet="SEC filing evidence with sufficiently descriptive text.",
            source_type="sec",
            verified=True,
        )
    )
    blog_score = score_evidence(
        Evidence(
            id="blog",
            subtask_id="collect",
            title="Blog",
            source_url="https://blog.example.com/post",
            snippet="Blog evidence with sufficiently descriptive text.",
            source_type="blog",
            verified=True,
        )
    )

    assert sec_score["authority_score"] == 95
    assert blog_score["authority_score"] == 50
    assert sec_score["overall_score"] > blog_score["overall_score"]
