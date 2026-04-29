from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DomainProfile:
    id: str
    display_name: str
    report_sections: tuple[str, ...]
    required_questions: tuple[str, ...]
    priority_source_types: tuple[str, ...]
    min_evidence_per_section: int
    expected_tables: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()


_CODE_DOMAIN_PROFILES: dict[str, DomainProfile] = {
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


def load_domain_profiles_from_directory(path: str | Path) -> dict[str, DomainProfile]:
    directory = Path(path)
    profiles: dict[str, DomainProfile] = {}
    for profile_path in sorted(directory.glob("*.md")):
        profile = _load_domain_profile_from_markdown(profile_path)
        profiles[profile.id] = profile
    return profiles


def _load_domain_profile_from_markdown(path: Path) -> DomainProfile:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text)
    metadata = _parse_frontmatter(frontmatter)
    profile_id = _required_metadata(metadata, "id")
    return DomainProfile(
        id=profile_id,
        display_name=metadata.get("display_name", profile_id.replace("_", " ").title()),
        report_sections=tuple(_section_list(body, "Report Sections")),
        required_questions=tuple(_section_list(body, "Required Questions")),
        priority_source_types=tuple(metadata.get("priority_source_types", [])),
        min_evidence_per_section=int(metadata.get("min_evidence_per_section", "1")),
        expected_tables=tuple(metadata.get("expected_tables", [])),
        keywords=tuple(_section_list(body, "Keywords")),
    )


def _split_frontmatter(text: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        return "", text
    _, frontmatter, body = text.split("---", 2)
    return frontmatter, body


def _parse_frontmatter(text: str) -> dict[str, object]:
    metadata: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key is not None:
            value = line[4:].strip()
            metadata.setdefault(current_key, [])
            values = metadata[current_key]
            if isinstance(values, list):
                values.append(value)
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        metadata[current_key] = value if value else []
    return metadata


def _required_metadata(metadata: dict[str, object], key: str) -> str:
    value = metadata.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Domain profile missing required metadata: {key}")
    return value.strip()


def _section_list(body: str, heading: str) -> list[str]:
    lines = body.splitlines()
    items: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_section = stripped == f"## {heading}"
            continue
        if in_section and stripped.startswith("- "):
            items.append(stripped[2:].strip())
    return items


def _build_domain_profiles() -> dict[str, DomainProfile]:
    profiles = dict(_CODE_DOMAIN_PROFILES)
    profiles.update(load_domain_profiles_from_directory(Path(__file__).with_name("domains")))
    return profiles


DOMAIN_PROFILES: dict[str, DomainProfile] = _build_domain_profiles()


def detect_domain_profile(user_request: str) -> DomainProfile:
    normalized = f" {user_request.lower()} "
    for profile in DOMAIN_PROFILES.values():
        if any(keyword.lower() in normalized for keyword in profile.keywords):
            return profile
    for profile_id, keywords in _DOMAIN_KEYWORDS:
        if any(keyword in normalized for keyword in keywords):
            return DOMAIN_PROFILES[profile_id]
    return DOMAIN_PROFILES["generic"]
