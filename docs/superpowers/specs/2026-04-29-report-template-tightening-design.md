# Report Template Tightening Design

## Goal

Make deterministic reports follow `section_research_plan` when available, instead of always using the fixed `Key Findings` body.

## Approach

When `GraphState.section_research_plan` is present, Reporter renders each planned section title except `References`. Findings are assigned to a section by the `section_id` of their cited verified evidence. If a planned section has no citable finding, the section remains visible with a short insufficiency sentence.

When no section plan exists, Reporter keeps the existing `## Key Findings` output so older direct tests and callers remain stable. Competitive Matrix, Critic Assessment, Citation Support, and References keep their existing positions after the main findings body.

## Scope

This change only affects deterministic Reporter output. LLM Reporter prompt/body generation is deferred because it needs stricter JSON prompt and validation changes, and the roadmap item specifically calls for deterministic template tightening.

## Testing

Add a RED test proving planned sections replace `Key Findings`, section headings use plan titles, and findings appear under the section matching their cited evidence's `section_id`.
