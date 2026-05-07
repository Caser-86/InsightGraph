import os
from urllib.parse import urlparse

from insight_graph.report_quality.citation_support import validate_citation_support
from insight_graph.report_quality.fact_mapping import build_fact_conclusion_mapping
from insight_graph.report_quality.intensity import get_report_intensity_config
from insight_graph.state import Critique, Evidence, GraphState


def critique_analysis(state: GraphState) -> GraphState:
    state.citation_support = validate_citation_support(state.findings, state.evidence_pool)
    fact_mapping = build_fact_conclusion_mapping(state)
    strict_quality_gate = _strict_quality_gate_enabled()
    state.entity_collection_status = _build_entity_collection_status(
        state,
        _entity_min_verified_evidence(
            _resolved_entity_count(state),
            strict_quality_gate,
        ),
    )
    state.replan_requests = _build_replan_requests(state)
    state.tried_strategies = _updated_tried_strategies(
        state.tried_strategies,
        state.replan_requests,
    )
    verified_count = sum(1 for item in state.evidence_pool if item.verified)
    min_verified_evidence = _min_verified_evidence_threshold(strict_quality_gate)
    has_findings = bool(state.findings)
    citations_supported = has_findings and all(
        item.get("support_status") == "supported" for item in state.citation_support
    )
    entity_coverage_ok = _all_entities_sufficient(state.entity_collection_status)
    section_coverage_ok = (
        _all_sections_sufficient(state.section_collection_status)
        if strict_quality_gate
        else True
    )
    topic_coverage_ok = (
        _topic_coverage_ok(state.section_collection_status)
        if strict_quality_gate
        else True
    )
    fact_mapping_ok = (
        fact_mapping["weak_conclusion_count"]
        <= _max_weak_conclusions_threshold(strict_quality_gate)
    )
    passed = (
        verified_count >= min_verified_evidence
        and has_findings
        and citations_supported
        and section_coverage_ok
        and entity_coverage_ok
        and topic_coverage_ok
        and fact_mapping_ok
    )
    missing_topics = []
    if verified_count < min_verified_evidence:
        missing_topics.append("verified evidence")
    if not has_findings:
        missing_topics.append("analysis findings")
    if not citations_supported:
        missing_topics.append("citation support")
    if not section_coverage_ok:
        missing_topics.append("section coverage")
    if not entity_coverage_ok:
        missing_topics.append("entity coverage")
    if not topic_coverage_ok:
        missing_topics.append("topic coverage")
    if not fact_mapping_ok:
        missing_topics.append("fact-conclusion mapping")
    state.critique = Critique(
        passed=passed,
        reason=(
            "Sufficient verified evidence and findings are available."
            if passed
            else "Evidence, findings, or citation support are insufficient."
        ),
        missing_topics=missing_topics,
    )
    return state


def _build_replan_requests(state: GraphState) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    tried_strategies = set(state.tried_strategies)
    for status in state.section_collection_status:
        if status.get("sufficient") is False:
            section_id = str(status.get("section_id", ""))
            missing_source_types = _missing_source_types(status)
            strategy_key = _missing_section_strategy_key(section_id, missing_source_types)
            if strategy_key in tried_strategies:
                continue
            requests.append(
                {
                    "type": "missing_section_evidence",
                    "section_id": section_id,
                    "missing_section": section_id,
                    "missing_evidence": int(status.get("missing_evidence", 0)),
                    "missing_source_types": missing_source_types,
                    "strategy_key": strategy_key,
                }
            )
    for status in state.entity_collection_status:
        if status.get("sufficient") is not False:
            continue
        entity_name = str(status.get("entity_name", "")).strip()
        if not entity_name:
            continue
        entity_id = str(status.get("entity_id", "entity")).strip() or "entity"
        strategy_key = f"missing_entity_evidence:{entity_id}:official_site_docs"
        if strategy_key in tried_strategies:
            continue
        requests.append(
            {
                "type": "missing_entity_evidence",
                "missing_entity": entity_name,
                "entity_id": entity_id,
                "missing_evidence": int(status.get("missing_evidence", 0)),
                "missing_source_types": ["official_site", "docs"],
                "preferred_domains": _string_values(status.get("official_domains", [])),
                "strategy_key": strategy_key,
            }
        )
    for item in state.citation_support:
        if item.get("support_status") != "supported":
            requests.append(_unsupported_claim_request(state, item))
    requests.extend(_weak_mapping_replan_requests(state, tried_strategies))
    return requests


