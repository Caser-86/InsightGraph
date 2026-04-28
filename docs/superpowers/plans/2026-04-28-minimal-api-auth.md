# Minimal API Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in shared API key authentication to the FastAPI API while keeping `/health` and existing local no-auth behavior unchanged.

**Architecture:** Add one FastAPI dependency in `src/insight_graph/api.py` that reads `INSIGHT_GRAPH_API_KEY` at request time and accepts either `Authorization: Bearer <key>` or `X-API-Key: <key>`. Attach it only to protected API routes. Update deployment/API docs with the new opt-in behavior.

**Tech Stack:** FastAPI dependencies, `Header`, `Depends`, `hmac.compare_digest`, pytest `TestClient`, existing docs.

---

## File Structure

- Modify `src/insight_graph/api.py`: add auth env constant, error constant, dependency, and route dependencies.
- Modify `tests/test_api.py`: add auth-disabled, health-bypass, failure, success, and job-route coverage.
- Modify `docs/deployment.md`: document `INSIGHT_GRAPH_API_KEY` setup and header usage.
- Modify `docs/research-jobs-api.md`: document conditional auth for job endpoints.
- Modify `README.md`: mention minimal API key auth in the API MVP paragraph.

## Task 1: Auth Helper and `/research` Protection

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Write failing tests for optional auth and `/research`**

Add these tests after `test_health_returns_ok()` in `tests/test_api.py`:

```python
def test_health_remains_public_when_api_key_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_research_allows_requests_when_api_key_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("INSIGHT_GRAPH_API_KEY", raising=False)

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare AI coding agents"})

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"


def test_research_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post("/research", json={"query": "Compare AI coding agents"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_rejects_wrong_bearer_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Bearer wrong-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_rejects_malformed_authorization(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Token demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_accepts_bearer_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Bearer demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"


def test_research_accepts_x_api_key(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"X-API-Key": "demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"


def test_research_accepts_matching_key_when_other_header_is_wrong(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")

    def fake_run_research(query: str) -> GraphState:
        return make_api_state(query)

    monkeypatch.setattr(api_module, "run_research", fake_run_research)
    client = TestClient(api_module.app)

    response = client.post(
        "/research",
        headers={"Authorization": "Bearer wrong-key", "X-API-Key": "demo-key"},
        json={"query": "Compare AI coding agents"},
    )

    assert response.status_code == 200
    assert response.json()["user_request"] == "Compare AI coding agents"
```

- [ ] **Step 2: Run the new auth tests and verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_health_remains_public_when_api_key_is_configured tests/test_api.py::test_research_allows_requests_when_api_key_is_unset tests/test_api.py::test_research_rejects_missing_api_key_when_configured tests/test_api.py::test_research_rejects_wrong_bearer_api_key tests/test_api.py::test_research_rejects_malformed_authorization tests/test_api.py::test_research_accepts_bearer_api_key tests/test_api.py::test_research_accepts_x_api_key tests/test_api.py::test_research_accepts_matching_key_when_other_header_is_wrong -v
```

Expected: tests that expect `401` fail because `/research` is not protected yet.

- [ ] **Step 3: Add auth imports and constants**

In `src/insight_graph/api.py`, change imports:

```python
import hmac
import os
from collections.abc import Iterator
```

Change the FastAPI import:

```python
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Query
```

After `_RESEARCH_ENV_LOCK`, add:

```python
_API_KEY_ENV_VAR = "INSIGHT_GRAPH_API_KEY"
_API_KEY_AUTH_ERROR_DETAIL = "Invalid or missing API key."
```

- [ ] **Step 4: Add API key dependency**

Add this helper before `@router.get("/health")`:

```python
def _configured_api_key() -> str | None:
    api_key = os.environ.get(_API_KEY_ENV_VAR, "").strip()
    return api_key or None


def _candidate_matches_api_key(candidate: str | None, expected: str) -> bool:
    if candidate is None:
        return False
    return hmac.compare_digest(candidate, expected)


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    token = authorization[len(prefix) :].strip()
    return token or None


