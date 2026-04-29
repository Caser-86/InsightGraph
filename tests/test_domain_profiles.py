import pytest

from insight_graph.report_quality.domain_profiles import (
    DOMAIN_PROFILES,
    detect_domain_profile,
    get_domain_profile,
)


def test_domain_profiles_define_required_phase2_domains() -> None:
    assert set(DOMAIN_PROFILES) == {
        "competitive_intel",
        "technology_trends",
        "market_research",
        "company_profile",
        "generic",
    }

    for profile in DOMAIN_PROFILES.values():
        assert profile.report_sections
        assert profile.required_questions
        assert profile.priority_source_types
        assert profile.min_evidence_per_section >= 1


@pytest.mark.parametrize(
    ("query", "profile_id"),
    [
        ("Compare Cursor, OpenCode, and GitHub Copilot pricing", "competitive_intel"),
        ("Analyze AI agent architecture and technology trends", "technology_trends"),
        ("Map the AI coding tools market opportunity", "market_research"),
        ("Build a company profile for Anthropic funding and products", "company_profile"),
        ("Summarize this research topic", "generic"),
    ],
)
def test_detect_domain_profile_is_deterministic(query: str, profile_id: str) -> None:
    assert detect_domain_profile(query).id == profile_id


def test_get_domain_profile_returns_generic_for_unknown_id() -> None:
    assert get_domain_profile("missing").id == "generic"
