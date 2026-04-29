from insight_graph.report_quality.entity_resolver import resolve_entities


def test_resolve_entities_detects_known_products_and_domains() -> None:
    entities = resolve_entities("Compare Cursor, OpenCode, and GitHub Copilot")

    assert [entity.id for entity in entities] == ["cursor", "opencode", "github-copilot"]
    assert entities[0].name == "Cursor"
    assert entities[0].entity_type == "product"
    assert entities[0].official_domains == ("cursor.com",)
    assert "Cursor" in entities[0].query_terms


def test_resolve_entities_matches_aliases_and_deduplicates() -> None:
    entities = resolve_entities("Compare Copilot with GitHub Copilot and Claude Code")

    assert [entity.id for entity in entities] == ["github-copilot", "claude-code"]


def test_resolve_entities_returns_empty_for_generic_request() -> None:
    assert resolve_entities("Summarize this research topic") == []


def test_resolve_entities_extracts_unknown_capitalized_entities() -> None:
    entities = resolve_entities("Compare NewAgent and AnotherTool pricing")

    assert [entity.id for entity in entities] == ["newagent", "anothertool"]
    assert all(entity.entity_type == "unknown" for entity in entities)
    assert entities[0].official_domains == ()
