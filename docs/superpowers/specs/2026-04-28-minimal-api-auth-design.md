# Minimal API Auth Design

## Goal

Add a minimal API key authentication boundary for the InsightGraph API so a demo server can be exposed behind a simple shared secret without changing local offline defaults.

## Context

The current API is useful for demos but has no built-in authentication. Deployment docs therefore require a private network, reverse proxy auth, VPN, or API gateway before public exposure. A small built-in API key gate improves MVP safety while avoiding a full user/account system.

## Requirements

- Authentication is disabled when `INSIGHT_GRAPH_API_KEY` is unset or blank.
- When `INSIGHT_GRAPH_API_KEY` is set, all API endpoints except `/health` require a matching key.
- Accepted client headers:
  - `Authorization: Bearer <key>`
  - `X-API-Key: <key>`
- `Authorization: Bearer <key>` and `X-API-Key: <key>` are equivalent. If both are present, either matching value is sufficient.
- Invalid, missing, or malformed credentials return HTTP `401` with `{"detail":"Invalid or missing API key."}`.
- `/health` always remains unauthenticated for health checks.
- The API key must never be logged, returned, included in examples, or stored in state.
- Existing behavior remains unchanged when the env var is not configured.

## Protected Endpoints

When auth is enabled, protect:

- `POST /research`
- `POST /research/jobs`
- `GET /research/jobs`
- `GET /research/jobs/summary`
- `GET /research/jobs/{job_id}`
- `POST /research/jobs/{job_id}/cancel`
- `POST /research/jobs/{job_id}/retry`

`GET /health` remains public.

## Architecture

Add a small request dependency in `src/insight_graph/api.py`:

- Read `INSIGHT_GRAPH_API_KEY` from process env at request time.
- If unset or blank, return without enforcing auth.
- Check `Authorization` for the exact `Bearer ` scheme prefix and compare the bearer token.
- Check `X-API-Key` for direct equality.
- Use constant-time comparison through `hmac.compare_digest()` for provided credential values.
- Raise `HTTPException(status_code=401, detail="Invalid or missing API key.")` on failure.

Attach the dependency to the protected route decorators. Keep `/health` without the dependency.

## OpenAPI Behavior

Do not add a full OpenAPI security scheme in this MVP step. The current docs and tests should focus on runtime behavior. A later production-hardening step can add formal OpenAPI security metadata if needed.

## Documentation

Update:

- `docs/deployment.md`: replace the warning that there is no built-in auth with instructions for `INSIGHT_GRAPH_API_KEY`, header examples, and a note that reverse proxy/network controls are still recommended.
- `docs/research-jobs-api.md`: mention that job endpoints require an API key when `INSIGHT_GRAPH_API_KEY` is configured.
- `README.md`: mention minimal API key auth in the API MVP paragraph or docs list if needed.

## Tests

Add API tests covering:

- Auth disabled preserves existing `/research` or jobs behavior.
- `/health` remains public when auth is enabled.
- Missing credentials return `401` on a protected endpoint.
- Wrong bearer token returns `401`.
- Correct bearer token succeeds.
- Correct `X-API-Key` succeeds.
- Malformed `Authorization` value returns `401`.
- Protected research job routes reject missing credentials when auth is enabled.

Tests must not call live search providers or real LLM APIs. Use existing fake `run_research` and executor patterns.

## Non-Goals

- No login endpoint.
- No users, roles, sessions, key rotation, or multi-tenant authorization.
- No database persistence for API keys.
- No rate limiting or quotas.
- No CORS policy changes.
- No change to CLI behavior.

## Success Criteria

- Full test suite passes.
- `ruff check .` passes.
- Existing no-auth local development behavior remains unchanged.
- A demo server can enable a shared API key with one environment variable.
