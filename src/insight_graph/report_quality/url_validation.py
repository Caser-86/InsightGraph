import os

from insight_graph.state import Evidence
from insight_graph.tools.http_client import FetchError, fetch_text


def validate_evidence_url(evidence: Evidence) -> dict[str, object]:
    try:
        page = fetch_text(
            evidence.source_url,
            timeout=_url_validation_timeout_seconds(),
        )
    except FetchError as exc:
        return {
            "evidence_id": evidence.id,
            "source_url": evidence.source_url,
            "valid": False,
            "status_code": None,
            "error": str(exc),
        }
    except TimeoutError as exc:
        return {
            "evidence_id": evidence.id,
            "source_url": evidence.source_url,
            "valid": False,
            "status_code": None,
            "error": f"Timeout error while validating URL: {exc}",
        }
    except OSError as exc:
        return {
            "evidence_id": evidence.id,
            "source_url": evidence.source_url,
            "valid": False,
            "status_code": None,
            "error": f"Network error while validating URL: {exc}",
        }
    return {
        "evidence_id": evidence.id,
        "source_url": evidence.source_url,
        "valid": True,
        "status_code": page.status_code,
        "error": None,
    }


def _url_validation_timeout_seconds() -> float:
    raw_value = os.getenv("INSIGHT_GRAPH_URL_VALIDATION_TIMEOUT_SECONDS")
    if raw_value is None:
        return 3.0
    try:
        value = float(raw_value)
    except ValueError:
        return 3.0
    return value if value > 0 else 3.0
