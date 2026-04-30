from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from insight_graph.state import Evidence

SEC_USER_AGENT = "InsightGraph contact@example.com"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SEC_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession}/{document}"
DEFAULT_SEC_LIMIT = 3
FINANCIAL_FACTS = (
    ("Revenue", "Revenues"),
    ("Net income", "NetIncomeLoss"),
    ("Assets", "Assets"),
)

KNOWN_TICKER_CIKS = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "GOOG": "0001652044",
    "AMZN": "0001018724",
    "META": "0001326801",
    "NVDA": "0001045810",
    "TSLA": "0001318605",
    "CRM": "0001108524",
    "ORCL": "0001341439",
    "ADBE": "0000796343",
    "NFLX": "0001065280",
    "INTC": "0000050863",
    "AMD": "0000002488",
    "IBM": "0000051143",
    "NOW": "0001373715",
    "SNOW": "0001640147",
    "PLTR": "0001321655",
    "UBER": "0001543151",
    "SHOP": "0001594805",
}

KNOWN_COMPANY_TICKERS = {
    "APPLE": "AAPL",
    "APPLE INC": "AAPL",
    "MICROSOFT": "MSFT",
    "MICROSOFT CORP": "MSFT",
    "ALPHABET": "GOOGL",
    "GOOGLE": "GOOGL",
    "AMAZON": "AMZN",
    "META": "META",
    "NVIDIA": "NVDA",
    "TESLA": "TSLA",
    "SALESFORCE": "CRM",
    "SALESFORCE INC": "CRM",
    "ORACLE": "ORCL",
    "ORACLE CORP": "ORCL",
    "ADOBE": "ADBE",
    "ADOBE INC": "ADBE",
    "NETFLIX": "NFLX",
    "INTEL": "INTC",
    "ADVANCED MICRO DEVICES": "AMD",
    "IBM": "IBM",
    "INTERNATIONAL BUSINESS MACHINES": "IBM",
    "SERVICENOW": "NOW",
    "SNOWFLAKE": "SNOW",
    "PALANTIR": "PLTR",
    "UBER": "UBER",
    "SHOPIFY": "SHOP",
}


def sec_filings(query: str, subtask_id: str = "collect") -> list[Evidence]:
    ticker = resolve_sec_ticker(query)
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


def sec_financials(query: str, subtask_id: str = "collect") -> list[Evidence]:
    ticker = resolve_sec_ticker(query)
    if ticker is None:
        return []
    cik = KNOWN_TICKER_CIKS.get(ticker)
    if cik is None:
        return []

    url = SEC_COMPANYFACTS_URL.format(cik=cik)
    try:
        payload = fetch_sec_json(
            url,
            {"Accept": "application/json", "User-Agent": SEC_USER_AGENT},
            timeout=10.0,
        )
    except Exception:
        return []

    facts = _extract_financial_facts(payload)
    if not facts:
        return []
    first_fact = facts[0][1]
    fiscal_year = str(first_fact["fy"])
    fiscal_period = str(first_fact["fp"])
    snippet_parts = [
        f"{label}: {fact['val']} USD"
        for label, fact in facts
    ]
    filed = str(first_fact["filed"])
    snippet = (
        f"{ticker} SEC companyfacts for {fiscal_year} {fiscal_period} "
        f"filed {filed}. " + "; ".join(snippet_parts) + "."
    )
    return [
        Evidence(
            id=f"sec-financials-{ticker.lower()}-{fiscal_year.lower()}-{fiscal_period.lower()}",
            subtask_id=subtask_id,
            title=f"{ticker} SEC financial facts {fiscal_year} {fiscal_period}",
            source_url=url,
            snippet=snippet,
            source_type="official_site",
            verified=True,
        )
    ]


def has_sec_filing_target(query: str) -> bool:
    return resolve_sec_ticker(query) is not None


def resolve_sec_ticker(query: str) -> str | None:
    ticker = _extract_ticker(query)
    if ticker is not None:
        return ticker
    return _extract_company_ticker(query)


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


def _extract_company_ticker(query: str) -> str | None:
    normalized = re.sub(r"[^A-Z0-9]+", " ", query.upper()).strip()
    for company, ticker in KNOWN_COMPANY_TICKERS.items():
        if re.search(rf"(?<!\w){re.escape(company)}(?!\w)", normalized):
            return ticker
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


def _extract_financial_facts(payload: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    us_gaap = payload.get("facts", {}).get("us-gaap", {})
    if not isinstance(us_gaap, dict):
        return []
    facts: list[tuple[str, dict[str, Any]]] = []
    for label, concept in FINANCIAL_FACTS:
        fact = _latest_usd_fact(us_gaap.get(concept))
        if fact is None:
            continue
        facts.append((label, fact))
    return facts


def _latest_usd_fact(concept_payload: object) -> dict[str, Any] | None:
    if not isinstance(concept_payload, dict):
        return None
    usd_facts = concept_payload.get("units", {}).get("USD", [])
    if not isinstance(usd_facts, list):
        return None
    candidates = [
        fact
        for fact in usd_facts
        if isinstance(fact, dict)
        and fact.get("form") in {"10-K", "10-Q"}
        and isinstance(fact.get("val"), int | float)
        and isinstance(fact.get("fy"), int)
        and isinstance(fact.get("fp"), str)
        and isinstance(fact.get("filed"), str)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda fact: str(fact.get("filed", "")), reverse=True)
    return candidates[0]
