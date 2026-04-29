import pytest

from insight_graph.report_quality.domain_profiles import (
    DOMAIN_PROFILES,
    detect_domain_profile,
    get_domain_profile,
    load_domain_profiles_from_directory,
)


def test_domain_profiles_define_required_phase2_domains() -> None:
    assert {
        "competitive_intel",
        "technology_trends",
        "market_research",
        "company_profile",
        "generic",
    }.issubset(set(DOMAIN_PROFILES))

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


def test_builtin_markdown_domain_profile_is_available() -> None:
    profile = get_domain_profile("biotech_finance")

    assert profile.display_name == "Biotech Finance"
    assert "Pipeline Analysis" in profile.report_sections
    assert profile.min_evidence_per_section == 3
    assert profile.expected_tables == ("Pipeline Matrix",)


def test_detect_domain_profile_uses_markdown_keywords() -> None:
    profile = detect_domain_profile("Analyze biotech pipeline and FDA clinical trial risks")

    assert profile.id == "biotech_finance"


def test_load_domain_profiles_from_markdown_directory() -> None:
    profiles = load_domain_profiles_from_directory("tests/fixtures/domains")

    profile = profiles["biotech_finance"]
    assert profile.display_name == "Biotech Finance"
    assert profile.report_sections == (
        "Executive Summary",
        "Company Fundamentals",
        "Pipeline Analysis",
        "Financial Analysis",
        "Risk Assessment",
        "References",
    )
    assert profile.required_questions == (
        "What are the company's verified financial fundamentals?",
        "Which pipeline assets or catalysts matter most?",
        "Which clinical, regulatory, or financing risks affect the thesis?",
    )
    assert profile.priority_source_types == ("official_site", "sec", "news")
    assert profile.min_evidence_per_section == 3
    assert profile.expected_tables == ("Pipeline Matrix",)