def _weak_mapping_replan_requests(
    state: GraphState,
    tried_strategies: set[str],
) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    mapping = build_fact_conclusion_mapping(state)
    for weak in mapping.get("weak_conclusions", []):
        claim = weak.get("claim")
        claim_type = weak.get("claim_type")
        if not isinstance(claim, str) or not claim.strip():
            continue
        # finding claims already covered by citation_support workflow.
        if claim_type == "finding":
            continue
        strategy_key = f"weak_mapping:{_normalize_claim_key(claim)}:official_site_docs"
        if strategy_key in tried_strategies:
            continue
        request: dict[str, object] = {
            "type": "unsupported_claim",
            "claim": claim,
            "reason": "weak fact-conclusion mapping",
            "unsupported_claim_hint": claim,
            "strategy_key": strategy_key,
        }
        missing_entity = _first_entity_name(state)
        if missing_entity:
            request["missing_entity"] = missing_entity
        requests.append(request)
    return requests


def _unsupported_claim_request(
    state: GraphState,
    item: dict[str, object],
) -> dict[str, object]:
    claim = str(item.get("claim", ""))
    request: dict[str, object] = {
        "type": "unsupported_claim",
        "claim": claim,
        "reason": str(item.get("unsupported_reason", "")),
    }
    evidence = _first_supported_evidence(state, item)
    if evidence is not None:
        if evidence.section_id:
            request["missing_section"] = evidence.section_id
        request["missing_source_type"] = evidence.source_type
    missing_entity = _first_entity_name(state)
    if missing_entity:
        request["missing_entity"] = missing_entity
    if claim:
        request["unsupported_claim_hint"] = claim
    return request


def _first_supported_evidence(state: GraphState, item: dict[str, object]):
    evidence_ids = item.get("evidence_ids", [])
    if not isinstance(evidence_ids, list):
        return None
    evidence_by_id = {evidence.id: evidence for evidence in state.evidence_pool}
    for evidence_id in evidence_ids:
        if not isinstance(evidence_id, str):
            continue
        evidence = evidence_by_id.get(evidence_id)
        if evidence is not None:
            return evidence
    return None


def _first_entity_name(state: GraphState) -> str:
    for entity in state.resolved_entities:
        name = entity.get("name")
        if isinstance(name, str) and name:
            return name
    return ""


def _missing_section_strategy_key(section_id: str, missing_source_types: list[str]) -> str:
    source_key = ",".join(sorted(missing_source_types)) if missing_source_types else "evidence"
    return f"missing_section_evidence:{section_id}:{source_key}"


def _updated_tried_strategies(
    existing: list[str],
    replan_requests: list[dict[str, object]],
) -> list[str]:
    strategies = list(existing)
    seen = set(strategies)
    for request in replan_requests:
        strategy_key = request.get("strategy_key")
        if not isinstance(strategy_key, str) or not strategy_key or strategy_key in seen:
            continue
        seen.add(strategy_key)
        strategies.append(strategy_key)
    return strategies


def _missing_source_types(status: dict[str, object]) -> list[str]:
    values = status.get("missing_source_types", [])
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str)]


def _resolved_entity_count(state: GraphState) -> int:
    return sum(
        1
        for entity in state.resolved_entities
        if isinstance(entity.get("name"), str) and str(entity.get("name")).strip()
    )


def _entity_min_verified_evidence(entity_count: int, strict_quality_gate: bool) -> int:
    intensity = get_report_intensity_config().name if strict_quality_gate else "standard"
    if intensity == "concise":
        base = 1
    elif intensity == "standard":
        base = 1
    elif intensity == "deep":
        base = 2
    elif intensity == "deep-plus":
        base = 3
    else:
        base = 1
    mode = _single_entity_detail_mode()
    if mode == "off":
        return base
    if mode == "on":
        return base + 1
    # auto mode: single-company analysis should be denser than multi-company analysis.
    return base + 1 if entity_count == 1 else base


def _single_entity_detail_mode() -> str:
    mode = os.getenv("INSIGHT_GRAPH_SINGLE_ENTITY_DETAIL_MODE", "auto").strip().lower()
    return mode if mode in {"auto", "on", "off"} else "auto"


def _min_verified_evidence_threshold(strict_quality_gate: bool) -> int:
    if not strict_quality_gate:
        return 3
    intensity = get_report_intensity_config()
    return max(3, int(intensity.min_verified_evidence))


