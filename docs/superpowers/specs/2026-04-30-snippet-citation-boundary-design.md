# Snippet Citation Boundary Design

## Goal

Move citation support closer to the reference design: verified URLs produce evidence snippets, Reporter consumes only those verified snippets, and citation support metadata records which snippets support each claim.

## Reference Alignment

The reference flow is `collect citations -> parallel URL validation -> evidence_snippets extraction -> anti-hallucination prompt -> Markdown + numbered references`. InsightGraph already validates live URLs and rebuilds verified-only References. This phase tightens the snippet boundary so claim support is tied to specific evidence snippets instead of only evidence IDs.

## Scope

- Preserve offline deterministic defaults.
- Keep LLM Reporter opt-in, but make its prompt explicitly snippet-grounded.
- Add snippet-level support metadata to `GraphState.citation_support`.
- Keep deterministic lexical validation as the offline fallback.
- Do not add real LLM-as-judge citation validation in this phase; tests remain fake/offline.

## Design

`validate_citation_support()` will enrich each support record with:

- `supporting_snippets`: snippets from verified cited evidence.
- `matched_terms`: claim terms found in cited snippets.
- `missing_terms`: claim terms not found in cited snippets.
- `support_score`: matched claim term ratio.

Support status remains `supported` or `unsupported`. A finding is supported when it cites verified evidence and has at least one meaningful matched term. This preserves current behavior while exposing the exact snippet boundary used by Critic and Reporter.

Reporter will include evidence snippets in the LLM prompt as the only allowed factual basis. The prompt will explicitly instruct the model to write claims only from listed snippets and use only allowed `[N]` citations. Deterministic Reporter continues to render only findings with verified citations.

## Testing

- Citation support records include supporting snippets, matched terms, missing terms, and score.
- Unsupported records include missing terms and snippets when verified evidence exists but lexical support is weak.
- LLM Reporter prompt includes `evidence_snippets` language and snippet text.
- Reporter Citation Support table can render snippet support metadata without exposing unverified evidence.

## Non-Goals

- No live LLM judge for claim verification.
- No claim rewriting.
- No forced removal of a finding solely because support score is below a new threshold beyond current supported/unsupported semantics.
- No changes to URL validation behavior.
