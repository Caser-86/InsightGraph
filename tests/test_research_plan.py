from insight_graph.report_quality.domain_profiles import get_domain_profile
from insight_graph.report_quality.research_plan import build_section_research_plan


def test_build_section_research_plan_uses_domain_profile_sections() -> None:
    plan = build_section_research_plan(
        profile=get_domain_profile("competitive_intel"),
        resolved_entities=[{"id": "cursor", "name": "Cursor"}],
    )

    assert plan[0].section_id == "executive-summary"
    assert plan[0].title == "Executive Summary"
    assert plan[0].required_source_types == ("official_site", "docs", "github", "news")
    assert plan[0].min_evidence == 2
    assert plan[0].budget == 3
    assert plan[0].entity_ids == ("cursor",)
    assert plan[0].questions


def test_build_section_research_plan_serializes_payloads() -> None:
    plan = build_section_research_plan(
        profile=get_domain_profile("generic"),
        resolved_entities=[],
    )

    payload = plan[0].to_payload()
    assert payload == {
        "section_id": "executive-summary",
        "title": "Executive Summary",
        "questions": list(plan[0].questions),
        "required_source_types": list(plan[0].required_source_types),
        "min_evidence": 1,
        "budget": 2,
        "entity_ids": [],
    }


def test_build_section_research_plan_single_entity_adds_detail_density() -> None:
    single = build_section_research_plan(
        profile=get_domain_profile("competitive_intel"),
        resolved_entities=[{"id": "cursor", "name": "Cursor"}],
    )
    multi = build_section_research_plan(
        profile=get_domain_profile("competitive_intel"),
        resolved_entities=[
            {"id": "cursor", "name": "Cursor"},
            {"id": "github-copilot", "name": "GitHub Copilot"},
        ],
    )

    # Keep section-0 stable for compatibility, increase depth on later sections.
    assert single[0].min_evidence == multi[0].min_evidence
    assert single[1].min_evidence > multi[1].min_evidence
    assert single[1].budget > multi[1].budget
