from insight_graph.state import Evidence
from insight_graph.tools.http_client import FetchError, fetch_text


def validate_evidence_url(evidence: Evidence) -> dict[str, object]:
    try:
        page = fetch_text(evidence.source_url)
    except FetchError as exc:
        return {
            "evidence_id": evidence.id,
            "source_url": evidence.source_url,
            "valid": False,
            "status_code": None,
            "error": str(exc),
        }
    return {
        "evidence_id": evidence.id,
        "source_url": evidence.source_url,
        "valid": True,
        "status_code": page.status_code,
        "error": None,
    }
