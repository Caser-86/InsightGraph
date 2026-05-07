from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from insight_graph.report_quality.domain_profiles import DomainProfile


@dataclass(frozen=True)
class SectionResearchPlan:
    section_id: str
    title: str
    questions: tuple[str, ...]
    required_source_types: tuple[str, ...]
    min_evidence: int
    budget: int
    entity_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "section_id": self.section_id,
            "title": self.title,
            "questions": list(self.questions),
            "required_source_types": list(self.required_source_types),
            "min_evidence": self.min_evidence,
            "budget": self.budget,
            "entity_ids": list(self.entity_ids),
        }


def build_section_research_plan(
    *,
    profile: DomainProfile,
    resolved_entities: list[dict[str, Any]],
) -> list[SectionResearchPlan]:
    entity_ids = tuple(str(entity["id"]) for entity in resolved_entities if "id" in entity)
    single_entity_detail = len(entity_ids) == 1
    plan: list[SectionResearchPlan] = []
    for index, section in enumerate(profile.report_sections):
        section_id = _section_id(section)
        min_evidence = profile.min_evidence_per_section
        if single_entity_detail and index > 0 and section_id not in {"references", "sources"}:
            # Single-company reports should be denser in section-level evidence.
            min_evidence += 1
        budget = max(2, min_evidence + 1)
        if single_entity_detail and index > 0:
            budget += 1
        plan.append(
            SectionResearchPlan(
                section_id=section_id,
                title=section,
                questions=_section_questions(profile, section),
                required_source_types=profile.priority_source_types,
                min_evidence=min_evidence,
                budget=budget,
                entity_ids=entity_ids,
            )
        )
    return plan


def _section_questions(profile: DomainProfile, section: str) -> tuple[str, ...]:
    return tuple(
        f"{question} Section focus: {section}." for question in profile.required_questions
    )


def _section_id(section: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", section.lower()).strip("-")
