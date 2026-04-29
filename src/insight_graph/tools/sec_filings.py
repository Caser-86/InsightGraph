from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from insight_graph.state import Evidence

SEC_USER_AGENT = "InsightGraph contact@example.com"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{document}"
DEFAULT_SEC_LIMIT = 3

KNOWN_TICKER_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "NVDA": "0001045810",
    "TSLA": "0001318605",
}


def sec_filings(query: str, subtask_id: str = "collect") -> list[Evidence]:
    ticker = _extract_ticker(query)
    if ticker is None:
        return []
    cik = KNOWN_TICKER_CIKS.get(ticker)
    if cik is None:
        return []

    try:
        payload = fetch_sec_json(
            SEC_SUBMISSIONS_URL.format(cik=cik),
            {"Accept": "application/json", "User-Agent": SEC_USER_AGENT},
            timeout=10.0,
        )
    except Exception:
        return []

    return _filings_to_evidence(payload, ticker, cik, subtask_id)


def fetch_sec_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            status_code = getattr(response, "status", 200)
            if status_code < 200 or status_code >= 300:
                raise RuntimeError(f"Unexpected SEC API status: {status_code}")
            body = response.read()
    except HTTPError as exc:
        raise RuntimeError(f"HTTP error while fetching SEC API: {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error while fetching SEC API: {exc.reason}") from exc
    return json.loads(body.decode("utf-8"))


def _extract_ticker(query: str) -> str | None:
    tokens = re.findall(r"[A-Za-z]{1,5}", query.upper())
    for token in tokens:
        if token in KNOWN_TICKER_CIKS:
            return token
    return None


def _filings_to_evidence(
    payload: dict[str, Any],
    ticker: str,
    cik: str,
    subtask_id: str,
) -> list[Evidence]:
    recent = payload.get("filings", {}).get("recent", {})
    if not isinstance(recent, dict):
        return []

    forms = recent.get("form")
    accessions = recent.get("accessionNumber")
    filing_dates = recent.get("filingDate")
    documents = recent.get("primaryDocument")
    if not all(isinstance(value, list) for value in [forms, accessions, filing_dates, documents]):
        return []

    evidence: list[Evidence] = []
    for form, accession, filing_date, document in zip(
        forms, accessions, filing_dates, documents, strict=False
    ):
        fields = [form, accession, filing_date, document]
        if not all(isinstance(value, str) and value for value in fields):
            continue
        if form not in {"10-K", "10-Q", "8-K", "S-1"}:
            continue
        evidence.append(
            Evidence(
                id=f"sec-{ticker.lower()}-{form.lower()}-{filing_date}",
                subtask_id=subtask_id,
                title=f"{ticker} {form} filing {filing_date}",
                source_url=_filing_url(cik, accession, document),
                snippet=f"{ticker} filed {form} on {filing_date}.",
                source_type="official_site",
                verified=True,
            )
        )
        if len(evidence) >= DEFAULT_SEC_LIMIT:
            break
    return evidence


def _filing_url(cik: str, accession: str, document: str) -> str:
    accession_path = accession.replace("-", "")
    return SEC_ARCHIVES_URL.format(
        cik_int=str(int(cik)),
        accession=accession_path,
        document=document,
    )