def _strict_quality_gate_enabled() -> bool:
    override = os.getenv("INSIGHT_GRAPH_STRICT_QUALITY_GATE")
    if override is not None:
        return override.strip().lower() in {"1", "true", "yes"}
    return os.getenv("INSIGHT_GRAPH_USE_WEB_SEARCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _topic_coverage_ok(statuses: list[dict[str, object]]) -> bool:
    if not statuses:
        return True
    meaningful = [
        status
        for status in statuses
        if str(status.get("section_id", "")).strip().lower() not in {"references", "sources"}
    ]
    if not meaningful:
        return True
    covered = sum(1 for status in meaningful if bool(status.get("sufficient", False)))
    ratio = covered / len(meaningful)
    return ratio >= _min_topic_coverage_ratio()


def _min_topic_coverage_ratio() -> float:
    raw = os.getenv("INSIGHT_GRAPH_MIN_TOPIC_COVERAGE_RATIO", "0.70").strip()
    try:
        value = float(raw)
    except ValueError:
        return 0.70
    return min(max(value, 0.0), 1.0)


def _max_weak_conclusions_threshold(strict_quality_gate: bool) -> int:
    raw = os.getenv(
        "INSIGHT_GRAPH_MAX_WEAK_CONCLUSIONS",
        "0" if strict_quality_gate else "2",
    ).strip()
    try:
        value = int(raw)
    except ValueError:
        return 0 if strict_quality_gate else 2
    return max(value, 0)


def _build_entity_collection_status(
    state: GraphState,
    min_per_entity: int,
) -> list[dict[str, object]]:
    statuses: list[dict[str, object]] = []
    verified_evidence = [item for item in state.evidence_pool if item.verified]
    for entity in state.resolved_entities:
        entity_name = entity.get("name")
        if not isinstance(entity_name, str) or not entity_name.strip():
            continue
        entity_id = _safe_entity_id(entity, entity_name)
        aliases = _string_values(entity.get("aliases", []))
        domains = _normalize_domains(_string_values(entity.get("official_domains", [])))
        matched = [
            item
            for item in verified_evidence
            if _evidence_matches_entity(item, entity_name, aliases, domains)
        ]
        evidence_count = len(matched)
        missing = max(0, min_per_entity - evidence_count)
        statuses.append(
            {
                "entity_id": entity_id,
                "entity_name": entity_name,
                "aliases": aliases,
                "official_domains": sorted(domains),
                "evidence_count": evidence_count,
                "min_evidence": min_per_entity,
                "missing_evidence": missing,
                "matched_evidence_ids": [item.id for item in matched],
                "sufficient": missing == 0,
            }
        )
    return statuses


def _all_entities_sufficient(statuses: list[dict[str, object]]) -> bool:
    if not statuses:
        return True
    return all(bool(status.get("sufficient", False)) for status in statuses)


def _all_sections_sufficient(statuses: list[dict[str, object]]) -> bool:
    if not statuses:
        return True
    return all(bool(status.get("sufficient", False)) for status in statuses)


def _safe_entity_id(entity: dict[str, object], fallback_name: str) -> str:
    entity_id = entity.get("id")
    if isinstance(entity_id, str) and entity_id:
        return entity_id
    return fallback_name.strip().lower().replace(" ", "-")


def _normalize_domains(values: list[str]) -> set[str]:
    domains: set[str] = set()
    for value in values:
        raw = value.strip().lower()
        if not raw:
            continue
        if "://" not in raw:
            raw = f"https://{raw}"
        parsed = urlparse(raw)
        host = parsed.netloc or parsed.path.split("/", maxsplit=1)[0]
        host = host.split("@", maxsplit=1)[-1].split(":", maxsplit=1)[0]
        if host.startswith("www."):
            host = host[4:]
        if host:
            domains.add(host)
    return domains


def _evidence_matches_entity(
    evidence: Evidence,
    entity_name: str,
    aliases: list[str],
    domains: set[str],
) -> bool:
    evidence_domain = _normalize_domains([evidence.source_url])
    if domains and evidence_domain and any(
        any(host == domain or host.endswith(f".{domain}") for domain in domains)
        for host in evidence_domain
    ):
        return True
    haystack = (
        f"{evidence.title}\n{evidence.source_url}\n{evidence.snippet}".lower()
    )
    terms = [entity_name, *aliases]
    for term in terms:
        normalized = term.strip().lower()
        if len(normalized) < 3:
            continue
        if normalized in haystack:
            return True
    return False


def _string_values(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value]


def _normalize_claim_key(value: str) -> str:
    return "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")
