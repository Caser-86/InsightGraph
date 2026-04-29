import importlib

from insight_graph.report_quality.url_validation import validate_evidence_url
from insight_graph.state import Evidence
from insight_graph.tools.http_client import FetchedPage, FetchError


def test_validate_evidence_url_records_success(monkeypatch) -> None:
    validation_module = importlib.import_module("insight_graph.report_quality.url_validation")

    def fake_fetch_text(url: str, timeout: float = 10.0):
        assert url == "https://example.com/source"
        return FetchedPage(
            url=url,
            status_code=200,
            content_type="text/html",
            text="ok",
        )

    monkeypatch.setattr(validation_module, "fetch_text", fake_fetch_text)
    evidence = Evidence(
        id="source",
        subtask_id="collect",
        title="Source",
        source_url="https://example.com/source",
        snippet="Source snippet.",
        verified=True,
    )

    result = validate_evidence_url(evidence)

    assert result == {
        "evidence_id": "source",
        "source_url": "https://example.com/source",
        "valid": True,
        "status_code": 200,
        "error": None,
    }


def test_validate_evidence_url_records_failure(monkeypatch) -> None:
    validation_module = importlib.import_module("insight_graph.report_quality.url_validation")

    def fake_fetch_text(url: str, timeout: float = 10.0):
        raise FetchError("Network error while fetching URL: timeout")

    monkeypatch.setattr(validation_module, "fetch_text", fake_fetch_text)
    evidence = Evidence(
        id="source",
        subtask_id="collect",
        title="Source",
        source_url="https://example.com/source",
        snippet="Source snippet.",
        verified=True,
    )

    result = validate_evidence_url(evidence)

    assert result == {
        "evidence_id": "source",
        "source_url": "https://example.com/source",
        "valid": False,
        "status_code": None,
        "error": "Network error while fetching URL: timeout",
    }