def require_api_key(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    expected_api_key = _configured_api_key()
    if expected_api_key is None:
        return

    candidates = [_bearer_token(authorization), x_api_key]
    if any(_candidate_matches_api_key(candidate, expected_api_key) for candidate in candidates):
        return

    raise HTTPException(status_code=401, detail=_API_KEY_AUTH_ERROR_DETAIL)
```

- [ ] **Step 5: Protect `/research`**

Change the route decorator:

```python
@router.post("/research", dependencies=[Depends(require_api_key)])
def research(request: ResearchRequest) -> dict[str, Any]:
```

- [ ] **Step 6: Run new auth tests and existing research test**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_health_remains_public_when_api_key_is_configured tests/test_api.py::test_research_allows_requests_when_api_key_is_unset tests/test_api.py::test_research_rejects_missing_api_key_when_configured tests/test_api.py::test_research_rejects_wrong_bearer_api_key tests/test_api.py::test_research_rejects_malformed_authorization tests/test_api.py::test_research_accepts_bearer_api_key tests/test_api.py::test_research_accepts_x_api_key tests/test_api.py::test_research_accepts_matching_key_when_other_header_is_wrong tests/test_api.py::test_research_returns_cli_aligned_json -v
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 1**

Run:

```powershell
git add src/insight_graph/api.py tests/test_api.py
git commit -m "feat: add opt-in api key auth"
```

## Task 2: Protect Research Job Routes

**Files:**
- Modify: `tests/test_api.py`
- Modify: `src/insight_graph/api.py`

- [ ] **Step 1: Write failing job route auth tests**

Add these tests after the Task 1 auth tests in `tests/test_api.py`:

```python
def test_research_jobs_create_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", FakeExecutor())
    client = TestClient(api_module.app)

    response = client.post(
        "/research/jobs",
        json={"query": "Compare AI coding agents", "preset": "offline"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_jobs_create_accepts_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    fake_executor = FakeExecutor()
    monkeypatch.setattr(api_module, "_JOB_EXECUTOR", fake_executor)
    client = TestClient(api_module.app)

    response = client.post(
        "/research/jobs",
        headers={"X-API-Key": "demo-key"},
        json={"query": "Compare AI coding agents", "preset": "offline"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert len(fake_executor.submissions) == 1


def test_research_jobs_list_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/research/jobs")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_jobs_summary_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/summary")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_job_detail_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.get("/research/jobs/job-123")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_job_cancel_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post("/research/jobs/job-123/cancel")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}


def test_research_job_retry_rejects_missing_api_key_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("INSIGHT_GRAPH_API_KEY", "demo-key")
    client = TestClient(api_module.app)

    response = client.post("/research/jobs/job-123/retry")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid or missing API key."}
```

- [ ] **Step 2: Run job route auth tests and verify they fail**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py::test_research_jobs_create_rejects_missing_api_key_when_configured tests/test_api.py::test_research_jobs_create_accepts_api_key_when_configured tests/test_api.py::test_research_jobs_list_rejects_missing_api_key_when_configured tests/test_api.py::test_research_jobs_summary_rejects_missing_api_key_when_configured tests/test_api.py::test_research_job_detail_rejects_missing_api_key_when_configured tests/test_api.py::test_research_job_cancel_rejects_missing_api_key_when_configured tests/test_api.py::test_research_job_retry_rejects_missing_api_key_when_configured -v
```

Expected: tests that expect `401` fail because job routes are not protected yet.

- [ ] **Step 3: Add a shared route dependency constant**

After `require_api_key()` in `src/insight_graph/api.py`, add:

```python
_API_KEY_DEPENDENCY = [Depends(require_api_key)]
```

Then change `/research` to use the constant:

```python
@router.post("/research", dependencies=_API_KEY_DEPENDENCY)
def research(request: ResearchRequest) -> dict[str, Any]:
```

- [ ] **Step 4: Protect job route decorators**

Add `dependencies=_API_KEY_DEPENDENCY,` to each protected job route decorator:

```python
@router.post(
    "/research/jobs",
    status_code=202,
    response_model=ResearchJobCreateResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
```

```python
@router.get(
    "/research/jobs",
    response_model=ResearchJobsListResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
```

```python
@router.get(
    "/research/jobs/summary",
    response_model=ResearchJobsSummaryResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
```

```python
@router.post(
    "/research/jobs/{job_id}/cancel",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
```

```python
@router.post(
    "/research/jobs/{job_id}/retry",
    status_code=202,
    response_model=ResearchJobCreateResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
```

```python
@router.get(
    "/research/jobs/{job_id}",
    response_model=ResearchJobDetailResponse,
    response_model_exclude_none=True,
    dependencies=_API_KEY_DEPENDENCY,
    tags=[_RESEARCH_JOBS_TAG],
```

- [ ] **Step 5: Run API tests**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py -v
```

Expected: all API tests pass.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add src/insight_graph/api.py tests/test_api.py
git commit -m "feat: protect research job routes"
```

## Task 3: Documentation and Verification

**Files:**
- Modify: `docs/deployment.md`
- Modify: `docs/research-jobs-api.md`
- Modify: `README.md`

- [ ] **Step 1: Update deployment guide security boundary**

In `docs/deployment.md`, replace the current security boundary bullets:

```markdown
Current security boundary:
- `/health`, `/research`, and `/research/jobs/*` do not require built-in authentication yet.
- Put the API behind a private network, VPN, reverse proxy auth, or API gateway before exposing it outside a trusted environment.
- Do not pass API keys in request bodies or query strings. Configure providers through environment variables.
```

with:

```markdown
Current security boundary:
- Set `INSIGHT_GRAPH_API_KEY` to require a shared API key for `/research` and `/research/jobs/*`.
- `/health` remains public for health checks.
- Keep reverse proxy, private network, VPN, or API gateway controls for any public demo server.
- Do not pass provider API keys in request bodies or query strings. Configure providers through environment variables.
```

- [ ] **Step 2: Add auth section to deployment guide**

In `docs/deployment.md`, add this section after the install section and before `## Offline API Smoke Test`:

```markdown
## Optional API Key Auth

Set `INSIGHT_GRAPH_API_KEY` to protect all API endpoints except `/health`:

```bash
export INSIGHT_GRAPH_API_KEY="replace-with-shared-demo-key"
```

Clients can authenticate with either header:

```bash
curl -X POST http://127.0.0.1:8000/research \
  -H "Authorization: Bearer replace-with-shared-demo-key" \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot"}'
```

```bash
curl -X POST http://127.0.0.1:8000/research/jobs \
  -H "X-API-Key: replace-with-shared-demo-key" \
  -H "Content-Type: application/json" \
  -d '{"query":"Compare Cursor, OpenCode, and GitHub Copilot","preset":"offline"}'
```

When `INSIGHT_GRAPH_API_KEY` is unset or blank, local development remains unauthenticated.
```

- [ ] **Step 3: Update deployment reverse proxy wording**

In `docs/deployment.md`, replace:

```markdown
Until built-in API authentication lands, expose the service only through a protected boundary. Minimum options:
```

with:

```markdown
Built-in API key auth is a minimal shared-secret gate. For public demos, still expose the service through a protected boundary. Minimum options:
```

- [ ] **Step 4: Update systemd example**

In the systemd example in `docs/deployment.md`, add this line after `Environment=INSIGHT_GRAPH_LLM_MODEL=your-model`:

```ini
EnvironmentFile=-/etc/insightgraph/auth.env
```

After the `secrets.env` example, add:

```markdown
Example `/etc/insightgraph/auth.env`:

```ini
INSIGHT_GRAPH_API_KEY=replace-with-shared-demo-key
```
```

- [ ] **Step 5: Update research jobs API docs**

In `docs/research-jobs-api.md`, after the opening paragraph, add:

```markdown
If `INSIGHT_GRAPH_API_KEY` is configured, all research job endpoints require `Authorization: Bearer <key>` or `X-API-Key: <key>`. `/health` remains public.
```

- [ ] **Step 6: Update README API MVP paragraph**

In `README.md`, append this sentence to the API MVP paragraph:

```markdown
设置 `INSIGHT_GRAPH_API_KEY` 后，除 `/health` 外的 API endpoint 会要求 `Authorization: Bearer <key>` 或 `X-API-Key: <key>`。
```

- [ ] **Step 7: Run documentation checks**

Run:

```powershell
git diff --check -- README.md docs/deployment.md docs/research-jobs-api.md
```

Expected: no output except possible CRLF warnings.

- [ ] **Step 8: Run focused and full verification**

Run:

```powershell
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest tests/test_api.py -v
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m pytest
& "C:\Users\77670\AppData\Local\Programs\Python\Python313\python.exe" -m ruff check .
```

Expected:
- API tests pass.
- Full suite passes with the existing skipped test count.
- Ruff prints `All checks passed!`.

- [ ] **Step 9: Commit Task 3**

Run:

```powershell
git add README.md docs/deployment.md docs/research-jobs-api.md
git commit -m "docs: document api key auth"
```

## Final Verification

- [ ] **Step 1: Inspect status and commits**

Run:

```powershell
git status --short --branch
git log --oneline --max-count=8
```

Expected: clean branch with auth implementation and docs commits on top of the design/plan commits.

- [ ] **Step 2: Push after approval**

Only push when the controller/user approves:

```powershell
git push origin master
```

Expected: `master` updates on origin.

- [ ] **Step 3: Wait for CI after push**

Run:

```powershell
gh run list --branch master --limit 5
gh run watch <run-id> --exit-status
```

Expected: CI completes successfully.

## Self-Review Notes

- Spec coverage: plan covers opt-in env behavior, `/health` bypass, both accepted headers, malformed/missing/wrong credential failures, protected endpoints, docs, and verification.
- Placeholder scan: no TBD/TODO placeholders or vague implementation steps remain.
- Scope check: this is one focused API boundary change and does not add login, users, rate limiting, CORS, or key persistence.
