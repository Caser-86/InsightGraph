# Live URL Revalidation Design

## Goal

Align InsightGraph's live research path with reference-style networked research by validating final Reporter reference URLs before the report is returned.

## Scope

- Enable URL revalidation for `--preset live-research`.
- Keep direct opt-in via `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`.
- Keep normal CLI/API/tests offline unless live mode or the explicit environment variable is used.
- Record URL validation metadata in `GraphState`.
- Never fabricate replacement citations when validation fails.

## Design

Reporter will run a final URL validation pass over verified evidence before building reference numbers and References. Validation uses a small helper that calls the existing bounded HTTP client (`fetch_text`) and maps outcomes into deterministic metadata: evidence ID, URL, status, HTTP status if available, and error if validation failed.

Validated evidence remains eligible for references. Failed validation does not generate substitute URLs or fake citations. The report References section will annotate each reference with validation status when validation is enabled, for example `(URL validated)` or `(URL validation failed: Network error...)`. This keeps reports honest while avoiding silent citation loss from transient network failures.

The `live-research` preset will set `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`. Tests will monkeypatch the validator or HTTP client and never access the network.

## Data Model

Add `GraphState.url_validation: list[dict[str, object]] = []`.

Each item:

- `evidence_id`: evidence ID.
- `source_url`: original URL.
- `valid`: boolean.
- `status_code`: HTTP status when known.
- `error`: validation error when invalid.

## Testing

- Reporter default does not validate URLs.
- Reporter validates URLs when `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`.
- References include validation annotations when validation metadata exists.
- Live research preset sets `INSIGHT_GRAPH_REPORTER_VALIDATE_URLS=1`.
- Tests use monkeypatch/fakes only; no network access.

## Non-Goals

- No retry/backoff policy in this phase.
- No replacement URL discovery.
- No URL canonicalization beyond using the evidence URL as collected.
- No validation in deterministic/offline default runs.
