from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainProfile:
    id: str
    display_name: str
    report_sections: tuple[str, ...]
    required_questions: tuple[str, ...]
    priority_source_types: tuple[str, ...]
    min_evidence_per_section: int
    expected_tables: tuple[str, ...] = ()


DOMAIN_PROFILES: dict[str, DomainProfile] = {
    "competitive_intel": DomainProfile(
        id="competitive_intel",
        display_name="Competitive Intelligence",
        report_sections=(
            "Executive Summary",
            "Product Positioning",
            "Competitive Landscape",
            "Pricing and Packaging",
            "Risks and Outlook",
            "References",
        ),
        required_questions=(
            "Which products or companies should be compared?",
            "How do positioning, features, pricing, and ecosystems differ?",
            "Which risks or uncertainties change the comparison?",
        ),
        priority_source_types=("official_site", "docs", "github", "news"),
        min_evidence_per_section=2,
        expected_tables=("Competitive Matrix",),
    ),
    "technology_trends": DomainProfile(
        id="technology_trends",
        display_name="Technology Trends",
        report_sections=(
            "Executive Summary",
            "Technology Background",
            "Adoption Signals",
            "Technical Trade-offs",
            "Risks and Outlook",
            "References",
        ),
        required_questions=(
            "Which technical shifts are visible in authoritative sources?",
            "Which adoption signals support or weaken the trend?",
            "What risks, constraints, or unknowns remain?",
        ),
        priority_source_types=("docs", "github", "official_site", "news"),
        min_evidence_per_section=2,
    ),
    "market_research": DomainProfile(
        id="market_research",
        display_name="Market Research",
        report_sections=(
            "Executive Summary",
            "Market Context",
            "Demand Signals",
            "Competitive Landscape",
            "Opportunities and Risks",
            "References",
        ),
        required_questions=(
            "What market segment and buyer needs define the opportunity?",
            "Which demand, adoption, or ecosystem signals are visible?",
            "What risks could limit market growth?",
        ),
        priority_source_types=("news", "official_site", "docs", "blog"),
        min_evidence_per_section=2,
        expected_tables=("Market Signals",),
    ),
    "company_profile": DomainProfile(
        id="company_profile",
        display_name="Company Profile",
        report_sections=(
            "Executive Summary",
            "Company Background",
            "Products and Strategy",
            "Funding and Ecosystem",
            "Risks and Outlook",
            "References",
        ),
        required_questions=(
            "What does the company build and who does it serve?",
            "Which product, funding, or ecosystem signals are verified?",
            "What strategic risks or unknowns remain?",
        ),
        priority_source_types=("official_site", "news", "docs", "github"),
        min_evidence_per_section=2,
    ),
    "generic": DomainProfile(
        id="generic",
        display_name="Generic Research",
        report_sections=(
            "Executive Summary",
            "Background",
            "Analysis",
            "Risks and Unknowns",
            "References",
        ),
        required_questions=(
            "What question should the report answer?",
            "Which sources directly support the main claims?",
            "What remains uncertain?",
        ),
        priority_source_types=("official_site", "docs", "news", "blog", "github"),
        min_evidence_per_section=1,
    ),
}

_DOMAIN_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "competitive_intel",
        (
            "compare",
            "comparison",
            "competitive",
            "competitor",
            "rival",
            "versus",
            " vs ",
            "pricing",
            "positioning",
            "竞品",
            "对比",
            "比较",
        ),
    ),
    (
        "technology_trends",
        (
            "technology",
            "technical",
            "architecture",
            "trend",
            "trends",
            "model",
            "framework",
            "技术",
            "架构",
            "趋势",
        ),
    ),
    (
        "market_research",
        (
            "market",
            "opportunity",
            "demand",
            "adoption",
            "segment",
            "buyer",
            "市场",
            "机会",
            "需求",
        ),
    ),
    (
        "company_profile",
        (
            "company profile",
            "company",
            "funding",
            "revenue",
            "organization",
            "startup",
            "公司",
            "融资",
        ),
    ),
)


def get_domain_profile(profile_id: str | None) -> DomainProfile:
    if profile_id is None:
        return DOMAIN_PROFILES["generic"]
    return DOMAIN_PROFILES.get(profile_id, DOMAIN_PROFILES["generic"])


def detect_domain_profile(user_request: str) -> DomainProfile:
    normalized = f" {user_request.lower()} "
    for profile_id, keywords in _DOMAIN_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return DOMAIN_PROFILES[profile_id]
    return DOMAIN_PROFILES["generic"]
