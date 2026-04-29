from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ResolvedEntity:
    id: str
    name: str
    entity_type: str
    aliases: tuple[str, ...]
    official_domains: tuple[str, ...]
    query_terms: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "aliases": list(self.aliases),
            "official_domains": list(self.official_domains),
            "query_terms": list(self.query_terms),
        }


KNOWN_ENTITIES: tuple[ResolvedEntity, ...] = (
    ResolvedEntity("cursor", "Cursor", "product", ("Cursor",), ("cursor.com",), ("Cursor",)),
    ResolvedEntity(
        "opencode",
        "OpenCode",
        "product",
        ("OpenCode", "OpenCode AI"),
        ("opencode.ai", "github.com/sst/opencode"),
        ("OpenCode", "opencode"),
    ),
    ResolvedEntity(
        "claude-code",
        "Claude Code",
        "product",
        ("Claude Code",),
        ("anthropic.com",),
        ("Claude Code", "Anthropic Claude Code"),
    ),
    ResolvedEntity(
        "github-copilot",
        "GitHub Copilot",
        "product",
        ("GitHub Copilot", "Copilot"),
        ("github.com", "docs.github.com"),
        ("GitHub Copilot", "Copilot"),
    ),
    ResolvedEntity("codeium", "Codeium", "product", ("Codeium",), ("codeium.com",), ("Codeium",)),
    ResolvedEntity(
        "windsurf",
        "Windsurf",
        "product",
        ("Windsurf", "Codeium Windsurf"),
        ("windsurf.com",),
        ("Windsurf", "Codeium Windsurf"),
    ),
    ResolvedEntity(
        "anthropic",
        "Anthropic",
        "company",
        ("Anthropic",),
        ("anthropic.com",),
        ("Anthropic",),
    ),
    ResolvedEntity("openai", "OpenAI", "company", ("OpenAI",), ("openai.com",), ("OpenAI",)),
    ResolvedEntity("github", "GitHub", "company", ("GitHub",), ("github.com",), ("GitHub",)),
)

_GENERIC_TOKENS = {
    "Analyze",
    "Compare",
    "Map",
    "Summarize",
    "Build",
    "Research",
    "AI",
    "Agent",
    "Agents",
    "Market",
}
_CAPITALIZED_TOKEN_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9]*(?:[A-Z][A-Za-z0-9]*)*\b")


def resolve_entities(user_request: str) -> list[ResolvedEntity]:
    matches: list[tuple[int, int, ResolvedEntity]] = []
    occupied_spans: list[tuple[int, int]] = []
    seen: set[str] = set()
    candidates: list[tuple[int, int, ResolvedEntity]] = []
    for entity in KNOWN_ENTITIES:
        for alias in entity.aliases:
            span = _alias_span(user_request, alias)
            if span is not None:
                candidates.append((span[0], span[1], entity))

    for start, end, entity in sorted(candidates, key=lambda item: (-(item[1] - item[0]), item[0])):
        if entity.id in seen or _span_overlaps(start, end, occupied_spans):
            continue
        matches.append((start, end, entity))
        occupied_spans.append((start, end))
        positions = [_alias_position(user_request, alias) for alias in entity.aliases]
        positions = [position for position in positions if position >= 0]
        seen.add(entity.id)

    resolved = [entity for _, _, entity in sorted(matches, key=lambda item: item[0])]
    known_alias_spans = _matched_known_alias_spans(user_request, resolved)
    for token in _CAPITALIZED_TOKEN_PATTERN.findall(user_request):
        if token in _GENERIC_TOKENS:
            continue
        if _token_is_in_known_alias(user_request, token, known_alias_spans):
            continue
        entity_id = _normalize_id(token)
        if entity_id in seen or any(entity_id == known.id for known in KNOWN_ENTITIES):
            continue
        resolved.append(
            ResolvedEntity(
                id=entity_id,
                name=token,
                entity_type="unknown",
                aliases=(token,),
                official_domains=(),
                query_terms=(token,),
            )
        )
        seen.add(entity_id)
    return resolved


def _alias_position(text: str, alias: str) -> int:
    span = _alias_span(text, alias)
    return -1 if span is None else span[0]


def _alias_span(text: str, alias: str) -> tuple[int, int] | None:
    match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.IGNORECASE)
    return None if match is None else match.span()


def _span_overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(
        start < existing_end and existing_start < end
        for existing_start, existing_end in spans
    )


def _matched_known_alias_spans(
    text: str,
    entities: list[ResolvedEntity],
) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for entity in entities:
        for alias in entity.aliases:
            match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.IGNORECASE)
            if match is not None:
                spans.append(match.span())
    return spans


def _token_is_in_known_alias(
    text: str,
    token: str,
    spans: list[tuple[int, int]],
) -> bool:
    match = re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text)
    if match is None:
        return False
    return any(start <= match.start() and match.end() <= end for start, end in spans)


def _normalize_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
