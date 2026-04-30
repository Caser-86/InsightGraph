from __future__ import annotations

import hashlib
import os

from insight_graph.memory.embeddings import build_memory_record
from insight_graph.memory.store import ResearchMemoryStore, get_research_memory_store
from insight_graph.state import Evidence, GraphState


def memory_writeback_enabled() -> bool:
    return os.environ.get("INSIGHT_GRAPH_MEMORY_WRITEBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def write_report_memories(
    state: GraphState,
    *,
    store: ResearchMemoryStore | None = None,
    run_id: str | None = None,
) -> int:
    if not memory_writeback_enabled() or not state.report_markdown:
        return 0
    store = store or get_research_memory_store()
    store.ensure_schema()
    count = 0
    for memory_type, text, metadata in _memory_items(state, run_id=run_id):
        memory_id = _memory_id(memory_type, text, run_id)
        store.add_memory(
            build_memory_record(
                memory_id=memory_id,
                text=text,
                metadata={"memory_type": memory_type, **metadata},
            )
        )
        count += 1
    return count


def _memory_items(
    state: GraphState,
    *,
    run_id: str | None,
) -> list[tuple[str, str, dict[str, object]]]:
    base_metadata: dict[str, object] = {"user_request": state.user_request}
    if run_id is not None:
        base_metadata["run_id"] = run_id
    items: list[tuple[str, str, dict[str, object]]] = []
    items.append(("report_summary", _report_summary_text(state), dict(base_metadata)))
    for entity in state.resolved_entities:
        name = entity.get("name")
        entity_id = entity.get("id")
        if isinstance(name, str) and name.strip():
            metadata = {**base_metadata, "entity_id": entity_id or name}
            items.append(("entity", f"Entity researched: {name}.", metadata))
    for claim in state.grounded_claims:
        if claim.get("support_status") != "supported":
            continue
        claim_text = claim.get("claim")
        if isinstance(claim_text, str) and claim_text.strip():
            metadata = {
                **base_metadata,
                "evidence_ids": list(_string_items(claim.get("evidence_ids"))),
            }
            items.append(("supported_claim", claim_text, metadata))
    for evidence in _verified_references(state):
        metadata = {
            **base_metadata,
            "evidence_id": evidence.id,
            "source_url": evidence.source_url,
            "source_type": evidence.source_type,
        }
        items.append(("reference", f"Reference: {evidence.title}. {evidence.source_url}", metadata))
    return items


def _report_summary_text(state: GraphState) -> str:
    finding_summaries = [finding.summary for finding in state.findings if finding.summary]
    if finding_summaries:
        return " ".join(finding_summaries)[:1000]
    return state.report_markdown or state.user_request


def _verified_references(state: GraphState) -> list[Evidence]:
    seen: set[str] = set()
    references = []
    for evidence in [*state.evidence_pool, *state.global_evidence_pool]:
        if not evidence.verified or evidence.id in seen:
            continue
        seen.add(evidence.id)
        references.append(evidence)
    return references


def _string_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _memory_id(memory_type: str, text: str, run_id: str | None) -> str:
    raw = "|".join([run_id or "", memory_type, text]).encode("utf-8")
    digest = hashlib.sha1(raw).hexdigest()[:12]
    return f"{memory_type}-{digest}"
